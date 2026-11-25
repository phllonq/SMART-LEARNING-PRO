import json
import math
from datetime import datetime, timezone
from pathlib import Path as FilePath
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Path, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_optional_current_user, require_roles
from app.modules.auth.models import User, UserRole
from app.modules.classrooms.models import AssignmentStatus
from app.modules.classrooms.schemas import AssignmentCreate
from app.modules.classrooms.service import create_assignment
from app.modules.curriculum.schemas import PaginatedResponse
from app.modules.exams.models import ExamStatus, AttemptStatus
from app.modules.exams.schemas import (
    ExamCreate, ExamUpdate, ExamSummaryResponse, ExamDetailResponse,
    ExamQuestionAssign, ExamStartResponse, AutosaveAnswerRequest,
    AutosaveAnswerResponse, ExamSubmitResponse, SubmissionSummaryResponse,
    ExamImportResponse, DraftQuizQuestion, ExamConvertPreviewResponse,
    ExamConvertConfirmRequest, ExamConvertConfirmResponse,
)
from app.modules.questions.importer import convert_exam_file_to_draft, parse_questions_file
from app.modules.questions.schemas import ImportedQuestionError, QuestionCreate
from app.modules.questions.service import import_questions_bulk
from app.modules.exams.service import (
    create_exam, get_exams, get_exam_by_id, update_exam,
    add_question_to_exam, remove_question_from_exam, publish_exam, archive_exam,
    get_available_exams_for_student, start_exam_attempt, get_attempt_detail,
    autosave_answer, submit_exam_attempt, get_attempt_review, get_exam_submissions_for_teacher,
    ensure_utc
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
        server_time=datetime.now(timezone.utc),
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
    Enforces server-side deadline auto-submission if time expired.
    """
    attempt, snapshot = await get_attempt_detail(db, attempt_id, user=current_user)
    
    # Check server-side deadline: if attempt is IN_PROGRESS and deadline has passed, auto-submit
    now = datetime.now(timezone.utc)
    deadline = ensure_utc(attempt.deadline_at) if attempt.deadline_at else None
    if attempt.status == AttemptStatus.IN_PROGRESS.value and deadline and now > deadline:
        # Check late submission policy if assignment
        allow_late = False
        if attempt.assignment_id and attempt.assignment:
            allow_late = bool(attempt.assignment.allow_late_submission)
        if not allow_late:
            await submit_exam_attempt(db, attempt_id, current_user, auto_submitted=True)
            attempt, snapshot = await get_attempt_detail(db, attempt_id, user=current_user)

    # Return saved answers map for easy UI population
    saved_answers = {}
    for a in attempt.answers:
        opt_ids = None
        if a.selected_option_ids_json:
            try:
                opt_ids = json.loads(a.selected_option_ids_json)
            except Exception:
                opt_ids = []
        saved_answers[a.question_id] = {
            "selected_option_id": a.selected_option_id,
            "selected_option_ids": opt_ids,
            "answer_text": a.answer_text,
            "is_flagged": a.is_flagged,
            "time_spent_seconds": a.time_spent_seconds,
            "version": a.version
        }

    return {
        "attempt_id": attempt.id,
        "exam_id": attempt.exam_id,
        "status": attempt.status,
        "started_at": attempt.started_at,
        "deadline_at": attempt.deadline_at,
        "server_time": now,
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
    Enforces server-side deadline, idempotency, atomic optimistic concurrency control (OCC) and student ownership.
    """
    save_status, answer = await autosave_answer(db, attempt_id, question_id, data, student=current_user)
    opt_ids = None
    if answer.selected_option_ids_json:
        try:
            opt_ids = json.loads(answer.selected_option_ids_json)
        except Exception:
            opt_ids = []
    return AutosaveAnswerResponse(
        status=save_status,
        attempt_id=answer.attempt_id,
        question_id=answer.question_id,
        version=answer.version,
        saved_at=answer.answered_at or datetime.now(timezone.utc),
        selected_option_id=answer.selected_option_id,
        selected_option_ids=opt_ids,
        answer_text=answer.answer_text
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


@router.get("/attempts/{attempt_id}/review", response_model=ExamSubmitResponse)
async def get_attempt_review_endpoint(
    attempt_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve submission review with question explanations, correct answers, and feedback.
    Enforces student ownership and review_allowed flag (or teacher/admin access).
    """
    return await get_attempt_review(db, attempt_id, user=current_user)


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


@router.post("/import", response_model=ExamImportResponse, status_code=status.HTTP_201_CREATED)
async def import_exam_from_file(
    file: UploadFile = File(..., description="Tệp đề thi (.xlsx, .csv, .json, .docx, .txt, .pdf, ảnh)"),
    title: str = Form(..., min_length=3, max_length=255),
    description: Optional[str] = Form(None),
    subject_id: Optional[str] = Form(None),
    grade_id: Optional[int] = Form(None),
    duration_minutes: int = Form(45, ge=5, le=300),
    total_points: float = Form(10.0, ge=1.0, le=100.0),
    passing_points: float = Form(5.0, ge=0.0, le=100.0),
    publish_now: bool = Form(True),
    publish_immediately: Optional[bool] = Form(None),
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a complete online Exam directly from an uploaded file (.xlsx, .csv, .json, .docx, .txt, .pdf, or image when AI is configured).
    Parses and persists questions, creates the exam, and attaches all imported questions.
    """
    raw_bytes = await file.read()
    effective_publish = publish_immediately if publish_immediately is not None else publish_now
    draft_res = await convert_exam_file_to_draft(
        filename=file.filename,
        content=raw_bytes,
        is_public=True,
        use_ai=True,
    )

    valid_questions: List[QuestionCreate] = []
    extra_errors: List[ImportedQuestionError] = [
        ImportedQuestionError(index=e.index, raw_preview=e.raw_preview, error=e.error)
        for e in draft_res.errors
    ]
    for idx, d in enumerate(draft_res.draft_questions, start=1):
        try:
            valid_questions.append(QuestionCreate.model_validate({**d, "is_public": True}))
        except Exception as exc:
            extra_errors.append(
                ImportedQuestionError(
                    index=idx,
                    raw_preview=str(d.get("content", ""))[:120],
                    error=str(exc),
                )
            )

    if not valid_questions:
        err_preview = extra_errors[0].error if extra_errors else "Không có câu hỏi hợp lệ có đáp án đúng trong tệp."
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Không thể tạo đề thi trực tiếp: {err_preview}",
        )

    created_questions = await import_questions_bulk(db, valid_questions, creator=current_user)
    exam_data = ExamCreate(
        title=title.strip(),
        description=description.strip() if description else None,
        subject_id=subject_id or None,
        grade_id=grade_id,
        duration_minutes=duration_minutes,
        total_points=total_points,
        passing_points=passing_points,
        status=ExamStatus.PUBLISHED if effective_publish else ExamStatus.DRAFT,
        question_ids=[q.id for q in created_questions],
    )
    exam = await create_exam(db, exam_data, creator=current_user)

    summary = ExamSummaryResponse(
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
    )
    return ExamImportResponse(
        exam=summary,
        imported_questions_count=len(created_questions),
        failed_count=len(extra_errors),
        errors=extra_errors,
    )


@router.post("/convert-preview", response_model=ExamConvertPreviewResponse)
async def preview_convert_exam_file(
    file: UploadFile = File(..., description="Tệp đề thi cần chuyển thành trắc nghiệm (.docx, .txt, .pdf, ảnh, .xlsx, .csv, .json)"),
    use_ai: bool = Form(True),
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
):
    """
    Parse an uploaded teacher exam file into editable draft multiple-choice questions
    (supports missing answer keys so teacher can review and click A/B/C/D before saving).
    """
    raw_bytes = await file.read()
    draft_res = await convert_exam_file_to_draft(
        filename=file.filename,
        content=raw_bytes,
        is_public=True,
        use_ai=use_ai,
    )
    stem = FilePath(file.filename or "Đề trắc nghiệm").stem
    suggested = stem.replace("_", " ").replace("-", " ").strip() or "Đề trắc nghiệm mới"

    draft_models = [DraftQuizQuestion.model_validate(d) for d in draft_res.draft_questions]
    ready_count = sum(1 for q in draft_models if q.has_correct_answer)
    needs_answer_count = len(draft_models) - ready_count

    return ExamConvertPreviewResponse(
        suggested_title=suggested,
        total_detected=draft_res.total_detected,
        ready_count=ready_count,
        needs_answer_count=needs_answer_count,
        extraction_method=draft_res.extraction_method,
        ai_used=draft_res.ai_used,
        ai_available=draft_res.ai_available,
        draft_questions=draft_models,
        errors=[
            ImportedQuestionError(index=e.index, raw_preview=e.raw_preview, error=e.error)
            for e in draft_res.errors
        ],
    )


@router.post("/convert-confirm", response_model=ExamConvertConfirmResponse, status_code=status.HTTP_201_CREATED)
async def confirm_convert_exam_to_quiz(
    payload: ExamConvertConfirmRequest,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    Persist reviewed quiz questions into Question Bank + create an online Exam,
    and optionally publish an Assignment to a classroom in the same transaction.
    """
    if payload.classroom_id and not payload.due_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cần chọn hạn chót nộp bài (due_date) khi giao trực tiếp cho lớp học.",
        )

    created_questions = await import_questions_bulk(db, payload.questions, creator=current_user)
    should_publish_exam = payload.publish_now or bool(payload.classroom_id)

    exam_data = ExamCreate(
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        subject_id=payload.subject_id or None,
        grade_id=payload.grade_id,
        duration_minutes=payload.duration_minutes,
        total_points=payload.total_points,
        passing_points=payload.passing_points,
        status=ExamStatus.PUBLISHED if should_publish_exam else ExamStatus.DRAFT,
        question_ids=[q.id for q in created_questions],
    )
    exam = await create_exam(db, exam_data, creator=current_user)

    assignment_id: Optional[str] = None
    if payload.classroom_id:
        assignment = await create_assignment(
            db=db,
            classroom_id=payload.classroom_id,
            data=AssignmentCreate(
                exam_id=exam.id,
                title=(payload.assignment_title or payload.title).strip(),
                description=payload.description.strip() if payload.description else None,
                due_date=payload.due_date,
                allow_late_submission=payload.allow_late_submission,
                status=AssignmentStatus.PUBLISHED,
            ),
            user=current_user,
        )
        assignment_id = assignment.id

    summary = ExamSummaryResponse(
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
    )
    return ExamConvertConfirmResponse(
        exam=summary,
        imported_questions_count=len(created_questions),
        assignment_id=assignment_id,
        classroom_id=payload.classroom_id,
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
