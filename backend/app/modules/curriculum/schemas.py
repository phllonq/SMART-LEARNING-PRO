from typing import Optional, List, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

T = TypeVar("T")


# Pagination Schema
class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)


# Grade Schemas
class GradeResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    order_index: int = 0

    model_config = ConfigDict(from_attributes=True)


# Subject Schemas
class SubjectBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=20)
    icon: Optional[str] = None
    color: Optional[str] = None
    is_published: bool = True
    order_index: int = 0


class SubjectCreate(SubjectBase):
    id: str = Field(..., min_length=2, max_length=50)
    grade_id: int


class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    is_published: Optional[bool] = None
    order_index: Optional[int] = None


class SubjectResponse(SubjectBase):
    id: str
    grade_id: int

    model_config = ConfigDict(from_attributes=True)


# Learning Material Schema
class MaterialResponse(BaseModel):
    id: str
    lesson_id: str
    title: str
    file_type: str
    file_url: str
    file_size_bytes: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# Lesson Schemas
class LessonBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    content_markdown: str
    video_url: Optional[str] = None
    duration_minutes: int = 45
    order_index: int = 0


class LessonCreate(LessonBase):
    topic_id: str


class LessonUpdate(BaseModel):
    title: Optional[str] = None
    content_markdown: Optional[str] = None
    video_url: Optional[str] = None
    duration_minutes: Optional[int] = None
    order_index: Optional[int] = None


class LessonSummaryResponse(BaseModel):
    id: str
    topic_id: str
    title: str
    duration_minutes: int
    order_index: int
    has_video: bool = False

    model_config = ConfigDict(from_attributes=True)


class LessonDetailResponse(BaseModel):
    id: str
    topic_id: str
    title: str
    content_markdown: str
    video_url: Optional[str] = None
    duration_minutes: int
    order_index: int
    created_at: datetime
    materials: List[MaterialResponse] = []

    model_config = ConfigDict(from_attributes=True)


# Topic Schemas
class TopicBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    order_index: int = 0


class TopicCreate(TopicBase):
    chapter_id: str


class TopicResponse(TopicBase):
    id: str
    chapter_id: str
    lessons: List[LessonSummaryResponse] = []

    model_config = ConfigDict(from_attributes=True)


# Chapter Schemas
class ChapterBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    order_index: int = 0


class ChapterCreate(ChapterBase):
    subject_id: str


class ChapterResponse(ChapterBase):
    id: str
    subject_id: str
    topics: List[TopicResponse] = []

    model_config = ConfigDict(from_attributes=True)
