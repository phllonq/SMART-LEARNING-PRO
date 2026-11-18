import uuid
from typing import Optional, List
from sqlalchemy import String, Boolean, Integer, Text, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # 6, 7, 8, 9, 10, 11, 12
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # "Lớp 11"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    subjects: Mapped[List["Subject"]] = relationship("Subject", back_populates="grade", cascade="all, delete-orphan")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # e.g., "toan-11", "vat-ly-11"
    grade_id: Mapped[int] = mapped_column(Integer, ForeignKey("grades.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    grade: Mapped["Grade"] = relationship("Grade", back_populates="subjects")
    chapters: Mapped[List["Chapter"]] = relationship("Chapter", back_populates="subject", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id: Mapped[str] = mapped_column(String(50), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    subject: Mapped["Subject"] = relationship("Subject", back_populates="chapters")
    topics: Mapped[List["Topic"]] = relationship("Topic", back_populates="chapter", cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id: Mapped[str] = mapped_column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    chapter: Mapped["Chapter"] = relationship("Chapter", back_populates="topics")
    lessons: Mapped[List["Lesson"]] = relationship("Lesson", back_populates="topic", cascade="all, delete-orphan")


class Lesson(Base, TimestampMixin):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    topic_id: Mapped[str] = mapped_column(String(36), ForeignKey("topics.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)  # KaTeX math supported
    video_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=45)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    topic: Mapped["Topic"] = relationship("Topic", back_populates="lessons")
    materials: Mapped[List["LearningMaterial"]] = relationship("LearningMaterial", back_populates="lesson", cascade="all, delete-orphan")


class LearningMaterial(Base, TimestampMixin):
    __tablename__ = "learning_materials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lesson_id: Mapped[str] = mapped_column(String(36), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), default="PDF")  # PDF, VIDEO, DOCX, SLIDE
    file_url: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="materials")
