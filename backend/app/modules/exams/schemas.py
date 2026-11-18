from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import datetime
from app.modules.exams.models import ExamStatus, AttemptStatus


# --- Question in Exam Schemas ---
class ExamQuestionAssign(BaseModel):
    question_id: str
    points: float = Field(0.5, ge=0.0, le=100.0)
    order_index: int = 0


class ExamQuestionReorderRequest(BaseModel):
    items: List[ExamQuestionAssign]


class ExamQuestionSummary(BaseModel):
    id: str
    question_id: str
    points: float
    order_index: int
    content: str
    question_type: str
    difficulty_level: str
    options_count: int

    model_config = ConfigDict(from_attributes=True)


# --- Exam Schemas ---
class ExamBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    subject_id: Optional[str] = None
    grade_id: Optional[int] = Field(None, ge=1, le=12)
    duration_minutes: int = Field(45, ge=5, le=300)
    total_points: float = Field(10.0, ge=1.0, le=100.0)
    passing_points: float = Field(5.0, ge=0.0, le=100.0)
    shuffle_questions: bool = True
    shuffle_options: bool = True
    allow_review: bool = True
    max_attempts: int = Field(1, ge=1, le=10)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class ExamCreate(ExamBase):
    status: ExamStatus = ExamStatus.DRAFT
    question_ids: Optional[List[str]] = Field(default_factory=list, description="Khởi tạo đề thi với danh sách ID câu hỏi")


class ExamUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    subject_id: Optional[str] = None
    grade_id: Optional[int] = Field(None, ge=1, le=12)
    duration_minutes: Optional[int] = Field(None, ge=5, le=300)
    total_points: Optional[float] = Field(None, ge=1.0, le=100.0)
    passing_points: Optional[float] = Field(None, ge=0.0, le=100.0)
    shuffle_questions: Optional[bool] = None
    shuffle_options: Optional[bool] = None
    allow_review: Optional[bool] = None
    max_attempts: Optional[int] = Field(None, ge=1, le=10)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[ExamStatus] = None


class ExamSummaryResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    subject_id: Optional[str] = None
    grade_id: Optional[int] = None
    creator_id: Optional[str] = None
    duration_minutes: int
    total_points: float
    passing_points: float
    max_attempts: int
    status: str
    is_published: bool
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    question_count: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExamDetailResponse(ExamSummaryResponse):
    questions: List[Dict[str, Any]] = []


# --- Student Attempt & Workflow Schemas ---
class ExamStartResponse(BaseModel):
    attempt_id: str
    exam_id: str
    attempt_number: int
    started_at: datetime
    deadline_at: datetime
    duration_minutes: int
    total_questions: int
    # Snapshot of questions WITHOUT answer keys
    questions: List[Dict[str, Any]]


class AutosaveAnswerRequest(BaseModel):
    selected_option_id: Optional[str] = None
    selected_option_ids: Optional[List[str]] = None
    answer_text: Optional[str] = None
    is_flagged: bool = False
    time_spent_seconds: int = 0


class AutosaveAnswerResponse(BaseModel):
    status: str = "SAVED"
    attempt_id: str
    question_id: str
    saved_at: datetime


class ExamSubmitResponse(BaseModel):
    attempt_id: str
    exam_id: str
    status: str
    total_score: float
    maximum_score: float
    passing_score: float
    is_passed: bool
    correct_answers_count: int
    wrong_answers_count: int
    skipped_answers_count: int
    accuracy_percentage: float
    feedback_summary: Optional[str] = None
    submitted_at: datetime
    review_allowed: bool = False
    question_reviews: Optional[List[Dict[str, Any]]] = None


class SubmissionSummaryResponse(BaseModel):
    attempt_id: str
    student_id: str
    student_name: str
    attempt_number: int
    status: str
    started_at: datetime
    submitted_at: Optional[datetime] = None
    score: Optional[float] = None
    maximum_score: float = 10.0
    is_passed: bool = False
    time_spent_seconds: int = 0

    model_config = ConfigDict(from_attributes=True)
