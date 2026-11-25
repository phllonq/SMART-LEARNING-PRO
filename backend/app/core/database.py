import logging
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import MetaData, DateTime, func, event, text
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

# Standard naming conventions for constraints and indexes
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)


class Base(DeclarativeBase):
    metadata = metadata


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


# Configure Async Engine
engine_kwargs = {"echo": False}
if "sqlite" in settings.DATABASE_URL:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_async_engine(settings.DATABASE_URL, **engine_kwargs)

if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def _ensure_assignments_file_columns_sync(sync_conn) -> None:
    """
    Idempotently migrate existing `assignments` table to support nullable `exam_id`
    and file-based assignment columns without losing existing records.
    """
    dialect = sync_conn.dialect.name
    if dialect == "sqlite":
        rows = sync_conn.execute(text("PRAGMA table_info(assignments)")).fetchall()
        if not rows:
            return
        cols = {row[1]: row for row in rows}
        needs_exam_nullable = cols.get("exam_id", (None, None, None, 0))[3] == 1
        needs_new_cols = not all(
            c in cols for c in ("assignment_type", "attachment_url", "attachment_name", "total_points")
        )
        if not needs_exam_nullable and not needs_new_cols:
            return

        sync_conn.execute(text("PRAGMA foreign_keys=OFF"))
        try:
            sync_conn.execute(
                text(
                    """
                    CREATE TABLE assignments_migrated (
                        id VARCHAR(36) NOT NULL PRIMARY KEY,
                        classroom_id VARCHAR(36) NOT NULL REFERENCES classrooms(id) ON DELETE CASCADE,
                        assignment_type VARCHAR(20) NOT NULL DEFAULT 'EXAM',
                        exam_id VARCHAR(36) REFERENCES exams(id) ON DELETE CASCADE,
                        attachment_url VARCHAR(500),
                        attachment_name VARCHAR(255),
                        total_points FLOAT NOT NULL DEFAULT 10.0,
                        title VARCHAR(255) NOT NULL,
                        description TEXT,
                        open_date DATETIME,
                        due_date DATETIME NOT NULL,
                        max_attempts INTEGER NOT NULL DEFAULT 1,
                        allow_late_submission BOOLEAN NOT NULL DEFAULT 0,
                        allow_review BOOLEAN NOT NULL DEFAULT 1,
                        status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
                        is_published BOOLEAN NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            has_type = "assignment_type" in cols
            has_att_url = "attachment_url" in cols
            has_att_name = "attachment_name" in cols
            has_pts = "total_points" in cols

            sel_type = "assignment_type" if has_type else "'EXAM'"
            sel_att_url = "attachment_url" if has_att_url else "NULL"
            sel_att_name = "attachment_name" if has_att_name else "NULL"
            sel_pts = "total_points" if has_pts else "10.0"

            sync_conn.execute(
                text(
                    f"""
                    INSERT INTO assignments_migrated (
                        id, classroom_id, assignment_type, exam_id, attachment_url, attachment_name,
                        total_points, title, description, open_date, due_date, max_attempts,
                        allow_late_submission, allow_review, status, is_published, created_at, updated_at
                    )
                    SELECT
                        id, classroom_id, {sel_type}, exam_id, {sel_att_url}, {sel_att_name},
                        {sel_pts}, title, description, open_date, due_date, max_attempts,
                        allow_late_submission, allow_review, status, is_published, created_at, updated_at
                    FROM assignments
                    """
                )
            )
            sync_conn.execute(text("DROP TABLE assignments"))
            sync_conn.execute(text("ALTER TABLE assignments_migrated RENAME TO assignments"))
        finally:
            sync_conn.execute(text("PRAGMA foreign_keys=ON"))
    elif dialect == "postgresql":
        sync_conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS assignment_type VARCHAR(20) NOT NULL DEFAULT 'EXAM'"))
        sync_conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS attachment_url VARCHAR(500)"))
        sync_conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS attachment_name VARCHAR(255)"))
        sync_conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS total_points DOUBLE PRECISION NOT NULL DEFAULT 10.0"))
        sync_conn.execute(text("ALTER TABLE assignments ALTER COLUMN exam_id DROP NOT NULL"))


async def init_db() -> None:
    """Create all tables if they do not exist and apply idempotent schema updates."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_assignments_file_columns_sync)
    logger.info("Database initialized successfully.")
