import enum
import uuid
from typing import Optional, List
from sqlalchemy import String, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class QuestionType(str, enum.Enum):
    SINGLE_CHOICE = "SINGLE_CHOICE"
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    TRUE_FALSE = "TRUE_FALSE"
    SHORT_ANSWER = "SHORT_ANSWER"
    NUMERIC = "NUMERIC"
    ESSAY = "ESSAY"


class DifficultyLevel(str, enum.Enum):
    RECOGNITION = "RECOGNITION"          # Nhận biết
    COMPREHENSION = "COMPREHENSION"      # Thông hiểu
    APPLICATION = "APPLICATION"          # Vận dụng
    HIGH_APPLICATION = "HIGH_APPLICATION"# Vận dụng cao


class Question(Base, TimestampMixin):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    creator_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    question_type: Mapped[str] = mapped_column(String(30), default=QuestionType.SINGLE_CHOICE.value, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # KaTeX math supported
    difficulty_level: Mapped[str] = mapped_column(String(20), default=DifficultyLevel.COMPREHENSION.value, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Official step-by-step solution
    hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)         # Socratic hint
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)

    options: Mapped[List["QuestionOption"]] = relationship("QuestionOption", back_populates="question", cascade="all, delete-orphan", order_by="QuestionOption.order_index")


class QuestionOption(Base):
    __tablename__ = "question_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    option_key: Mapped[str] = mapped_column(String(10), nullable=False)  # A, B, C, D
    content: Mapped[str] = mapped_column(Text, nullable=False)          # KaTeX supported
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped["Question"] = relationship("Question", back_populates="options")
