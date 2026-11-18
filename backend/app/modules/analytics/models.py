import enum
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, Integer, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class GapSeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TopicMastery(Base):
    __tablename__ = "topic_mastery"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # 0 to 100
    total_attempted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_practiced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    student = relationship("app.modules.auth.models.User")
    topic = relationship("app.modules.curriculum.models.Topic")


class KnowledgeGap(Base):
    __tablename__ = "knowledge_gaps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    gap_severity: Mapped[str] = mapped_column(String(20), default=GapSeverity.MEDIUM.value, nullable=False)
    detected_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    student = relationship("app.modules.auth.models.User")
    topic = relationship("app.modules.curriculum.models.Topic")
