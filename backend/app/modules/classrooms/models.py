import uuid
import enum
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Text, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class ClassroomStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class AssignmentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


class AssignmentType(str, enum.Enum):
    EXAM = "EXAM"
    FILE = "FILE"


class FileSubmissionStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    GRADED = "GRADED"


class Classroom(Base, TimestampMixin):
    __tablename__ = "classrooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    teacher_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True, nullable=False)
    grade_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("grades.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=ClassroomStatus.ACTIVE.value, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_students: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    teacher = relationship("User")
    grade = relationship("Grade")
    members: Mapped[List["ClassroomMember"]] = relationship("ClassroomMember", back_populates="classroom", cascade="all, delete-orphan")
    assignments: Mapped[List["Assignment"]] = relationship("Assignment", back_populates="classroom", cascade="all, delete-orphan")

    @property
    def member_count(self) -> int:
        return len(self.members) if self.members else 0

    @property
    def assignment_count(self) -> int:
        return len(self.assignments) if self.assignments else 0


class ClassroomMember(Base):
    __tablename__ = "classroom_members"
    __table_args__ = (
        UniqueConstraint("classroom_id", "student_id", name="uq_classroom_member"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    classroom_id: Mapped[str] = mapped_column(String(36), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    classroom: Mapped["Classroom"] = relationship("Classroom", back_populates="members")
    student = relationship("User")


class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    classroom_id: Mapped[str] = mapped_column(String(36), ForeignKey("classrooms.id", ondelete="CASCADE"), nullable=False)
    assignment_type: Mapped[str] = mapped_column(String(20), default=AssignmentType.EXAM.value, server_default="EXAM", nullable=False)
    exam_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=True)
    attachment_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    attachment_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    total_points: Mapped[float] = mapped_column(Float, default=10.0, server_default="10.0", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    open_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    allow_late_submission: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=AssignmentStatus.DRAFT.value, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    classroom: Mapped["Classroom"] = relationship("Classroom", back_populates="assignments")
    exam = relationship("Exam")
    attempts = relationship("ExamAttempt", back_populates="assignment")
    file_submissions: Mapped[List["AssignmentFileSubmission"]] = relationship(
        "AssignmentFileSubmission",
        back_populates="assignment",
        cascade="all, delete-orphan",
    )


class AssignmentFileSubmission(Base, TimestampMixin):
    __tablename__ = "assignment_file_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_assignment_file_submission"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assignment_id: Mapped[str] = mapped_column(String(36), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    student_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=FileSubmissionStatus.SUBMITTED.value, nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    teacher_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    graded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    assignment: Mapped["Assignment"] = relationship("Assignment", back_populates="file_submissions")
    student = relationship("User")
