import json
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from fastapi import UploadFile
from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    EntityNotFoundException,
    PermissionDeniedException,
    DuplicateEntityException
)
from app.core.storage import resolve_storage_path, save_upload_file
from app.modules.auth.models import User, UserRole
from app.modules.classrooms.models import (
    Classroom,
    ClassroomMember,
    Assignment,
    AssignmentFileSubmission,
    ClassroomStatus,
    AssignmentStatus,
    AssignmentType,
    FileSubmissionStatus,
)
from app.modules.classrooms.schemas import (
    ClassroomCreate,
    ClassroomUpdate,
    ClassroomStatisticsResponse,
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentSubmissionsResponse,
    AssignmentSubmissionItem,
    FileSubmissionResponse,
    FileSubmissionGradeRequest,
)
from app.modules.exams.models import (
    Exam,
    ExamAttempt,
    AttemptStatus,
    ExamStatus
)
from app.modules.exams.schemas import ExamSubmitResponse
from app.modules.exams.service import (
    start_exam_attempt,
    submit_exam_attempt,
    ensure_utc
)


# ==============================================================================
# 1. HELPERS & PERMISSIONS
# ==============================================================================

async def generate_unique_classroom_code(db: AsyncSession) -> str:
    """Generate an unpredictable 8-character invite code (e.g., 'SL-9A7K2X')."""
    chars = string.ascii_uppercase + string.digits
    for _ in range(20):
        random_suffix = "".join(secrets.choice(chars) for _ in range(6))
        code = f"SL-{random_suffix}"
        res = await db.execute(select(Classroom.id).where(Classroom.code == code))
        if not res.scalar_one_or_none():
            return code
    # Fallback to uuid hex
    return f"SL-{secrets.token_hex(3).upper()}"


def check_classroom_teacher_access(classroom: Classroom, user: User) -> None:
    """Ensure user is the classroom's teacher or an admin."""
    if user.role in [UserRole.ADMIN.value, UserRole.SUPERADMIN.value]:
        return
    if classroom.teacher_id != user.id:
        raise PermissionDeniedException("Bạn không phải giáo viên phụ trách lớp học này.")


async def verify_classroom_membership(db: AsyncSession, classroom_id: str, student_id: str) -> bool:
    """Check if student is an active member of the classroom."""
    q = select(ClassroomMember.id).where(
        ClassroomMember.classroom_id == classroom_id,
        ClassroomMember.student_id == student_id
    )
    res = await db.execute(q)
    return res.scalar_one_or_none() is not None


# ==============================================================================
# 2. CLASSROOM MANAGEMENT SERVICES
# ==============================================================================

async def create_classroom(db: AsyncSession, data: ClassroomCreate, teacher: User) -> Classroom:
    """Create a new classroom owned by the teacher."""
    if teacher.role not in [UserRole.TEACHER.value, UserRole.ADMIN.value, UserRole.SUPERADMIN.value]:
        raise PermissionDeniedException("Chỉ giáo viên và quản trị viên mới có quyền tạo lớp học.")

    code = await generate_unique_classroom_code(db)
    classroom = Classroom(
        teacher_id=teacher.id,
        name=data.name.strip(),
        code=code,
        grade_id=data.grade_id,
        description=data.description,
        max_students=data.max_students,
        status=ClassroomStatus.ACTIVE.value,
        is_archived=False
    )
    db.add(classroom)
    await db.flush()
    return await get_classroom_by_id(db, classroom.id, user=teacher)


async def get_classroom_by_id(db: AsyncSession, classroom_id: str, user: User) -> Classroom:
    """Retrieve classroom details and verify caller has access."""
    q = (
        select(Classroom)
        .where(Classroom.id == classroom_id)
        .options(
            selectinload(Classroom.teacher),
            selectinload(Classroom.members).selectinload(ClassroomMember.student),
            selectinload(Classroom.assignments)
        )
        .execution_options(populate_existing=True)
    )
    res = await db.execute(q)
    classroom = res.scalar_one_or_none()
    if not classroom:
        raise EntityNotFoundException("Classroom", classroom_id)

    # Authorization Check
    is_admin = user.role in [UserRole.ADMIN.value, UserRole.SUPERADMIN.value]
    is_teacher_owner = (classroom.teacher_id == user.id)
    is_member = any(m.student_id == user.id for m in classroom.members)

    if not (is_admin or is_teacher_owner or is_member):
        raise PermissionDeniedException("Bạn không có quyền truy cập thông tin lớp học này.")

    return classroom


async def list_classrooms(
    db: AsyncSession,
    user: User,
    is_archived: Optional[bool] = None
) -> List[Classroom]:
    """
    List classrooms relevant to the authenticated user:
    - Teacher: created classrooms.
    - Student: joined classrooms.
    - Admin: all classrooms.
    """
    query = (
        select(Classroom)
        .options(
            selectinload(Classroom.teacher),
            selectinload(Classroom.members),
            selectinload(Classroom.assignments)
        )
        .order_by(Classroom.created_at.desc())
    )

    conditions = []
    if is_archived is not None:
        conditions.append(Classroom.is_archived == is_archived)

    if user.role in [UserRole.ADMIN.value, UserRole.SUPERADMIN.value]:
        pass
    elif user.role == UserRole.TEACHER.value:
        conditions.append(Classroom.teacher_id == user.id)
    else:
        # Student: only classrooms where student is a member
        query = query.join(Classroom.members).where(ClassroomMember.student_id == user.id)

    if conditions:
        query = query.where(and_(*conditions))

    result = await db.execute(query)
    return list(result.scalars().all())


async def update_classroom(
    db: AsyncSession,
    classroom_id: str,
    data: ClassroomUpdate,
    user: User
) -> Classroom:
    """Update classroom info (Teacher owner or Admin)."""
    classroom = await get_classroom_by_id(db, classroom_id, user=user)
    check_classroom_teacher_access(classroom, user)

    update_dict = data.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(classroom, k, v)

    classroom.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_classroom_by_id(db, classroom.id, user=user)


async def archive_classroom(db: AsyncSession, classroom_id: str, user: User) -> Classroom:
    """Archive a classroom. Closes new memberships."""
    classroom = await get_classroom_by_id(db, classroom_id, user=user)
    check_classroom_teacher_access(classroom, user)

    classroom.is_archived = True
    classroom.status = ClassroomStatus.ARCHIVED.value
    classroom.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_classroom_by_id(db, classroom.id, user=user)


async def regenerate_classroom_code(db: AsyncSession, classroom_id: str, user: User) -> str:
    """Regenerate unique invite code for classroom."""
    classroom = await get_classroom_by_id(db, classroom_id, user=user)
    check_classroom_teacher_access(classroom, user)

    new_code = await generate_unique_classroom_code(db)
    classroom.code = new_code
    classroom.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return new_code


async def join_classroom_by_code(db: AsyncSession, code: str, student: User) -> Classroom:
    """Student joins a classroom using an invite code."""
    if student.role != UserRole.STUDENT.value:
        raise PermissionDeniedException("Chỉ học sinh mới có thể tham gia lớp học qua mã mời.")

    clean_code = code.strip().upper()
    q = (
        select(Classroom)
        .where(Classroom.code == clean_code)
        .options(selectinload(Classroom.members))
        .execution_options(populate_existing=True)
    )
    res = await db.execute(q)
    classroom = res.scalar_one_or_none()
    if not classroom:
        raise EntityNotFoundException("ClassroomCode", clean_code)

    if classroom.is_archived or classroom.status == ClassroomStatus.ARCHIVED.value:
        raise PermissionDeniedException("Lớp học này đã được lưu trữ và không còn nhận học sinh mới.")

    # Duplicate check
    is_already_member = any(m.student_id == student.id for m in classroom.members)
    if is_already_member:
        raise DuplicateEntityException("Bạn đã là thành viên của lớp học này.")

    # Capacity check (preliminary in-memory check)
    if len(classroom.members) >= classroom.max_students:
        raise PermissionDeniedException(f"Lớp học đã đạt sĩ số tối đa ({classroom.max_students} học sinh).")

    new_member = ClassroomMember(
        classroom_id=classroom.id,
        student_id=student.id,
        joined_at=datetime.now(timezone.utc)
    )
    db.add(new_member)
    classroom.members.append(new_member)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise DuplicateEntityException("Bạn đã là thành viên của lớp học này.")

    # Concurrency capacity enforcement: verify total members in DB after insert
    count_query = select(func.count(ClassroomMember.id)).where(ClassroomMember.classroom_id == classroom.id)
    current_count = (await db.execute(count_query)).scalar_one()
    if current_count > classroom.max_students:
        await db.delete(new_member)
        await db.flush()
        raise PermissionDeniedException(f"Lớp học đã đạt sĩ số tối đa ({classroom.max_students} học sinh).")

    db.expire(classroom, ["members"])

    return await get_classroom_by_id(db, classroom.id, user=student)


async def remove_student_from_classroom(
    db: AsyncSession,
    classroom_id: str,
    student_id: str,
    user: User
) -> bool:
    """Remove a student from classroom (Teacher owner or Admin)."""
    classroom = await get_classroom_by_id(db, classroom_id, user=user)
    check_classroom_teacher_access(classroom, user)

    q = select(ClassroomMember).where(
        ClassroomMember.classroom_id == classroom_id,
        ClassroomMember.student_id == student_id
    )
    res = await db.execute(q)
    member = res.scalar_one_or_none()
    if not member:
        raise EntityNotFoundException("ClassroomMember", student_id)

    await db.delete(member)
    await db.flush()
    return True


async def leave_classroom(db: AsyncSession, classroom_id: str, student: User) -> bool:
    """Student leaves a classroom."""
    q = select(ClassroomMember).where(
        ClassroomMember.classroom_id == classroom_id,
        ClassroomMember.student_id == student.id
    )
    res = await db.execute(q)
    member = res.scalar_one_or_none()
    if not member:
        raise PermissionDeniedException("Bạn không phải thành viên của lớp học này.")

    await db.delete(member)
    await db.flush()
    return True


async def get_classroom_statistics(
    db: AsyncSession,
    classroom_id: str,
    user: User
) -> ClassroomStatisticsResponse:
    """Compute aggregate performance statistics for classroom (Teacher/Admin)."""
    classroom = await get_classroom_by_id(db, classroom_id, user=user)
    check_classroom_teacher_access(classroom, user)

    total_students = len(classroom.members)
    total_assignments = len(classroom.assignments)
    active_assignments = sum(1 for a in classroom.assignments if a.status == AssignmentStatus.PUBLISHED.value)

    # Submissions across all assignments of this classroom
    assignment_ids = [a.id for a in classroom.assignments]
    if not assignment_ids or total_students == 0:
        return ClassroomStatisticsResponse(
            classroom_id=classroom.id,
            name=classroom.name,
            total_students=total_students,
            total_assignments=total_assignments,
            active_assignments=active_assignments,
            total_submissions=0,
            average_score=0.0,
            completion_rate_percentage=0.0
        )

    attempts_query = select(ExamAttempt).where(
        ExamAttempt.assignment_id.in_(assignment_ids),
        ExamAttempt.status.in_([AttemptStatus.SUBMITTED.value, AttemptStatus.AUTO_SUBMITTED.value, AttemptStatus.GRADED.value])
    )
    att_res = await db.execute(attempts_query)
    attempts = list(att_res.scalars().all())

    file_subs_query = select(AssignmentFileSubmission).where(
        AssignmentFileSubmission.assignment_id.in_(assignment_ids)
    )
    file_subs = list((await db.execute(file_subs_query)).scalars().all())

    total_submissions = len(attempts) + len(file_subs)
    scores = [att.score for att in attempts if att.score is not None] + [
        fs.score for fs in file_subs if fs.score is not None
    ]
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    possible_submissions = total_students * total_assignments
    completion_rate = round((total_submissions / possible_submissions) * 100, 1) if possible_submissions > 0 else 0.0

    return ClassroomStatisticsResponse(
        classroom_id=classroom.id,
        name=classroom.name,
        total_students=total_students,
        total_assignments=total_assignments,
        active_assignments=active_assignments,
        total_submissions=total_submissions,
        average_score=avg_score,
        completion_rate_percentage=completion_rate
    )


# ==============================================================================
# 3. HOMEWORK & ASSIGNMENTS SERVICES
# ==============================================================================

async def create_assignment(
    db: AsyncSession,
    classroom_id: str,
    data: AssignmentCreate,
    user: User
) -> Assignment:
    """Create a new homework assignment linked to an existing published Exam."""
    classroom = await get_classroom_by_id(db, classroom_id, user=user)
    check_classroom_teacher_access(classroom, user)

    # Check exam
    ex_res = await db.execute(select(Exam).where(Exam.id == data.exam_id))
    exam = ex_res.scalar_one_or_none()
    if not exam:
        raise EntityNotFoundException("Exam", data.exam_id)

    if exam.status != ExamStatus.PUBLISHED.value and not exam.is_published:
        raise PermissionDeniedException("Chỉ có thể giao bài tập từ đề thi đã xuất bản.")

    if data.open_date and data.due_date:
        if ensure_utc(data.due_date) <= ensure_utc(data.open_date):
            raise PermissionDeniedException("Hạn nộp bài phải sau thời điểm mở bài tập.")

    is_pub = (data.status == AssignmentStatus.PUBLISHED)
    assignment = Assignment(
        classroom_id=classroom.id,
        assignment_type=AssignmentType.EXAM.value,
        exam_id=data.exam_id,
        total_points=exam.total_points,
        title=data.title.strip(),
        description=data.description,
        open_date=data.open_date,
        due_date=data.due_date,
        max_attempts=data.max_attempts,
        allow_late_submission=data.allow_late_submission,
        allow_review=data.allow_review,
        status=data.status.value,
        is_published=is_pub
    )
    db.add(assignment)
    await db.flush()
    return await get_assignment_by_id(db, assignment.id, user=user)


async def create_file_assignment(
    db: AsyncSession,
    classroom_id: str,
    title: str,
    due_date: datetime,
    upload_file: UploadFile,
    user: User,
    description: Optional[str] = None,
    open_date: Optional[datetime] = None,
    allow_late_submission: bool = False,
    total_points: float = 10.0,
    status: AssignmentStatus = AssignmentStatus.PUBLISHED,
) -> Assignment:
    """Create a file-based homework assignment by uploading a file from teacher's computer."""
    classroom = await get_classroom_by_id(db, classroom_id, user=user)
    check_classroom_teacher_access(classroom, user)

    if open_date and due_date:
        if ensure_utc(due_date) <= ensure_utc(open_date):
            raise PermissionDeniedException("Hạn nộp bài phải sau thời điểm mở bài tập.")

    storage_key, safe_name, _, _ = await save_upload_file(
        upload=upload_file,
        subdir=f"assignments/{classroom.id}",
    )

    is_pub = (status == AssignmentStatus.PUBLISHED)
    assignment = Assignment(
        classroom_id=classroom.id,
        assignment_type=AssignmentType.FILE.value,
        exam_id=None,
        attachment_url=storage_key,
        attachment_name=safe_name,
        total_points=total_points,
        title=title.strip(),
        description=description.strip() if description else None,
        open_date=open_date,
        due_date=due_date,
        max_attempts=1,
        allow_late_submission=allow_late_submission,
        allow_review=True,
        status=status.value,
        is_published=is_pub,
    )
    db.add(assignment)
    await db.flush()
    return await get_assignment_by_id(db, assignment.id, user=user)


async def get_assignment_by_id(
    db: AsyncSession,
    assignment_id: str,
    user: User,
    allow_cancelled: bool = False
) -> Assignment:
    """Retrieve assignment and verify access."""
    q = (
        select(Assignment)
        .where(Assignment.id == assignment_id)
        .options(
            selectinload(Assignment.classroom).selectinload(Classroom.members),
            selectinload(Assignment.exam).selectinload(Exam.exam_questions),
            selectinload(Assignment.attempts),
            selectinload(Assignment.file_submissions),
        )
        .execution_options(populate_existing=True)
    )
    res = await db.execute(q)
    assignment = res.scalar_one_or_none()
    if not assignment:
        raise EntityNotFoundException("Assignment", assignment_id)

    classroom = assignment.classroom
    is_admin = user.role in [UserRole.ADMIN.value, UserRole.SUPERADMIN.value]
    is_teacher_owner = (classroom.teacher_id == user.id)
    is_member = any(m.student_id == user.id for m in classroom.members)

    if not (is_admin or is_teacher_owner or is_member):
        raise PermissionDeniedException("Bạn không có quyền truy cập vào bài tập này.")

    # Student cannot view draft/cancelled assignment unless allow_cancelled is True (e.g. submitting active attempt)
    if not (is_admin or is_teacher_owner):
        if not allow_cancelled and (assignment.status != AssignmentStatus.PUBLISHED.value or not assignment.is_published):
            raise PermissionDeniedException("Bài tập này chưa được công bố hoặc đã bị hủy.")

    return assignment


async def list_classroom_assignments(
    db: AsyncSession,
    classroom_id: str,
    user: User
) -> List[Assignment]:
    """List assignments for classroom with student status overlays."""
    classroom = await get_classroom_by_id(db, classroom_id, user=user)

    is_privileged = user.role in [UserRole.ADMIN.value, UserRole.SUPERADMIN.value] or classroom.teacher_id == user.id

    query = (
        select(Assignment)
        .where(Assignment.classroom_id == classroom_id)
        .options(
            selectinload(Assignment.exam).selectinload(Exam.exam_questions),
            selectinload(Assignment.classroom),
            selectinload(Assignment.attempts),
            selectinload(Assignment.file_submissions),
        )
        .order_by(Assignment.due_date.asc())
    )

    if not is_privileged:
        query = query.where(
            Assignment.status == AssignmentStatus.PUBLISHED.value,
            Assignment.is_published == True
        )

    res = await db.execute(query)
    return list(res.scalars().all())


async def update_assignment(
    db: AsyncSession,
    assignment_id: str,
    data: AssignmentUpdate,
    user: User
) -> Assignment:
    """Update assignment details (Teacher owner or Admin)."""
    assignment = await get_assignment_by_id(db, assignment_id, user=user)
    check_classroom_teacher_access(assignment.classroom, user)

    update_dict = data.model_dump(exclude_unset=True)
    if "status" in update_dict and update_dict["status"]:
        val = update_dict["status"]
        assignment.status = val.value if hasattr(val, "value") else str(val)
        assignment.is_published = (assignment.status == AssignmentStatus.PUBLISHED.value)
        del update_dict["status"]

    for k, v in update_dict.items():
        setattr(assignment, k, v)

    assignment.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_assignment_by_id(db, assignment.id, user=user)


async def publish_assignment(db: AsyncSession, assignment_id: str, user: User) -> Assignment:
    """Publish an assignment so students can see and start it."""
    assignment = await get_assignment_by_id(db, assignment_id, user=user)
    check_classroom_teacher_access(assignment.classroom, user)

    assignment.status = AssignmentStatus.PUBLISHED.value
    assignment.is_published = True
    assignment.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_assignment_by_id(db, assignment.id, user=user)


async def cancel_assignment(db: AsyncSession, assignment_id: str, user: User) -> Assignment:
    """Cancel an assignment."""
    assignment = await get_assignment_by_id(db, assignment_id, user=user)
    check_classroom_teacher_access(assignment.classroom, user)

    assignment.status = AssignmentStatus.CANCELLED.value
    assignment.is_published = False
    assignment.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return await get_assignment_by_id(db, assignment.id, user=user)


async def get_assignment_submissions(
    db: AsyncSession,
    assignment_id: str,
    user: User
) -> AssignmentSubmissionsResponse:
    """Retrieve full submission gradebook for an assignment (Teacher owner or Admin)."""
    assignment = await get_assignment_by_id(db, assignment_id, user=user)
    check_classroom_teacher_access(assignment.classroom, user)

    # All students in classroom
    members_q = (
        select(ClassroomMember)
        .where(ClassroomMember.classroom_id == assignment.classroom_id)
        .options(selectinload(ClassroomMember.student))
        .order_by(ClassroomMember.joined_at.asc())
    )
    members_res = await db.execute(members_q)
    members = list(members_res.scalars().all())

    # Handle FILE-based assignment submissions separately
    if assignment.assignment_type == AssignmentType.FILE.value:
        subs_q = select(AssignmentFileSubmission).where(
            AssignmentFileSubmission.assignment_id == assignment_id
        )
        subs = list((await db.execute(subs_q)).scalars().all())
        sub_map = {s.student_id: s for s in subs}

        items = []
        submitted_count = 0
        not_started_count = 0
        scores = []
        max_pts = assignment.total_points or 10.0

        for m in members:
            stu = m.student
            fs = sub_map.get(stu.id)
            if not fs:
                not_started_count += 1
                items.append(
                    AssignmentSubmissionItem(
                        student_id=stu.id,
                        student_name=stu.full_name,
                        student_email=stu.email,
                        status="NOT_STARTED",
                        maximum_score=max_pts,
                    )
                )
            else:
                submitted_count += 1
                if fs.score is not None:
                    scores.append(fs.score)
                is_pass = fs.score is not None and fs.score >= (max_pts * 0.5)
                items.append(
                    AssignmentSubmissionItem(
                        student_id=stu.id,
                        student_name=stu.full_name,
                        student_email=stu.email,
                        status=fs.status,
                        file_submission_id=fs.id,
                        submitted_file_name=fs.file_name,
                        submitted_file_size=fs.file_size,
                        student_note=fs.student_note,
                        teacher_feedback=fs.teacher_feedback,
                        download_url=f"/api/v1/assignments/{assignment.id}/file-submissions/{fs.id}/download",
                        score=fs.score,
                        maximum_score=max_pts,
                        is_passed=is_pass,
                        submitted_at=fs.submitted_at,
                        file_submission=FileSubmissionResponse(
                            id=fs.id,
                            assignment_id=fs.assignment_id,
                            student_id=fs.student_id,
                            file_name=fs.file_name,
                            file_size=fs.file_size,
                            content_type=fs.content_type,
                            student_note=fs.student_note,
                            status=fs.status,
                            score=fs.score,
                            teacher_feedback=fs.teacher_feedback,
                            submitted_at=fs.submitted_at,
                            graded_at=fs.graded_at,
                            download_url=f"/api/v1/assignments/{assignment.id}/file-submissions/{fs.id}/download",
                        ),
                    )
                )

        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        return AssignmentSubmissionsResponse(
            assignment_id=assignment.id,
            assignment_title=assignment.title,
            assignment_type=assignment.assignment_type,
            due_date=assignment.due_date,
            total_students=len(members),
            submitted_count=submitted_count,
            in_progress_count=0,
            not_started_count=not_started_count,
            average_score=avg_score,
            items=items,
        )

    # All attempts for this assignment
    attempts_q = (
        select(ExamAttempt)
        .where(ExamAttempt.assignment_id == assignment_id)
        .options(selectinload(ExamAttempt.result))
        .order_by(ExamAttempt.started_at.desc())
    )
    attempts_res = await db.execute(attempts_q)
    attempts = list(attempts_res.scalars().all())

    # Map student_id -> best / latest attempt
    student_attempts: Dict[str, ExamAttempt] = {}
    for att in attempts:
        if att.student_id not in student_attempts:
            student_attempts[att.student_id] = att

    items = []
    submitted_count = 0
    in_progress_count = 0
    not_started_count = 0
    scores = []

    for m in members:
        stu = m.student
        att = student_attempts.get(stu.id)
        if not att:
            not_started_count += 1
            items.append(AssignmentSubmissionItem(
                student_id=stu.id,
                student_name=stu.full_name,
                student_email=stu.email,
                status="NOT_STARTED",
                attempt_id=None,
                attempt_number=0,
                score=None,
                maximum_score=assignment.exam.total_points if assignment.exam else assignment.total_points,
                is_passed=False,
                started_at=None,
                submitted_at=None,
                time_spent_seconds=0
            ))
        elif att.status == AttemptStatus.IN_PROGRESS.value:
            in_progress_count += 1
            items.append(AssignmentSubmissionItem(
                student_id=stu.id,
                student_name=stu.full_name,
                student_email=stu.email,
                status="IN_PROGRESS",
                attempt_id=att.id,
                attempt_number=att.attempt_number,
                score=None,
                maximum_score=att.maximum_score,
                is_passed=False,
                started_at=att.started_at,
                submitted_at=None,
                time_spent_seconds=att.time_spent_seconds
            ))
        else:
            submitted_count += 1
            score_val = att.score if att.score is not None else (att.result.total_score if att.result else 0.0)
            scores.append(score_val)
            passing = assignment.exam.passing_points if assignment.exam else (assignment.total_points * 0.5)
            is_pass = score_val >= passing
            items.append(AssignmentSubmissionItem(
                student_id=stu.id,
                student_name=stu.full_name,
                student_email=stu.email,
                status=att.status,
                attempt_id=att.id,
                attempt_number=att.attempt_number,
                score=score_val,
                maximum_score=att.maximum_score,
                is_passed=is_pass,
                started_at=att.started_at,
                submitted_at=att.submitted_at,
                time_spent_seconds=att.time_spent_seconds
            ))

    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    return AssignmentSubmissionsResponse(
        assignment_id=assignment.id,
        assignment_title=assignment.title,
        assignment_type=assignment.assignment_type,
        due_date=assignment.due_date,
        total_students=len(members),
        submitted_count=submitted_count,
        in_progress_count=in_progress_count,
        not_started_count=not_started_count,
        average_score=avg_score,
        items=items
    )


# ==============================================================================
# 4. STUDENT ASSIGNMENT WORKFLOW (START, MY-ATTEMPT, SUBMIT, FILE SUBMISSION)
# ==============================================================================

async def start_assignment(
    db: AsyncSession,
    assignment_id: str,
    student: User
) -> Tuple[ExamAttempt, List[Dict[str, Any]]]:
    """
    Student begins or resumes an assignment:
    - Enforces classroom membership.
    - Enforces opening time and server-side due date.
    - Reuses Examination Engine snapshot and attempt tracking.
    """
    assignment = await get_assignment_by_id(db, assignment_id, user=student)
    if assignment.assignment_type == AssignmentType.FILE.value or not assignment.exam_id:
        raise PermissionDeniedException("Bài tập này là dạng nộp tệp đính kèm, không phải bài thi trắc nghiệm trực tuyến.")
    now = datetime.now(timezone.utc)

    # 1. Check membership
    is_member = await verify_classroom_membership(db, assignment.classroom_id, student.id)
    if not is_member:
        raise PermissionDeniedException("Bạn không phải thành viên của lớp học này để làm bài tập.")

    # 2. Check timing
    if assignment.open_date:
        open_utc = ensure_utc(assignment.open_date)
        if open_utc and open_utc > now:
            raise PermissionDeniedException(f"Bài tập chưa mở (Thời điểm mở: {assignment.open_date}).")

    due_utc = ensure_utc(assignment.due_date)
    if due_utc and now > due_utc and not assignment.allow_late_submission:
        raise PermissionDeniedException("Hạn chót nộp bài tập đã qua. Hệ thống không cho phép nộp muộn.")

    # 3. Delegate to Examination Engine with assignment context
    attempt, snapshot = await start_exam_attempt(
        db=db,
        exam_id=assignment.exam_id,
        student=student,
        assignment_id=assignment.id,
        max_attempts_override=assignment.max_attempts,
        deadline_override=assignment.due_date
    )

    return attempt, snapshot


async def get_my_assignment_attempt(
    db: AsyncSession,
    assignment_id: str,
    student: User
) -> Dict[str, Any]:
    """Get active or submitted attempt details for current student."""
    assignment = await get_assignment_by_id(db, assignment_id, user=student)
    if assignment.assignment_type == AssignmentType.FILE.value or not assignment.exam_id:
        raise PermissionDeniedException(detail="Bài tập dạng tệp đính kèm không sử dụng bài thi trực tuyến.")

    q = (
        select(ExamAttempt)
        .where(
            ExamAttempt.assignment_id == assignment_id,
            ExamAttempt.student_id == student.id
        )
        .options(
            selectinload(ExamAttempt.answers),
            selectinload(ExamAttempt.result)
        )
        .order_by(ExamAttempt.started_at.desc())
    )
    res = await db.execute(q)
    attempt = res.scalars().first()

    if not attempt:
        return {
            "assignment_id": assignment_id,
            "status": "NOT_STARTED",
            "attempt": None,
            "saved_answers": {}
        }

    snapshot = json.loads(attempt.questions_snapshot_json or "[]")
    saved_answers = {}
    for a in attempt.answers:
        saved_answers[a.question_id] = {
            "selected_option_id": a.selected_option_id,
            "selected_option_ids": json.loads(a.selected_option_ids_json) if a.selected_option_ids_json else None,
            "answer_text": a.answer_text,
            "is_flagged": a.is_flagged,
            "time_spent_seconds": a.time_spent_seconds
        }

    return {
        "assignment_id": assignment_id,
        "status": attempt.status,
        "attempt_id": attempt.id,
        "attempt_number": attempt.attempt_number,
        "started_at": attempt.started_at,
        "deadline_at": attempt.deadline_at,
        "submitted_at": attempt.submitted_at,
        "score": attempt.score,
        "maximum_score": attempt.maximum_score,
        "questions": snapshot,
        "saved_answers": saved_answers
    }


async def submit_assignment(
    db: AsyncSession,
    assignment_id: str,
    student: User
) -> ExamSubmitResponse:
    """Submit student's active assignment attempt with auto-grading."""
    assignment = await get_assignment_by_id(db, assignment_id, user=student, allow_cancelled=True)
    if assignment.assignment_type == AssignmentType.FILE.value or not assignment.exam_id:
        raise PermissionDeniedException(detail="Bài tập dạng tệp đính kèm cần nộp file qua endpoint /file-submission.")

    # Find the active or most recent in-progress attempt
    q = (
        select(ExamAttempt)
        .where(
            ExamAttempt.assignment_id == assignment_id,
            ExamAttempt.student_id == student.id
        )
        .order_by(ExamAttempt.started_at.desc())
    )
    res = await db.execute(q)
    attempt = res.scalars().first()

    if not attempt:
        raise EntityNotFoundException("AssignmentAttempt", assignment_id)

    now = datetime.now(timezone.utc)
    due_utc = ensure_utc(assignment.due_date)
    is_late = bool(due_utc and now > due_utc)

    # Server-side deadline check
    if is_late and not assignment.allow_late_submission and attempt.status == AttemptStatus.IN_PROGRESS.value:
        # Mark auto-submitted due to deadline passed
        result = await submit_exam_attempt(db, attempt.id, student, auto_submitted=True)
    else:
        result = await submit_exam_attempt(db, attempt.id, student, auto_submitted=False)

    # Enforce assignment-level review policy
    if not assignment.allow_review:
        result.review_allowed = False
        result.question_reviews = None

    return result


async def get_assignment_attachment_path(
    db: AsyncSession,
    assignment_id: str,
    user: User,
) -> Tuple[Path, str]:
    """Authorize user and resolve attachment file path on disk."""
    assignment = await get_assignment_by_id(db, assignment_id, user=user)
    if not assignment.attachment_url:
        raise EntityNotFoundException("AssignmentAttachment", assignment_id)
    file_path = resolve_storage_path(assignment.attachment_url)
    return file_path, (assignment.attachment_name or file_path.name)


async def submit_file_assignment(
    db: AsyncSession,
    assignment_id: str,
    upload_file: UploadFile,
    student: User,
    student_note: Optional[str] = None,
) -> AssignmentFileSubmission:
    """Student uploads a file submission for a FILE-type assignment."""
    if student.role != UserRole.STUDENT.value:
        raise PermissionDeniedException("Chỉ học sinh mới có quyền nộp bài tập.")

    assignment = await get_assignment_by_id(db, assignment_id, user=student)
    if assignment.assignment_type != AssignmentType.FILE.value:
        raise PermissionDeniedException("Bài tập này yêu cầu làm bài trắc nghiệm trực tuyến, không phải nộp tệp.")

    is_member = await verify_classroom_membership(db, assignment.classroom_id, student.id)
    if not is_member:
        raise PermissionDeniedException("Bạn không phải thành viên của lớp học này để nộp bài.")

    now = datetime.now(timezone.utc)
    if assignment.open_date:
        open_utc = ensure_utc(assignment.open_date)
        if open_utc and open_utc > now:
            raise PermissionDeniedException(f"Bài tập chưa mở (Thời điểm mở: {assignment.open_date}).")

    due_utc = ensure_utc(assignment.due_date)
    if due_utc and now > due_utc and not assignment.allow_late_submission:
        raise PermissionDeniedException("Hạn chót nộp bài tập đã qua. Hệ thống không cho phép nộp muộn.")

    storage_key, safe_name, file_size, content_type = await save_upload_file(
        upload=upload_file,
        subdir=f"submissions/{assignment.id}/{student.id}",
    )

    existing_q = select(AssignmentFileSubmission).where(
        AssignmentFileSubmission.assignment_id == assignment.id,
        AssignmentFileSubmission.student_id == student.id,
    )
    existing = (await db.execute(existing_q)).scalar_one_or_none()

    if existing:
        if existing.status == FileSubmissionStatus.GRADED.value:
            raise PermissionDeniedException("Bài nộp của bạn đã được giáo viên chấm điểm và khóa lại.")
        # Clean up old file safely if exists
        try:
            old_path = resolve_storage_path(existing.file_url)
            old_path.unlink(missing_ok=True)
        except Exception:
            pass
        existing.file_url = storage_key
        existing.file_name = safe_name
        existing.file_size = file_size
        existing.content_type = content_type
        existing.student_note = student_note.strip() if student_note else None
        existing.submitted_at = now
        existing.status = FileSubmissionStatus.SUBMITTED.value
        await db.flush()
        await db.refresh(existing)
        return existing

    submission = AssignmentFileSubmission(
        assignment_id=assignment.id,
        student_id=student.id,
        file_url=storage_key,
        file_name=safe_name,
        file_size=file_size,
        content_type=content_type,
        student_note=student_note.strip() if student_note else None,
        status=FileSubmissionStatus.SUBMITTED.value,
        submitted_at=now,
    )
    db.add(submission)
    await db.flush()
    await db.refresh(submission)
    return submission


async def get_file_submission_download_path(
    db: AsyncSession,
    assignment_id: str,
    submission_id: str,
    user: User,
) -> Tuple[Path, str]:
    """Authorize teacher owner/admin or submitting student to download a file submission."""
    assignment = await get_assignment_by_id(db, assignment_id, user=user, allow_cancelled=True)

    sub_q = select(AssignmentFileSubmission).where(
        AssignmentFileSubmission.id == submission_id,
        AssignmentFileSubmission.assignment_id == assignment.id,
    )
    submission = (await db.execute(sub_q)).scalar_one_or_none()
    if not submission:
        raise EntityNotFoundException("AssignmentFileSubmission", submission_id)

    is_admin = user.role in [UserRole.ADMIN.value, UserRole.SUPERADMIN.value]
    is_teacher_owner = (assignment.classroom.teacher_id == user.id)
    is_submitting_student = (submission.student_id == user.id)

    if not (is_admin or is_teacher_owner or is_submitting_student):
        raise PermissionDeniedException("Bạn không có quyền tải tệp bài nộp này.")

    file_path = resolve_storage_path(submission.file_url)
    return file_path, (submission.file_name or file_path.name)


async def grade_file_submission(
    db: AsyncSession,
    assignment_id: str,
    submission_id: str,
    data: FileSubmissionGradeRequest,
    user: User,
) -> AssignmentFileSubmission:
    """Teacher or Admin grades a student's file submission."""
    assignment = await get_assignment_by_id(db, assignment_id, user=user, allow_cancelled=True)
    check_classroom_teacher_access(assignment.classroom, user)

    sub_q = select(AssignmentFileSubmission).where(
        AssignmentFileSubmission.id == submission_id,
        AssignmentFileSubmission.assignment_id == assignment.id,
    )
    submission = (await db.execute(sub_q)).scalar_one_or_none()
    if not submission:
        raise EntityNotFoundException("AssignmentFileSubmission", submission_id)

    max_pts = assignment.total_points or 10.0
    if data.score > max_pts:
        raise PermissionDeniedException(f"Điểm chấm ({data.score}) không được vượt quá thang điểm tối đa ({max_pts}).")

    submission.score = data.score
    submission.teacher_feedback = data.teacher_feedback.strip() if data.teacher_feedback else None
    submission.status = FileSubmissionStatus.GRADED.value
    submission.graded_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(submission)
    return submission
