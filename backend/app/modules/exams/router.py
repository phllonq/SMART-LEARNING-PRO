import math
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_current_user, require_roles
from app.modules.auth.models import User, UserRole
from app.modules.curriculum.schemas import PaginatedResponse
from app.modules.exams.models import ExamStatus
from app.modules.exams.schemas import (
    ExamCreate, ExamUpdate, ExamSummaryResponse, ExamDetailResponse,
    ExamQuestionAssign, ExamStartResponse, AutosaveAnswerRequest,
    AutosaveAnswerResponse, ExamSubmitResponse, SubmissionSummaryResponse
)
from app.modules.exams.service import (
    create_exam, get_exams, get_exam_by_id, update_exam,
    add_question_to_exam, remove_question_from_exam, publish_exam, archive_exam,
    get_available_exams_for_student, start_exam_attempt, get_attempt_detail,
    autosave_answer, submit_exam_attempt, get_exam_submissions_for_teacher
)

router = APIRouter(prefix="/exams", tags=["Examinations"])


# ==============================================================================
# 1. STUDENT EXAMINATION FLOW
# ==============================================================================
@router.get("/available", response_model=List[Dict[str, Any]])
async def list_available_exams(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List published exams currently available for the authenticated student to take."""
    return await get_available_exams_for_student(db, student=current_user)


@router.post("/{exam_id}/start", response_model=ExamStartResponse)
async def start_exam(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new examination attempt or resume an active one.
    Strict answer confidentiality: Questions snapshot does NOT expose any `is_correct` answers or solution keys.
    """
    attempt, snapshot = await start_exam_attempt(db, exam_id, student=current_user)
    duration = int((attempt.deadline_at - attempt.started_at).total_seconds() // 60) if (attempt.deadline_at and attempt.started_at) else 45
    return ExamStartResponse(
        attempt_id=attempt.id,
        exam_id=attempt.exam_id,
        attempt_number=attempt.attempt_number,
        started_at=attempt.started_at,
        deadline_at=attempt.deadline_at,
        duration_minutes=duration,
        total_questions=len(snapshot),
        questions=snapshot
    )


@router.get("/attempts/{attempt_id}", response_model=Dict[str, Any])
async def get_attempt(
    attempt_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve attempt state and questions snapshot for the student.
    Confidentiality: Answer keys and teacher solutions are stripped from questions snapshot.
    """
    attempt, snapshot = await get_attempt_detail(db, attempt_id, user=current_user)
    
    # Return saved answers map for easy UI population
    saved_answers = {}
    for a in attempt.answers:
        saved_answers[a.question_id] = {
            "selected_option_id": a.selected_option_id,
            "selected_option_ids": a.selected_option_ids_json,
            "answer_text": a.answer_text,
            "is_flagged": a.is_flagged,
            "time_spent_seconds": a.time_spent_seconds
        }

    return {
        "attempt_id": attempt.id,
        "exam_id": attempt.exam_id,
        "status": attempt.status,
        "started_at": attempt.started_at,
        "deadline_at": attempt.deadline_at,
        "time_spent_seconds": attempt.time_spent_seconds,
        "questions": snapshot,
        "saved_answers": saved_answers
    }


@router.put("/attempts/{attempt_id}/answers/{question_id}", response_model=AutosaveAnswerResponse)
async def autosave(
    attempt_id: str,
    question_id: str,
    data: AutosaveAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Autosave student answer in real-time during an active examination attempt.
    Enforces server-side deadline and student ownership.
    """
    answer = await autosave_answer(db, attempt_id, question_id, data, student=current_user)
    return AutosaveAnswerResponse(
        status="SAVED",
        attempt_id=answer.attempt_id,
        question_id=answer.question_id,
        saved_at=answer.answered_at
    )


@router.post("/attempts/{attempt_id}/submit", response_model=ExamSubmitResponse)
async def submit_exam(
    attempt_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Finalize examination submission and trigger server-side automatic grading engine.
    Idempotent: Returns existing result if already submitted.
    """
    return await submit_exam_attempt(db, attempt_id, user=current_user)


# ==============================================================================
# 2. TEACHER & ADMIN MANAGEMENT
# ==============================================================================
@router.post("", response_model=ExamSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_new_exam(
    data: ExamCreate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Create a new examination (Teacher or Admin)."""
    exam = await create_exam(db, data, creator=current_user)
    return ExamSummaryResponse(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        subject_id=exam.subject_id,
        grade_id=exam.grade_id,
        creator_id=exam.creator_id,
        duration_minutes=exam.duration_minutes,
        total_points=exam.total_points,
        passing_points=exam.passing_points,
        max_attempts=exam.max_attempts,
        status=exam.status,
        is_published=exam.is_published,
        start_time=exam.start_time,
        end_time=exam.end_time,
        question_count=len(exam.exam_questions),
        created_at=exam.created_at
    )


@router.get("", response_model=PaginatedResponse[ExamSummaryResponse])
async def list_exams(
    subject_id: Optional[str] = Query(None, description="Lọc theo môn học"),
    grade_id: Optional[int] = Query(None, ge=1, le=12, description="Lọc theo khối lớp"),
    status_filter: Optional[str] = Query(None, description="Lọc theo trạng thái"),
    creator_id: Optional[str] = Query(None, description="Lọc theo giáo viên tạo"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List exams with filtering and pagination."""
    exams, total = await get_exams(
        db=db,
        subject_id=subject_id,
        grade_id=grade_id,
        status_filter=status_filter,
        creator_id=creator_id,
        user=current_user,
        page=page,
        page_size=page_size
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    items = [
        ExamSummaryResponse(
            id=e.id,
            title=e.title,
            description=e.description,
            subject_id=e.subject_id,
            grade_id=e.grade_id,
            creator_id=e.creator_id,
            duration_minutes=e.duration_minutes,
            total_points=e.total_points,
            passing_points=e.passing_points,
            max_attempts=e.max_attempts,
            status=e.status,
            is_published=e.is_published,
            start_time=e.start_time,
            end_time=e.end_time,
            question_count=len(e.exam_questions),
            created_at=e.created_at
        )
        for e in exams
    ]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{exam_id}", response_model=ExamDetailResponse)
async def get_exam_details(
    exam_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get exam details with questions."""
    exam = await get_exam_by_id(db, exam_id, user=current_user)
    is_teacher_or_admin = current_user and current_user.role in [UserRole.TEACHER.value, UserRole.ADMIN.value, UserRole.SUPERADMIN.value]

    questions_data = []
    if is_teacher_or_admin:
        for eq in exam.exam_questions:
            q = eq.question
            questions_data.append({
                "exam_question_id": eq.id,
                "question_id": q.id,
                "points": eq.points,
                "order_index": eq.order_index,
                "content": q.content,
                "question_type": q.question_type,
                "difficulty_level": q.difficulty_level,
                "options_count": len(q.options)
            })

    return ExamDetailResponse(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        subject_id=exam.subject_id,
        grade_id=exam.grade_id,
        creator_id=exam.creator_id,
        duration_minutes=exam.duration_minutes,
        total_points=exam.total_points,
        passing_points=exam.passing_points,
        max_attempts=exam.max_attempts,
        status=exam.status,
        is_published=exam.is_published,
        start_time=exam.start_time,
        end_time=exam.end_time,
        question_count=len(exam.exam_questions),
        created_at=exam.created_at,
        questions=questions_data
    )


@router.patch("/{exam_id}", response_model=ExamSummaryResponse)
async def update_exam_settings(
    exam_id: str,
    data: ExamUpdate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Update exam settings (Teacher ownership / Admin)."""
    exam = await update_exam(db, exam_id, data, user=current_user)
    return ExamSummaryResponse(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        subject_id=exam.subject_id,
        grade_id=exam.grade_id,
        creator_id=exam.creator_id,
        duration_minutes=exam.duration_minutes,
        total_points=exam.total_points,
        passing_points=exam.passing_points,
        max_attempts=exam.max_attempts,
        status=exam.status,
        is_published=exam.is_published,
        start_time=exam.start_time,
        end_time=exam.end_time,
        question_count=len(exam.exam_questions),
        created_at=exam.created_at
    )


@router.post("/{exam_id}/questions", response_model=ExamDetailResponse)
async def add_question(
    exam_id: str,
    assign_data: ExamQuestionAssign,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Add a question from Question Bank into the examination."""
    exam = await add_question_to_exam(db, exam_id, assign_data, user=current_user)
    return await get_exam_details(exam.id, current_user=current_user, db=db)


@router.delete("/{exam_id}/questions/{question_id}", response_model=ExamDetailResponse)
async def remove_question(
    exam_id: str,
    question_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Remove a question from the examination."""
    exam = await remove_question_from_exam(db, exam_id, question_id, user=current_user)
    return await get_exam_details(exam.id, current_user=current_user, db=db)


@router.post("/{exam_id}/publish", response_model=ExamSummaryResponse)
async def publish(
    exam_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Publish the examination so eligible students can take it."""
    exam = await publish_exam(db, exam_id, user=current_user)
    return ExamSummaryResponse(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        subject_id=exam.subject_id,
        grade_id=exam.grade_id,
        creator_id=exam.creator_id,
        duration_minutes=exam.duration_minutes,
        total_points=exam.total_points,
        passing_points=exam.passing_points,
        max_attempts=exam.max_attempts,
        status=exam.status,
        is_published=exam.is_published,
        start_time=exam.start_time,
        end_time=exam.end_time,
        question_count=len(exam.exam_questions),
        created_at=exam.created_at
    )


@router.post("/{exam_id}/archive", response_model=ExamSummaryResponse)
async def archive(
    exam_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Archive an examination."""
    exam = await archive_exam(db, exam_id, user=current_user)
    return ExamSummaryResponse(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        subject_id=exam.subject_id,
        grade_id=exam.grade_id,
        creator_id=exam.creator_id,
        duration_minutes=exam.duration_minutes,
        total_points=exam.total_points,
        passing_points=exam.passing_points,
        max_attempts=exam.max_attempts,
        status=exam.status,
        is_published=exam.is_published,
        start_time=exam.start_time,
        end_time=exam.end_time,
        question_count=len(exam.exam_questions),
        created_at=exam.created_at
    )


@router.get("/{exam_id}/submissions", response_model=List[SubmissionSummaryResponse])
async def list_exam_submissions(
    exam_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """View all student submissions for an exam (Teacher ownership / Admin)."""
    return await get_exam_submissions_for_teacher(db, exam_id, user=current_user)
