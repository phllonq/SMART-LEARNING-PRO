import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from app.modules.classrooms.models import ClassroomStatus, AssignmentStatus


# ==============================================================================
# CLASSROOM SCHEMAS
# ==============================================================================

class ClassroomCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=150, description="Tên lớp học")
    grade_id: Optional[int] = Field(None, ge=1, le=12, description="Khối lớp (1-12)")
    description: Optional[str] = Field(None, max_length=1000, description="Mô tả lớp học")
    max_students: int = Field(default=50, ge=1, le=500, description="Sĩ số tối đa")


class ClassroomUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=150)
    grade_id: Optional[int] = Field(None, ge=1, le=12)
    description: Optional[str] = Field(None, max_length=1000)
    max_students: Optional[int] = Field(None, ge=1, le=500)


class ClassroomJoinRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=16, description="Mã tham gia lớp học")


class ClassroomMemberResponse(BaseModel):
    id: str
    student_id: str
    student_name: str
    student_email: str
    student_avatar: Optional[str] = None
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassroomSummaryResponse(BaseModel):
    id: str
    name: str
    code: str
    grade_id: Optional[int] = None
    teacher_id: str
    teacher_name: Optional[str] = None
    description: Optional[str] = None
    status: str
    is_archived: bool
    max_students: int
    member_count: int = 0
    assignment_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClassroomDetailResponse(ClassroomSummaryResponse):
    members: List[ClassroomMemberResponse] = []


class ClassroomStatisticsResponse(BaseModel):
    classroom_id: str
    name: str
    total_students: int
    total_assignments: int
    active_assignments: int
    total_submissions: int
    average_score: float = 0.0
    completion_rate_percentage: float = 0.0


# ==============================================================================
# ASSIGNMENT SCHEMAS
# ==============================================================================

class AssignmentCreate(BaseModel):
    exam_id: str = Field(..., description="ID đề thi từ Ngân hàng đề")
    title: str = Field(..., min_length=3, max_length=255, description="Tiêu đề bài tập")
    description: Optional[str] = Field(None, description="Hướng dẫn làm bài tập")
    open_date: Optional[datetime] = Field(None, description="Thời điểm mở bài tập")
    due_date: datetime = Field(..., description="Hạn chót nộp bài")
    max_attempts: int = Field(default=1, ge=1, le=10, description="Số lần làm bài tối đa")
    allow_late_submission: bool = Field(default=False, description="Cho phép nộp muộn")
    allow_review: bool = Field(default=True, description="Cho phép xem đáp án và lời giải sau khi nộp")
    status: AssignmentStatus = Field(default=AssignmentStatus.DRAFT, description="Trạng thái ban đầu")


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    open_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    max_attempts: Optional[int] = Field(None, ge=1, le=10)
    allow_late_submission: Optional[bool] = None
    allow_review: Optional[bool] = None
    status: Optional[AssignmentStatus] = None


class AssignmentSummaryResponse(BaseModel):
    id: str
    classroom_id: str
    classroom_name: Optional[str] = None
    assignment_type: str = "EXAM"
    exam_id: Optional[str] = None
    exam_title: Optional[str] = None
    attachment_name: Optional[str] = None
    has_attachment: bool = False
    attachment_download_url: Optional[str] = None
    title: str
    description: Optional[str] = None
    open_date: Optional[datetime] = None
    due_date: datetime
    max_attempts: int
    allow_late_submission: bool
    allow_review: bool
    status: str
    is_published: bool
    total_points: float = 10.0
    duration_minutes: int = 45
    question_count: int = 0
    my_status: Optional[str] = None  # NOT_STARTED, IN_PROGRESS, SUBMITTED, GRADED
    my_score: Optional[float] = None
    my_attempts_count: int = 0
    my_file_submission: Optional["FileSubmissionResponse"] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileSubmissionResponse(BaseModel):
    id: str
    assignment_id: str
    student_id: str
    file_name: str
    file_size: int
    content_type: Optional[str] = None
    student_note: Optional[str] = None
    status: str
    score: Optional[float] = None
    teacher_feedback: Optional[str] = None
    submitted_at: datetime
    graded_at: Optional[datetime] = None
    download_url: str

    model_config = ConfigDict(from_attributes=True)


class FileSubmissionGradeRequest(BaseModel):
    score: float = Field(..., ge=0.0, le=100.0, description="Điểm chấm cho bài nộp")
    teacher_feedback: Optional[str] = Field(None, max_length=2000, description="Nhận xét của giáo viên")


class AssignmentSubmissionItem(BaseModel):
    student_id: str
    student_name: str
    student_email: str
    status: str  # NOT_STARTED, IN_PROGRESS, SUBMITTED, GRADED
    attempt_id: Optional[str] = None
    attempt_number: int = 0
    file_submission_id: Optional[str] = None
    submitted_file_name: Optional[str] = None
    submitted_file_size: Optional[int] = None
    student_note: Optional[str] = None
    teacher_feedback: Optional[str] = None
    download_url: Optional[str] = None
    score: Optional[float] = None
    maximum_score: float = 10.0
    is_passed: bool = False
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    time_spent_seconds: int = 0
    file_submission: Optional[FileSubmissionResponse] = None


class AssignmentSubmissionsResponse(BaseModel):
    assignment_id: str
    assignment_title: str
    assignment_type: str = "EXAM"
    due_date: datetime
    total_students: int
    submitted_count: int
    in_progress_count: int
    not_started_count: int
    average_score: float = 0.0
    items: List[AssignmentSubmissionItem]
