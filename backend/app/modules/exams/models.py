import enum
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, Integer, Float, Text, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class ExamStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class AttemptStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    AUTO_SUBMITTED = "AUTO_SUBMITTED"
    GRADED = "GRADED"
    ABANDONED = "ABANDONED"


class Exam(Base, TimestampMixin):
    __tablename__ = "exams"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    creator_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    subject_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    grade_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("grades.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    total_points: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    passing_points: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=True)
    shuffle_options: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_review: Mapped[bool] = mapped_column(Boolean, default=True)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default=ExamStatus.PUBLISHED.value, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    exam_questions: Mapped[List["ExamQuestion"]] = relationship("ExamQuestion", back_populates="exam", cascade="all, delete-orphan", order_by="ExamQuestion.order_index")
    attempts: Mapped[List["ExamAttempt"]] = relationship("ExamAttempt", back_populates="exam", cascade="all, delete-orphan")
    subject = relationship("app.modules.curriculum.models.Subject")
    grade = relationship("app.modules.curriculum.models.Grade")
    creator = relationship("app.modules.auth.models.User")

    @property
    def question_count(self) -> int:
        return len(self.exam_questions) if self.exam_questions else 0


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    points: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="exam_questions")
    question = relationship("app.modules.questions.models.Question")


class ExamAttempt(Base, TimestampMixin):
    __tablename__ = "exam_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default=AttemptStatus.IN_PROGRESS.value, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    deadline_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    maximum_score: Mapped[float] = mapped_column(Float, default=10.0)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)
    questions_snapshot_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Immutable sanitized questions snapshot
    answer_key_snapshot_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Immutable server-side answer keys snapshot
    assignment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True)

    exam: Mapped["Exam"] = relationship("Exam", back_populates="attempts")
    assignment = relationship("Assignment", back_populates="attempts")
    student = relationship("app.modules.auth.models.User")
    answers: Mapped[List["StudentAnswer"]] = relationship("StudentAnswer", back_populates="attempt", cascade="all, delete-orphan")
    result: Mapped[Optional["ExamResult"]] = relationship("ExamResult", back_populates="attempt", uselist=False, cascade="all, delete-orphan")


class StudentAnswer(Base):
    __tablename__ = "student_answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attempt_id: Mapped[str] = mapped_column(String(36), ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    selected_option_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    selected_option_ids_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # For multiple choice
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)               # For short answer / essay
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    points_awarded: Mapped[float] = mapped_column(Float, default=0.0)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=datetime.utcnow, nullable=True)

    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="answers")
    question = relationship("app.modules.questions.models.Question")


class ExamResult(Base, TimestampMixin):
    __tablename__ = "exam_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    attempt_id: Mapped[str] = mapped_column(String(36), ForeignKey("exam_attempts.id", ondelete="CASCADE"), unique=True, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    correct_answers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wrong_answers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_answers_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accuracy_percentage: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    feedback_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    attempt: Mapped["ExamAttempt"] = relationship("ExamAttempt", back_populates="result")
