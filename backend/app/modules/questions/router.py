import math
from typing import Optional, List, Union
from fastapi import APIRouter, Depends, File, Form, Query, Path, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_current_user, require_roles
from app.modules.auth.models import User, UserRole
from app.modules.curriculum.schemas import PaginatedResponse
from app.modules.questions.models import QuestionType, DifficultyLevel
from app.modules.questions.schemas import (
    QuestionCreate, QuestionUpdate,
    QuestionAdminResponse, QuestionStudentResponse,
    QuestionOptionAdminResponse, QuestionOptionStudentResponse,
    ImportedQuestionError, QuestionImportResponse,
)
from app.modules.questions.service import (
    get_questions, get_question_by_id,
    create_question, update_question,
    delete_question, toggle_question_publish,
    import_questions_bulk,
)
from app.modules.questions.importer import parse_questions_file

router = APIRouter(prefix="/questions", tags=["Question Bank"])


def is_privileged_user(user: Optional[User]) -> bool:
    """Check if the requesting user has teacher or admin privileges."""
    return bool(user and user.role in [UserRole.TEACHER.value, UserRole.ADMIN.value, UserRole.SUPERADMIN.value])


def format_question_response(q, privileged: bool) -> Union[QuestionAdminResponse, QuestionStudentResponse]:
    """Format question response based on role to strictly preserve answer confidentiality for students."""
    if privileged:
        return QuestionAdminResponse(
            id=q.id,
            topic_id=q.topic_id,
            lesson_id=q.lesson_id,
            creator_id=q.creator_id,
            question_type=q.question_type,
            content=q.content,
            difficulty_level=q.difficulty_level,
            explanation=q.explanation,
            hint=q.hint,
            tags=q.tags,
            is_public=q.is_public,
            created_at=q.created_at,
            updated_at=q.updated_at,
            options=[QuestionOptionAdminResponse.model_validate(o) for o in q.options],
            creator_name=q.creator.full_name if q.creator else None,
            topic_title=q.topic.title if q.topic else None
        )
    else:
        # Student or anonymous: STRICT ANSWER CONFIDENTIALITY
        return QuestionStudentResponse(
            id=q.id,
            topic_id=q.topic_id,
            lesson_id=q.lesson_id,
            question_type=q.question_type,
            content=q.content,
            difficulty_level=q.difficulty_level,
            tags=q.tags,
            hint=q.hint,
            options=[QuestionOptionStudentResponse.model_validate(o) for o in q.options]
        )


@router.get("", response_model=PaginatedResponse[Union[QuestionAdminResponse, QuestionStudentResponse]])
async def list_questions(
    grade_id: Optional[int] = Query(None, ge=1, le=12, description="Lọc theo khối lớp"),
    subject_id: Optional[str] = Query(None, description="Lọc theo mã môn học"),
    chapter_id: Optional[str] = Query(None, description="Lọc theo chương"),
    topic_id: Optional[str] = Query(None, description="Lọc theo chủ đề"),
    lesson_id: Optional[str] = Query(None, description="Lọc theo bài học"),
    difficulty_level: Optional[DifficultyLevel] = Query(None, description="Độ khó"),
    question_type: Optional[QuestionType] = Query(None, description="Dạng câu hỏi"),
    creator_id: Optional[str] = Query(None, description="Lọc theo tác giả"),
    is_public: Optional[bool] = Query(None, description="Trạng thái xuất bản (chỉ dành cho Giáo viên/Admin)"),
    search: Optional[str] = Query(None, description="Tìm kiếm trong nội dung hoặc thẻ tags"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List questions with extensive filtering and pagination.
    Confidentiality: Students receive questions without `is_correct` answers or official explanations.
    """
    privileged = is_privileged_user(current_user)

    questions, total = await get_questions(
        db=db,
        grade_id=grade_id,
        subject_id=subject_id,
        chapter_id=chapter_id,
        topic_id=topic_id,
        lesson_id=lesson_id,
        difficulty_level=difficulty_level.value if difficulty_level else None,
        question_type=question_type.value if question_type else None,
        creator_id=creator_id,
        is_public=is_public,
        search=search,
        user=current_user,
        page=page,
        page_size=page_size
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0
    items = [format_question_response(q, privileged=privileged) for q in questions]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{question_id}", response_model=Union[QuestionAdminResponse, QuestionStudentResponse])
async def get_single_question(
    question_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve single question details.
    Confidentiality: Students receive question data without `is_correct` keys.
    """
    privileged = is_privileged_user(current_user)
    question = await get_question_by_id(db, question_id, user=current_user)
    return format_question_response(question, privileged=privileged)


@router.post("", response_model=QuestionAdminResponse, status_code=status.HTTP_201_CREATED)
async def create_new_question(
    data: QuestionCreate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new question with multiple-choice / true-false / short-answer options.
    RBAC: Teachers and Administrators only.
    """
    question = await create_question(db, data, creator=current_user)
    return format_question_response(question, privileged=True)


@router.patch("/{question_id}", response_model=QuestionAdminResponse)
async def update_existing_question(
    question_id: str,
    data: QuestionUpdate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing question.
    Ownership: Teachers may only update their own questions. Administrators can update any question.
    """
    question = await update_question(db, question_id, data, user=current_user)
    return format_question_response(question, privileged=True)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_question(
    question_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a question from the question bank.
    Ownership: Teachers may only delete their own questions. Administrators can delete any question.
    """
    await delete_question(db, question_id, user=current_user)
    return None


@router.post("/{question_id}/toggle-publish", response_model=QuestionAdminResponse)
async def toggle_publish(
    question_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Toggle between published (public) and draft states."""
    question = await toggle_question_publish(db, question_id, user=current_user)
    return format_question_response(question, privileged=True)


@router.get("/import-template/csv")
async def download_question_import_template(
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
):
    """Download a UTF-8 BOM CSV template for bulk question import."""
    csv_template = (
        "\ufeff"
        "content,question_type,difficulty_level,option_a,option_b,option_c,option_d,correct,explanation,hint,tags\n"
        "\"Giải phương trình $x^2 - 4 = 0$.\",SINGLE_CHOICE,RECOGNITION,\"x = 2\",\"x = -2\",\"x = 2 hoặc x = -2\",\"Vô nghiệm\",C,\"Ta có $x^2 = 4 \\Rightarrow x = \\pm 2$.\",\"Chuyển vế và lấy căn bậc hai\",\"toan,dai so\"\n"
        "\"Đạo hàm của $f(x) = x^3$ là:\",SINGLE_CHOICE,COMPREHENSION,\"$3x^2$\",\"$x^2$\",\"$3x$\",\"$x^3$\",A,\"Áp dụng công thức $(x^n)' = n x^{n-1}$.\",\"Dùng quy tắc lũy thừa\",\"giai tich,dao ham\"\n"
    )
    return Response(
        content=csv_template.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="smart_learning_question_template.csv"'},
    )


@router.post("/import", response_model=QuestionImportResponse, status_code=status.HTTP_200_OK)
async def import_questions_from_file(
    file: UploadFile = File(..., description="Tệp câu hỏi (.xlsx, .csv, .json, .docx)"),
    topic_id: Optional[str] = Form(None),
    lesson_id: Optional[str] = Form(None),
    is_public: bool = Form(True),
    dry_run: bool = Form(False),
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Parse and import questions from teacher's local .xlsx, .csv, .json, or .docx file.
    Supports `dry_run=true` to preview and validate before persisting.
    """
    raw_bytes = await file.read()
    parsed = parse_questions_file(
        filename=file.filename,
        content=raw_bytes,
        topic_id=topic_id or None,
        lesson_id=lesson_id or None,
        is_public=is_public,
    )

    err_items = [
        ImportedQuestionError(index=e.index, raw_preview=e.raw_preview, error=e.error)
        for e in parsed.errors
    ]

    if dry_run:
        return QuestionImportResponse(
            dry_run=True,
            total_detected=parsed.total_detected,
            imported_count=0,
            failed_count=len(err_items),
            errors=err_items,
            questions=[],
            preview_questions=parsed.valid_questions,
        )

    created = await import_questions_bulk(db, parsed.valid_questions, creator=current_user)
    return QuestionImportResponse(
        dry_run=False,
        total_detected=parsed.total_detected,
        imported_count=len(created),
        failed_count=len(err_items),
        errors=err_items,
        questions=[format_question_response(q, privileged=True) for q in created],
        preview_questions=[],
    )
