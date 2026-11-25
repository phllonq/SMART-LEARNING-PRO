from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, model_validator
from datetime import datetime
from app.modules.questions.models import QuestionType, DifficultyLevel


# --- Question Option Schemas ---
class QuestionOptionBase(BaseModel):
    option_key: str = Field(..., min_length=1, max_length=10, description="e.g. A, B, C, D")
    content: str = Field(..., min_length=1, description="Nội dung phương án (hỗ trợ KaTeX)")
    order_index: int = 0


class QuestionOptionCreate(QuestionOptionBase):
    is_correct: bool = False


class QuestionOptionAdminResponse(QuestionOptionBase):
    id: str
    question_id: str
    is_correct: bool

    model_config = ConfigDict(from_attributes=True)


class QuestionOptionStudentResponse(QuestionOptionBase):
    id: str
    question_id: str
    # STRICT CONFIDENTIALITY: is_correct is NOT included in student response!

    model_config = ConfigDict(from_attributes=True)


# --- Question Schemas ---
class QuestionBase(BaseModel):
    topic_id: Optional[str] = None
    lesson_id: Optional[str] = None
    question_type: QuestionType = QuestionType.SINGLE_CHOICE
    content: str = Field(..., min_length=3, description="Nội dung câu hỏi (hỗ trợ KaTeX)")
    difficulty_level: DifficultyLevel = DifficultyLevel.COMPREHENSION
    explanation: Optional[str] = Field(None, description="Lời giải chi tiết chuẩn")
    hint: Optional[str] = Field(None, description="Gợi ý sư phạm Socratic")
    tags: Optional[str] = Field(None, description="Tags cách nhau bởi dấu phẩy")
    is_public: bool = True


class QuestionCreate(QuestionBase):
    options: List[QuestionOptionCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_options_by_type(self) -> "QuestionCreate":
        q_type = self.question_type
        opts = self.options

        # Option key duplicate check
        keys = [o.option_key.strip().upper() for o in opts]
        if len(keys) != len(set(keys)):
            raise ValueError(f"Các phương án không được trùng mã option_key: {keys}")

        if q_type == QuestionType.SINGLE_CHOICE:
            if len(opts) < 2:
                raise ValueError("Câu hỏi trắc nghiệm một đáp án phải có ít nhất 2 phương án.")
            correct_count = sum(1 for o in opts if o.is_correct)
            if correct_count != 1:
                raise ValueError(f"Câu hỏi trắc nghiệm một đáp án phải có đúng 1 đáp án đúng (hiện có {correct_count}).")

        elif q_type == QuestionType.MULTIPLE_CHOICE:
            if len(opts) < 2:
                raise ValueError("Câu hỏi trắc nghiệm nhiều đáp án phải có ít nhất 2 phương án.")
            correct_count = sum(1 for o in opts if o.is_correct)
            if correct_count < 1:
                raise ValueError("Câu hỏi trắc nghiệm nhiều đáp án phải có ít nhất 1 đáp án đúng.")

        elif q_type == QuestionType.TRUE_FALSE:
            if len(opts) != 2:
                raise ValueError(f"Câu hỏi Đúng/Sai phải có đúng 2 phương án (hiện có {len(opts)}).")
            correct_count = sum(1 for o in opts if o.is_correct)
            if correct_count != 1:
                raise ValueError("Câu hỏi Đúng/Sai phải có đúng 1 đáp án đúng.")

        elif q_type == QuestionType.SHORT_ANSWER:
            if len(opts) < 1:
                raise ValueError("Câu hỏi trả lời ngắn phải có ít nhất 1 đáp án mẫu được chấp nhận.")
            correct_count = sum(1 for o in opts if o.is_correct)
            if correct_count < 1:
                raise ValueError("Câu hỏi trả lời ngắn phải có ít nhất 1 đáp án mẫu được đánh dấu là đúng.")

        return self


class QuestionUpdate(BaseModel):
    topic_id: Optional[str] = None
    lesson_id: Optional[str] = None
    question_type: Optional[QuestionType] = None
    content: Optional[str] = Field(None, min_length=3)
    difficulty_level: Optional[DifficultyLevel] = None
    explanation: Optional[str] = None
    hint: Optional[str] = None
    tags: Optional[str] = None
    is_public: Optional[bool] = None
    options: Optional[List[QuestionOptionCreate]] = None

    @model_validator(mode="after")
    def validate_options_if_provided(self) -> "QuestionUpdate":
        if self.options is not None:
            opts = self.options
            keys = [o.option_key.strip().upper() for o in opts]
            if len(keys) != len(set(keys)):
                raise ValueError(f"Các phương án không được trùng mã option_key: {keys}")
        return self


class QuestionAdminResponse(QuestionBase):
    id: str
    creator_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    options: List[QuestionOptionAdminResponse] = []
    creator_name: Optional[str] = None
    topic_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ImportedQuestionError(BaseModel):
    index: int
    raw_preview: str
    error: str


class QuestionImportResponse(BaseModel):
    dry_run: bool = False
    total_detected: int
    imported_count: int
    failed_count: int
    errors: List[ImportedQuestionError] = []
    questions: List[QuestionAdminResponse] = []
    preview_questions: List[QuestionCreate] = []


class QuestionStudentResponse(BaseModel):
    id: str
    topic_id: Optional[str] = None
    lesson_id: Optional[str] = None
    question_type: str
    content: str
    difficulty_level: str
    tags: Optional[str] = None
    hint: Optional[str] = None
    options: List[QuestionOptionStudentResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ImportedQuestionError(BaseModel):
    index: int
    raw_preview: str
    error: str


class QuestionImportResponse(BaseModel):
    dry_run: bool = False
    total_detected: int
    imported_count: int
    failed_count: int
    errors: List[ImportedQuestionError] = []
    questions: List[QuestionAdminResponse] = []
    preview_questions: List[QuestionCreate] = []
