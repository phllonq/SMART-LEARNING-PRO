import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class Classroom(Base, TimestampMixin):
    __tablename__ = "classrooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    teacher_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True, nullable=False)
    grade_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("grades.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    teacher = relationship("app.modules.auth.models.User")
    members: Mapped[List["ClassroomMember"]] = relationship("ClassroomMember", back_populates="classroom", cascade="all, delete-orphan")
    assignments: Mapped[List["Assignment"]] = relationship("Assignment", back_populates="classroom", cascade="all, delete-orphan")


class ClassroomMember(Base):
    __tablename__ = "classroom_members"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    classroom_id: Mapped[str] = mapped_column(String(36), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    classroom: Mapped["Classroom"] = relationship("Classroom", back_populates="members")
    student = relationship("app.modules.auth.models.User")


class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    classroom_id: Mapped[str] = mapped_column(String(36), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False)
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    classroom: Mapped["Classroom"] = relationship("Classroom", back_populates="assignments")
    exam = relationship("app.modules.exams.models.Exam")
