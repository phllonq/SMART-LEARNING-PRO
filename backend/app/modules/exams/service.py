import json
import math
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from app.modules.exams.models import Exam, ExamQuestion, ExamAttempt, StudentAnswer, ExamResult, ExamStatus, AttemptStatus
from app.modules.exams.schemas import (
    ExamCreate, ExamUpdate, ExamQuestionAssign, ExamQuestionReorderRequest,
    AutosaveAnswerRequest, ExamSubmitResponse
)
from app.modules.questions.models import Question, QuestionOption, QuestionType
from app.modules.curriculum.models import Subject, Grade
from app.modules.auth.models import User, UserRole
from app.core.exceptions import EntityNotFoundException, PermissionDeniedException


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Helper to ensure datetime is timezone-aware in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def check_exam_ownership(exam: Exam, user: User):
    """Ensure teacher can only modify their own exams, while Admins have override privileges."""
    if user.role in [UserRole.ADMIN.value, UserRole.SUPERADMIN.value]:
        return
    if user.role == UserRole.TEACHER.value:
        if exam.creator_id != user.id:
            raise PermissionDeniedException("Bạn không có quyền quản trị đề thi của giáo viên khác.")
        return
    raise PermissionDeniedException("Thao tác này chỉ dành cho giáo viên hoặc quản trị viên.")


# ==============================================================================
# 1. TEACHER & ADMIN EXAM MANAGEMENT
# ==============================================================================
async def create_exam(db: AsyncSession, data: ExamCreate, creator: User) -> Exam:
    """Create a new examination."""
    exam_dict = data.model_dump(exclude={"question_ids", "status"})
    is_pub = data.status == ExamStatus.PUBLISHED
    
    exam = Exam(
        **exam_dict,
        creator_id=creator.id,
        status=data.status.value,
        is_published=is_pub
    )
    db.add(exam)
    await db.flush()

    # Add questions if provided
    if data.question_ids:
        for idx, q_id in enumerate(data.question_ids):
            # Verify question exists
            q_res = await db.execute(select(Question).where(Question.id == q_id))
            if q_res.scalar_one_or_none():
                eq = ExamQuestion(
                    exam_id=exam.id,
                    question_id=q_id,
                    points=round(exam.total_points / max(1, len(data.question_ids)), 2),
                    order_index=idx + 1
                )
                db.add(eq)
        await db.flush()

    return await get_exam_by_id(db, exam.id, user=creator)


async def get_exams(
    db: AsyncSession,
    subject_id: Optional[str] = None,
    grade_id: Optional[int] = None,
    status_filter: Optional[str] = None,
    creator_id: Optional[str] = None,
    user: Optional[User] = None,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Exam], int]:
    """Retrieve exams list with pagination and access controls."""
    conditions = []
    is_privileged = user and user.role in [UserRole.TEACHER.value, UserRole.ADMIN.value, UserRole.SUPERADMIN.value]

    if not is_privileged:
        # Students & anonymous only see PUBLISHED exams
        conditions.append(Exam.status == ExamStatus.PUBLISHED.value)
        conditions.append(Exam.is_published == True)
    elif status_filter:
        conditions.append(Exam.status == status_filter)

    if subject_id:
        conditions.append(Exam.subject_id == subject_id)
    if grade_id:
        conditions.append(Exam.grade_id == grade_id)
    if creator_id:
        conditions.append(Exam.creator_id == creator_id)

    count_query = select(func.count(Exam.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total = (await db.execute(count_query)).scalar_one()

    query = (
        select(Exam)
        .options(
            selectinload(Exam.exam_questions),
            selectinload(Exam.creator),
            selectinload(Exam.subject)
        )
        .order_by(Exam.created_at.desc())
    )
    if conditions:
        query = query.where(and_(*conditions))

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    exams = list(result.scalars().all())
    return exams, total


async def get_exam_by_id(db: AsyncSession, exam_id: str, user: Optional[User] = None) -> Exam:
    """Retrieve an exam by ID with questions eagerly loaded."""
    query = (
        select(Exam)
        .where(Exam.id == exam_id)
        .options(
            selectinload(Exam.exam_questions).selectinload(ExamQuestion.question).selectinload(Question.options),
            selectinload(Exam.creator),
            selectinload(Exam.subject)
        )
        .execution_options(populate_existing=True)
    )
    result = await db.execute(query)
    exam = result.scalar_one_or_none()
    if not exam:
        raise EntityNotFoundException("Exam", exam_id)

    is_privileged = user and user.role in [UserRole.TEACHER.value, UserRole.ADMIN.value, UserRole.SUPERADMIN.value]
    if exam.status != ExamStatus.PUBLISHED.value and not is_privileged:
        raise EntityNotFoundException("Exam", exam_id)

    return exam


async def update_exam(db: AsyncSession, exam_id: str, data: ExamUpdate, user: User) -> Exam:
    """Update exam configuration."""
    exam = await get_exam_by_id(db, exam_id, user=user)
    check_exam_ownership(exam, user)

    update_dict = data.model_dump(exclude_unset=True)
    if "status" in update_dict:
        val = update_dict["status"]
        exam.status = val.value if hasattr(val, "value") else str(val)
        exam.is_published = (exam.status == ExamStatus.PUBLISHED.value)
        del update_dict["status"]

    for k, v in update_dict.items():
        setattr(exam, k, v)

    await db.flush()
    return await get_exam_by_id(db, exam.id, user=user)


async def add_question_to_exam(db: AsyncSession, exam_id: str, assign_data: ExamQuestionAssign, user: User) -> Exam:
    """Add a question from Question Bank into the examination."""
    exam = await get_exam_by_id(db, exam_id, user=user)
    check_exam_ownership(exam, user)

    # Verify question exists
    q_res = await db.execute(select(Question).where(Question.id == assign_data.question_id))
    q = q_res.scalar_one_or_none()
    if not q:
        raise EntityNotFoundException("Question", assign_data.question_id)

    # Check if already added
    existing = await db.execute(
        select(ExamQuestion).where(
            ExamQuestion.exam_id == exam_id,
            ExamQuestion.question_id == assign_data.question_id
        )
    )
    if existing.scalar_one_or_none():
        raise PermissionDeniedException("Câu hỏi này đã có trong đề thi.")

    order_idx = assign_data.order_index if assign_data.order_index > 0 else len(exam.exam_questions) + 1
    eq = ExamQuestion(
        exam_id=exam_id,
        question_id=assign_data.question_id,
        points=assign_data.points,
        order_index=order_idx,
        question=q
    )
    db.add(eq)
    exam.exam_questions.append(eq)
    await db.flush()
    db.expire(exam, ["exam_questions"])
    return await get_exam_by_id(db, exam_id, user=user)


async def remove_question_from_exam(db: AsyncSession, exam_id: str, question_id: str, user: User) -> Exam:
    """Remove a question from an exam."""
    exam = await get_exam_by_id(db, exam_id, user=user)
    check_exam_ownership(exam, user)

    existing = await db.execute(
        select(ExamQuestion).where(
            ExamQuestion.exam_id == exam_id,
            ExamQuestion.question_id == question_id
        )
    )
    eq = existing.scalar_one_or_none()
    if not eq:
        raise EntityNotFoundException("ExamQuestion", question_id)

    await db.delete(eq)
    if eq in exam.exam_questions:
        exam.exam_questions.remove(eq)
    await db.flush()
    db.expire(exam, ["exam_questions"])
    return await get_exam_by_id(db, exam_id, user=user)


async def publish_exam(db: AsyncSession, exam_id: str, user: User) -> Exam:
    """Publish an exam. Validates that it has at least 1 question."""
    exam = await get_exam_by_id(db, exam_id, user=user)
    check_exam_ownership(exam, user)

    if not exam.exam_questions:
        raise PermissionDeniedException("Không thể xuất bản đề thi chưa có câu hỏi nào. Vui lòng thêm câu hỏi.")

    exam.status = ExamStatus.PUBLISHED.value
    exam.is_published = True
    await db.flush()
    return await get_exam_by_id(db, exam_id, user=user)


async def archive_exam(db: AsyncSession, exam_id: str, user: User) -> Exam:
    """Archive an exam."""
    exam = await get_exam_by_id(db, exam_id, user=user)
    check_exam_ownership(exam, user)

    exam.status = ExamStatus.ARCHIVED.value
    exam.is_published = False
    await db.flush()
    return await get_exam_by_id(db, exam_id, user=user)


# ==============================================================================
# 2. STUDENT EXAMINATION WORKFLOW
# ==============================================================================
async def get_available_exams_for_student(db: AsyncSession, student: User) -> List[Dict[str, Any]]:
    """List published exams currently available for the student to take."""
    now = datetime.now(timezone.utc)
    query = (
        select(Exam)
        .where(
            Exam.status == ExamStatus.PUBLISHED.value,
            Exam.is_published == True
        )
        .options(
            selectinload(Exam.exam_questions),
            selectinload(Exam.subject)
        )
        .order_by(Exam.created_at.desc())
    )
    result = await db.execute(query)
    exams = list(result.scalars().all())

    available = []
    for ex in exams:
        # Check start_time
        if ex.start_time and ensure_utc(ex.start_time) > now:
            continue
        # Check end_time
        if ex.end_time and ensure_utc(ex.end_time) < now:
            continue

        # Count completed attempts by this student
        attempts_cnt_query = select(func.count(ExamAttempt.id)).where(
            ExamAttempt.exam_id == ex.id,
            ExamAttempt.student_id == student.id,
            ExamAttempt.status.in_([AttemptStatus.SUBMITTED.value, AttemptStatus.AUTO_SUBMITTED.value, AttemptStatus.GRADED.value])
        )
        completed_cnt = (await db.execute(attempts_cnt_query)).scalar_one()

        if completed_cnt < ex.max_attempts:
            available.append({
                "id": ex.id,
                "title": ex.title,
                "description": ex.description,
                "subject_name": ex.subject.name if ex.subject else None,
                "duration_minutes": ex.duration_minutes,
                "total_points": ex.total_points,
                "passing_points": ex.passing_points,
                "max_attempts": ex.max_attempts,
                "attempts_taken": completed_cnt,
                "question_count": len(ex.exam_questions),
                "end_time": ex.end_time
            })
    return available


async def start_exam_attempt(
    db: AsyncSession,
    exam_id: str,
    student: User,
    assignment_id: Optional[str] = None,
    max_attempts_override: Optional[int] = None,
    deadline_override: Optional[datetime] = None
) -> Tuple[ExamAttempt, List[Dict[str, Any]]]:
    """
    Start or resume an examination attempt:
    - Verifies eligibility, scheduling window, attempt limit.
    - Prevents duplicate active attempts.
    - Creates immutable questions snapshot decoupled from future Question Bank edits.
    - Strictly sanitizes questions snapshot without answer keys for the student.
    - Reusable for Homework Assignments via assignment_id.
    """
    now = datetime.now(timezone.utc)
    student_id = str(student.id)
    exam = await get_exam_by_id(db, exam_id, user=student)

    if exam.status != ExamStatus.PUBLISHED.value or not exam.is_published:
        raise PermissionDeniedException("Đề thi này chưa được công bố hoặc đã lưu trữ.")

    if not assignment_id:
        if ex_start := ensure_utc(exam.start_time):
            if ex_start > now:
                raise PermissionDeniedException(f"Đề thi chưa đến giờ mở (Mở lúc: {exam.start_time}).")
        if ex_end := ensure_utc(exam.end_time):
            if ex_end < now:
                raise PermissionDeniedException("Đề thi đã hết hạn tham gia.")

    if not exam.exam_questions:
        raise PermissionDeniedException("Đề thi chưa có câu hỏi nào.")

    # 1. Check if there is an existing active IN_PROGRESS attempt
    active_conditions = [
        ExamAttempt.exam_id == exam_id,
        ExamAttempt.student_id == student.id,
        ExamAttempt.status == AttemptStatus.IN_PROGRESS.value
    ]
    if assignment_id:
        active_conditions.append(ExamAttempt.assignment_id == assignment_id)
    else:
        active_conditions.append(ExamAttempt.assignment_id.is_(None))

    active_query = (
        select(ExamAttempt)
        .where(and_(*active_conditions))
        .options(selectinload(ExamAttempt.exam))
    )
    active_res = await db.execute(active_query)
    existing_attempt = active_res.scalar_one_or_none()

    if existing_attempt:
        # Check deadline
        deadline = ensure_utc(existing_attempt.deadline_at)
        if deadline and deadline < now:
            # Expired -> auto-submit and grade
            await submit_exam_attempt(db, existing_attempt.id, student, auto_submitted=True)
        else:
            # Resume existing attempt
            snapshot = json.loads(existing_attempt.questions_snapshot_json or "[]")
            return existing_attempt, snapshot

    # 2. Check attempt limits
    completed_conditions = [
        ExamAttempt.exam_id == exam_id,
        ExamAttempt.student_id == student.id,
        ExamAttempt.status.in_([AttemptStatus.SUBMITTED.value, AttemptStatus.AUTO_SUBMITTED.value, AttemptStatus.GRADED.value])
    ]
    if assignment_id:
        completed_conditions.append(ExamAttempt.assignment_id == assignment_id)
    else:
        completed_conditions.append(ExamAttempt.assignment_id.is_(None))

    completed_query = select(func.count(ExamAttempt.id)).where(and_(*completed_conditions))
    completed_count = (await db.execute(completed_query)).scalar_one()

    max_allowed = max_attempts_override if max_attempts_override is not None else exam.max_attempts
    if completed_count >= max_allowed:
        raise PermissionDeniedException(f"Bạn đã dùng hết số lượt làm bài cho phép ({completed_count}/{max_allowed}).")

    # 3. Create fresh attempt
    started_at = now
    calc_deadline = started_at + timedelta(minutes=exam.duration_minutes)
    if deadline_override:
        dl_utc = ensure_utc(deadline_override)
        deadline_at = min(calc_deadline, dl_utc) if dl_utc else calc_deadline
    else:
        deadline_at = calc_deadline

    # 4. Generate Immutable Snapshot
    eq_list = list(exam.exam_questions)
    if exam.shuffle_questions:
        random.shuffle(eq_list)

    sanitized_snapshot = []
    full_snapshot = []

    for idx, eq in enumerate(eq_list):
        q = eq.question
        opts = list(q.options)
        if exam.shuffle_options:
            random.shuffle(opts)

        # Sanitized options for student (WITHOUT is_correct)
        sanitized_opts = [
            {"id": o.id, "option_key": o.option_key, "content": o.content, "order_index": i + 1}
            for i, o in enumerate(opts)
        ]
        # Full options with answer keys for internal server-side grading
        full_opts = [
            {"id": o.id, "option_key": o.option_key, "content": o.content, "is_correct": o.is_correct, "order_index": i + 1}
            for i, o in enumerate(opts)
        ]

        q_item_sanitized = {
            "question_id": q.id,
            "order_index": idx + 1,
            "points": eq.points,
            "content": q.content,
            "question_type": q.question_type,
            "difficulty_level": q.difficulty_level,
            "hint": q.hint,
            "options": sanitized_opts
        }
        q_item_full = {
            "question_id": q.id,
            "order_index": idx + 1,
            "points": eq.points,
            "content": q.content,
            "question_type": q.question_type,
            "difficulty_level": q.difficulty_level,
            "explanation": q.explanation,
            "options": full_opts
        }
        sanitized_snapshot.append(q_item_sanitized)
        full_snapshot.append(q_item_full)

    attempt = ExamAttempt(
        exam_id=exam.id,
        assignment_id=assignment_id,
        student_id=student.id,
        attempt_number=completed_count + 1,
        status=AttemptStatus.IN_PROGRESS.value,
        started_at=started_at,
        deadline_at=deadline_at,
        maximum_score=exam.total_points,
        questions_snapshot_json=json.dumps(sanitized_snapshot, ensure_ascii=False),
        answer_key_snapshot_json=json.dumps(full_snapshot, ensure_ascii=False)
    )
    db.add(attempt)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Concurrent start race condition: reload the active attempt that won the race
        active_conditions = [
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.student_id == student_id,
            ExamAttempt.status == AttemptStatus.IN_PROGRESS.value
        ]
        if assignment_id:
            active_conditions.append(ExamAttempt.assignment_id == assignment_id)
        else:
            active_conditions.append(ExamAttempt.assignment_id.is_(None))

        active_query = (
            select(ExamAttempt)
            .where(and_(*active_conditions))
            .options(selectinload(ExamAttempt.exam))
        )
        active_res = await db.execute(active_query)
        winning_attempt = active_res.scalar_one_or_none()
        if winning_attempt:
            winning_snapshot = json.loads(winning_attempt.questions_snapshot_json or "[]")
            return winning_attempt, winning_snapshot
        raise

    att_res = await db.execute(
        select(ExamAttempt)
        .where(ExamAttempt.id == attempt.id)
        .options(selectinload(ExamAttempt.exam))
    )
    loaded_attempt = att_res.scalar_one()

    return loaded_attempt, sanitized_snapshot


async def get_attempt_detail(db: AsyncSession, attempt_id: str, user: User) -> Tuple[ExamAttempt, List[Dict[str, Any]]]:
    """Retrieve attempt content. Enforces ownership and answer confidentiality."""
    query = (
        select(ExamAttempt)
        .where(ExamAttempt.id == attempt_id)
        .options(
            selectinload(ExamAttempt.answers),
            selectinload(ExamAttempt.exam),
            selectinload(ExamAttempt.result)
        )
    )
    res = await db.execute(query)
    attempt = res.scalar_one_or_none()
    if not attempt:
        raise EntityNotFoundException("ExamAttempt", attempt_id)

    # Ownership check
    is_owner = (attempt.student_id == user.id)
    is_teacher_or_admin = (user.role in [UserRole.TEACHER.value, UserRole.ADMIN.value, UserRole.SUPERADMIN.value])
    if not is_owner and not is_teacher_or_admin:
        raise PermissionDeniedException("Bạn không có quyền truy cập vào bài thi này.")

    snapshot = json.loads(attempt.questions_snapshot_json or "[]")
    return attempt, snapshot


async def autosave_answer(
    db: AsyncSession,
    attempt_id: str,
    question_id: str,
    data: AutosaveAnswerRequest,
    student: User
) -> StudentAnswer:
    """
    Autosave student answer in real-time:
    - Validates attempt is active and not expired.
    - Validates student ownership.
    - Upserts answer safely.
    """
    attempt, snapshot = await get_attempt_detail(db, attempt_id, user=student)
    if attempt.student_id != student.id:
        raise PermissionDeniedException("Bạn không phải chủ sở hữu của bài thi này.")

    if attempt.status != AttemptStatus.IN_PROGRESS.value:
        raise PermissionDeniedException(f"Bài thi này đã nộp hoặc kết thúc (Trạng thái: {attempt.status}). Không thể lưu thêm đáp án.")

    now = datetime.now(timezone.utc)
    deadline = ensure_utc(attempt.deadline_at)
    if deadline and now > deadline:
        # Auto-submit
        await submit_exam_attempt(db, attempt_id, student, auto_submitted=True)
        raise PermissionDeniedException("Đã hết thời gian làm bài quy định. Bài thi của bạn đã được tự động nộp.")

    # Verify question belongs to this attempt snapshot
    valid_q_ids = [q["question_id"] for q in snapshot]
    if question_id not in valid_q_ids:
        raise EntityNotFoundException("Question in Attempt", question_id)

    # Find existing answer or create new
    existing_query = select(StudentAnswer).where(
        StudentAnswer.attempt_id == attempt_id,
        StudentAnswer.question_id == question_id
    )
    ans_res = await db.execute(existing_query)
    answer = ans_res.scalar_one_or_none()

    opt_ids_json = json.dumps(data.selected_option_ids) if data.selected_option_ids else None

    if not answer:
        answer = StudentAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_option_id=data.selected_option_id,
            selected_option_ids_json=opt_ids_json,
            answer_text=data.answer_text,
            is_flagged=data.is_flagged,
            time_spent_seconds=data.time_spent_seconds,
            answered_at=now
        )
        db.add(answer)
    else:
        # Out-of-order protection: discard delayed packet if time_spent is strictly lower than existing recorded time
        if data.time_spent_seconds < answer.time_spent_seconds:
            return answer

        answer.selected_option_id = data.selected_option_id
        answer.selected_option_ids_json = opt_ids_json
        answer.answer_text = data.answer_text
        answer.is_flagged = data.is_flagged
        answer.time_spent_seconds = data.time_spent_seconds
        answer.answered_at = now
        answer.updated_at = now

    await db.flush()
    await db.refresh(answer)
    return answer


# ==============================================================================
# 3. SERVER-SIDE AUTOMATIC GRADING ENGINE
# ==============================================================================
async def submit_exam_attempt(
    db: AsyncSession,
    attempt_id: str,
    user: User,
    auto_submitted: bool = False
) -> ExamSubmitResponse:
    """
    Server-side submit & grading engine:
    - Idempotent: returns existing result if already submitted.
    - Evaluates SINGLE_CHOICE, MULTIPLE_CHOICE, TRUE_FALSE, SHORT_ANSWER.
    - Server-side calculation of score, percentage, pass/fail.
    - Never trusts client-submitted scores.
    """
    attempt, snapshot = await get_attempt_detail(db, attempt_id, user=user)

    # 1. Idempotency Check: if already graded or submitted, return existing result
    if attempt.status in [AttemptStatus.SUBMITTED.value, AttemptStatus.AUTO_SUBMITTED.value, AttemptStatus.GRADED.value]:
        if attempt.result:
            r = attempt.result
            q_reviews = None
            if attempt.exam.allow_review:
                rev_resp = await get_attempt_review(db, attempt_id, user=user)
                q_reviews = rev_resp.question_reviews

            return ExamSubmitResponse(
                attempt_id=attempt.id,
                exam_id=attempt.exam_id,
                status=attempt.status,
                total_score=r.total_score,
                maximum_score=attempt.maximum_score,
                passing_score=attempt.exam.passing_points,
                is_passed=(r.total_score >= attempt.exam.passing_points),
                correct_answers_count=r.correct_answers_count,
                wrong_answers_count=r.wrong_answers_count,
                skipped_answers_count=r.skipped_answers_count,
                accuracy_percentage=r.accuracy_percentage,
                feedback_summary=r.feedback_summary,
                submitted_at=attempt.submitted_at or attempt.created_at,
                review_allowed=attempt.exam.allow_review,
                question_reviews=q_reviews
            )

    now = datetime.now(timezone.utc)
    attempt.submitted_at = now
    attempt.status = AttemptStatus.AUTO_SUBMITTED.value if auto_submitted else AttemptStatus.SUBMITTED.value

    # Calculate time spent
    started_utc = ensure_utc(attempt.started_at)
    time_spent = int((now - started_utc).total_seconds()) if started_utc else 0
    attempt.time_spent_seconds = max(0, time_spent)

    # 2. Server-side Automatic Grading
    # Decode immutable answer key snapshot if available
    snapshot_keys_map = {}
    if attempt.answer_key_snapshot_json:
        try:
            raw_keys = json.loads(attempt.answer_key_snapshot_json)
            snapshot_keys_map = {item["question_id"]: item for item in raw_keys}
        except Exception:
            snapshot_keys_map = {}

    # For any question not in snapshot_keys_map (e.g. legacy attempts), query DB
    q_ids = [q["question_id"] for q in snapshot]
    missing_q_ids = [qid for qid in q_ids if qid not in snapshot_keys_map]
    db_questions_map = {}
    if missing_q_ids:
        questions_query = (
            select(Question)
            .where(Question.id.in_(missing_q_ids))
            .options(selectinload(Question.options))
        )
        q_res = await db.execute(questions_query)
        db_questions_map = {q.id: q for q in q_res.scalars().all()}

    # Fetch all student answers
    answers_query = select(StudentAnswer).where(StudentAnswer.attempt_id == attempt_id)
    answers_res = await db.execute(answers_query)
    answers_map = {a.question_id: a for a in answers_res.scalars().all()}

    # Points mapping from exam_questions or snapshot
    points_map = {}
    if not snapshot_keys_map:
        eq_query = select(ExamQuestion).where(ExamQuestion.exam_id == attempt.exam_id)
        eq_res = await db.execute(eq_query)
        points_map = {eq.question_id: eq.points for eq in eq_res.scalars().all()}

    total_score = 0.0
    correct_count = 0
    wrong_count = 0
    skipped_count = 0
    question_reviews = []

    for q_item in snapshot:
        qid = q_item["question_id"]
        ans = answers_map.get(qid)
        max_q_points = points_map.get(qid, q_item.get("points", 1.0))

        if qid in snapshot_keys_map:
            snap_q = snapshot_keys_map[qid]
            q_type = snap_q["question_type"]
            q_content = snap_q["content"]
            q_explanation = snap_q.get("explanation")
            max_q_points = snap_q.get("points", max_q_points)
            options = snap_q.get("options", [])

            is_correct = False
            points_awarded = 0.0

            if not ans or (not ans.selected_option_id and not ans.selected_option_ids_json and not ans.answer_text):
                skipped_count += 1
                if ans:
                    ans.is_correct = False
                    ans.points_awarded = 0.0
            else:
                if q_type in [QuestionType.SINGLE_CHOICE.value, QuestionType.TRUE_FALSE.value]:
                    correct_opt = next((o for o in options if o.get("is_correct")), None)
                    if correct_opt and ans.selected_option_id == correct_opt.get("id"):
                        is_correct = True
                        points_awarded = max_q_points
                elif q_type == QuestionType.MULTIPLE_CHOICE.value:
                    correct_opt_ids = {o["id"] for o in options if o.get("is_correct")}
                    student_opt_ids = set()
                    if ans.selected_option_ids_json:
                        try:
                            student_opt_ids = set(json.loads(ans.selected_option_ids_json))
                        except Exception:
                            pass
                    elif ans.selected_option_id:
                        student_opt_ids = {ans.selected_option_id}
                    if student_opt_ids == correct_opt_ids:
                        is_correct = True
                        points_awarded = max_q_points
                elif q_type == QuestionType.SHORT_ANSWER.value:
                    correct_opts_texts = {o["content"].strip().lower() for o in options if o.get("is_correct")}
                    student_text = (ans.answer_text or "").strip().lower()
                    if student_text in correct_opts_texts:
                        is_correct = True
                        points_awarded = max_q_points

                if is_correct:
                    correct_count += 1
                else:
                    wrong_count += 1

                ans.is_correct = is_correct
                ans.points_awarded = points_awarded
                total_score += points_awarded

            if attempt.exam.allow_review:
                correct_keys = [o["option_key"] for o in options if o.get("is_correct")]
                question_reviews.append({
                    "question_id": qid,
                    "content": q_content,
                    "is_correct": is_correct,
                    "points_awarded": points_awarded,
                    "max_points": max_q_points,
                    "correct_option_keys": correct_keys,
                    "explanation": q_explanation
                })

        elif qid in db_questions_map:
            question = db_questions_map[qid]
            q_type = question.question_type
            is_correct = False
            points_awarded = 0.0

            if not ans or (not ans.selected_option_id and not ans.selected_option_ids_json and not ans.answer_text):
                # Skipped question
                skipped_count += 1
                if ans:
                    ans.is_correct = False
                    ans.points_awarded = 0.0
            else:
                # Evaluate based on Question Type
                if q_type in [QuestionType.SINGLE_CHOICE.value, QuestionType.TRUE_FALSE.value]:
                    correct_opt = next((o for o in question.options if o.is_correct), None)
                    if correct_opt and ans.selected_option_id == correct_opt.id:
                        is_correct = True
                        points_awarded = max_q_points
                    else:
                        is_correct = False
                        points_awarded = 0.0

                elif q_type == QuestionType.MULTIPLE_CHOICE.value:
                    correct_opt_ids = {o.id for o in question.options if o.is_correct}
                    student_opt_ids = set()
                    if ans.selected_option_ids_json:
                        try:
                            student_opt_ids = set(json.loads(ans.selected_option_ids_json))
                        except Exception:
                            pass
                    elif ans.selected_option_id:
                        student_opt_ids = {ans.selected_option_id}

                    if student_opt_ids == correct_opt_ids:
                        is_correct = True
                        points_awarded = max_q_points
                    else:
                        is_correct = False
                        points_awarded = 0.0

                elif q_type == QuestionType.SHORT_ANSWER.value:
                    # Deterministic normalized comparison with explanation / correct options
                    correct_opts_texts = {o.content.strip().lower() for o in question.options if o.is_correct}
                    student_text = (ans.answer_text or "").strip().lower()
                    if student_text in correct_opts_texts:
                        is_correct = True
                        points_awarded = max_q_points
                    else:
                        is_correct = False
                        points_awarded = 0.0

                if is_correct:
                    correct_count += 1
                else:
                    wrong_count += 1

                ans.is_correct = is_correct
                ans.points_awarded = points_awarded
                total_score += points_awarded

            if attempt.exam.allow_review:
                correct_keys = [o.option_key for o in question.options if o.is_correct]
                question_reviews.append({
                    "question_id": qid,
                    "content": question.content,
                    "is_correct": is_correct,
                    "points_awarded": points_awarded,
                    "max_points": max_q_points,
                    "correct_option_keys": correct_keys,
                    "explanation": question.explanation
                })

    # Total questions
    total_q = len(snapshot)
    accuracy = round((correct_count / max(1, total_q)) * 100.0, 1)
    total_score = round(total_score, 2)
    is_passed = (total_score >= attempt.exam.passing_points)

    # 3. Create or update ExamResult
    existing_result_res = await db.execute(select(ExamResult).where(ExamResult.attempt_id == attempt.id))
    exam_result = existing_result_res.scalar_one_or_none()
    feedback = f"Bạn đã hoàn thành bài thi với {correct_count}/{total_q} câu đúng. " + ("Đạt yêu cầu!" if is_passed else "Chưa đạt yêu cầu, hãy ôn tập thêm nhé!")

    if not exam_result:
        exam_result = ExamResult(
            attempt_id=attempt.id,
            total_score=total_score,
            correct_answers_count=correct_count,
            wrong_answers_count=wrong_count,
            skipped_answers_count=skipped_count,
            accuracy_percentage=accuracy,
            feedback_summary=feedback
        )
        db.add(exam_result)
    else:
        exam_result.total_score = total_score
        exam_result.correct_answers_count = correct_count
        exam_result.wrong_answers_count = wrong_count
        exam_result.skipped_answers_count = skipped_count
        exam_result.accuracy_percentage = accuracy
        exam_result.feedback_summary = feedback

    attempt.score = total_score
    attempt.status = AttemptStatus.GRADED.value

    # Gamification: award XP to student
    student_query = select(User).where(User.id == attempt.student_id)
    student_res = await db.execute(student_query)
    stu_user = student_res.scalar_one_or_none()
    if stu_user:
        xp_gain = int(total_score * 10) + (50 if is_passed else 20)
        stu_user.xp_points += xp_gain
        stu_user.current_level = 1 + (stu_user.xp_points // 200)

    try:
        await db.flush()
        await db.refresh(attempt)
    except IntegrityError:
        await db.rollback()
        # Another concurrent submission flushed first, re-call submit_exam_attempt to return cached result
        return await submit_exam_attempt(db, attempt_id, user, auto_submitted)

    return ExamSubmitResponse(
        attempt_id=attempt.id,
        exam_id=attempt.exam_id,
        status=attempt.status,
        total_score=total_score,
        maximum_score=attempt.maximum_score,
        passing_score=attempt.exam.passing_points,
        is_passed=is_passed,
        correct_answers_count=correct_count,
        wrong_answers_count=wrong_count,
        skipped_answers_count=skipped_count,
        accuracy_percentage=accuracy,
        feedback_summary=feedback,
        submitted_at=now,
        review_allowed=attempt.exam.allow_review,
        question_reviews=question_reviews if attempt.exam.allow_review else None
    )


async def get_attempt_review(
    db: AsyncSession,
    attempt_id: str,
    user: User
) -> ExamSubmitResponse:
    """
    Retrieve completed examination attempt review.
    Enforces review permission and returns full question breakdown.
    """
    attempt, snapshot = await get_attempt_detail(db, attempt_id, user=user)

    if attempt.status not in [AttemptStatus.SUBMITTED.value, AttemptStatus.AUTO_SUBMITTED.value, AttemptStatus.GRADED.value]:
        raise PermissionDeniedException("Bài thi chưa được nộp. Không thể xem lại đáp án.")

    is_privileged = user.role in [UserRole.TEACHER.value, UserRole.ADMIN.value, UserRole.SUPERADMIN.value]
    if not is_privileged and not attempt.exam.allow_review:
        raise PermissionDeniedException("Đề thi này không cho phép xem lại bài làm.")

    # Fetch answers
    answers_query = select(StudentAnswer).where(StudentAnswer.attempt_id == attempt_id)
    answers_res = await db.execute(answers_query)
    answers_map = {a.question_id: a for a in answers_res.scalars().all()}

    # Check for snapshot keys
    snapshot_keys_map = {}
    if attempt.answer_key_snapshot_json:
        try:
            raw_keys = json.loads(attempt.answer_key_snapshot_json)
            snapshot_keys_map = {item["question_id"]: item for item in raw_keys}
        except Exception:
            snapshot_keys_map = {}

    missing_qids = [q["question_id"] for q in snapshot if q["question_id"] not in snapshot_keys_map]
    db_questions_map = {}
    if missing_qids:
        q_res = await db.execute(
            select(Question).where(Question.id.in_(missing_qids)).options(selectinload(Question.options))
        )
        db_questions_map = {q.id: q for q in q_res.scalars().all()}

    question_reviews = []
    for q_item in snapshot:
        qid = q_item["question_id"]
        ans = answers_map.get(qid)
        max_q_points = q_item.get("points", 1.0)
        is_correct = ans.is_correct if ans else False
        points_awarded = ans.points_awarded if ans else 0.0

        if qid in snapshot_keys_map:
            snap_q = snapshot_keys_map[qid]
            opts = snap_q.get("options", [])
            correct_keys = [o["option_key"] for o in opts if o.get("is_correct")]
            explanation = snap_q.get("explanation")
            content = snap_q.get("content", q_item.get("content", ""))
            max_q_points = snap_q.get("points", max_q_points)
        elif qid in db_questions_map:
            q = db_questions_map[qid]
            correct_keys = [o.option_key for o in q.options if o.is_correct]
            explanation = q.explanation
            content = q.content
        else:
            correct_keys = []
            explanation = None
            content = q_item.get("content", "")

        question_reviews.append({
            "question_id": qid,
            "content": content,
            "is_correct": is_correct,
            "points_awarded": points_awarded,
            "max_points": max_q_points,
            "correct_option_keys": correct_keys,
            "explanation": explanation
        })

    r = attempt.result
    total_score = attempt.score if attempt.score is not None else (r.total_score if r else 0.0)
    correct_cnt = r.correct_answers_count if r else 0
    wrong_cnt = r.wrong_answers_count if r else 0
    skipped_cnt = r.skipped_answers_count if r else 0
    accuracy = r.accuracy_percentage if r else 0.0
    feedback = r.feedback_summary if r else None

    return ExamSubmitResponse(
        attempt_id=attempt.id,
        exam_id=attempt.exam_id,
        status=attempt.status,
        total_score=total_score,
        maximum_score=attempt.maximum_score,
        passing_score=attempt.exam.passing_points,
        is_passed=(total_score >= attempt.exam.passing_points),
        correct_answers_count=correct_cnt,
        wrong_answers_count=wrong_cnt,
        skipped_answers_count=skipped_cnt,
        accuracy_percentage=accuracy,
        feedback_summary=feedback,
        submitted_at=attempt.submitted_at or attempt.created_at,
        review_allowed=True,
        question_reviews=question_reviews
    )


async def get_exam_submissions_for_teacher(db: AsyncSession, exam_id: str, user: User) -> List[Dict[str, Any]]:
    """Retrieve all student submissions for an examination (Teacher / Admin only)."""
    exam = await get_exam_by_id(db, exam_id, user=user)
    check_exam_ownership(exam, user)

    query = (
        select(ExamAttempt)
        .where(
            ExamAttempt.exam_id == exam_id,
            ExamAttempt.status.in_([AttemptStatus.SUBMITTED.value, AttemptStatus.AUTO_SUBMITTED.value, AttemptStatus.GRADED.value])
        )
        .options(
            selectinload(ExamAttempt.student),
            selectinload(ExamAttempt.result)
        )
        .order_by(ExamAttempt.submitted_at.desc())
    )
    result = await db.execute(query)
    attempts = list(result.scalars().all())

    submissions = []
    for att in attempts:
        score_val = att.score or (att.result.total_score if att.result else 0.0)
        submissions.append({
            "attempt_id": att.id,
            "student_id": att.student_id,
            "student_name": att.student.full_name if att.student else "Học sinh",
            "attempt_number": att.attempt_number,
            "status": att.status,
            "started_at": att.started_at,
            "submitted_at": att.submitted_at,
            "score": score_val,
            "maximum_score": att.maximum_score,
            "is_passed": bool(score_val >= exam.passing_points),
            "time_spent_seconds": att.time_spent_seconds
        })
    return submissions
