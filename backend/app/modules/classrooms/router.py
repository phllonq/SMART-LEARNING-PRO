from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.modules.auth.models import User, UserRole
from app.modules.classrooms.schemas import (
    ClassroomCreate,
    ClassroomUpdate,
    ClassroomJoinRequest,
    ClassroomSummaryResponse,
    ClassroomDetailResponse,
    ClassroomMemberResponse,
    ClassroomStatisticsResponse,
    AssignmentCreate,
    AssignmentUpdate,
    AssignmentSummaryResponse,
    AssignmentSubmissionsResponse
)
from app.modules.classrooms.service import (
    create_classroom,
    get_classroom_by_id,
    list_classrooms,
    update_classroom,
    archive_classroom,
    regenerate_classroom_code,
    join_classroom_by_code,
    remove_student_from_classroom,
    leave_classroom,
    get_classroom_statistics,
    create_assignment,
    get_assignment_by_id,
    list_classroom_assignments,
    update_assignment,
    publish_assignment,
    cancel_assignment,
    get_assignment_submissions,
    start_assignment,
    get_my_assignment_attempt,
    submit_assignment
)
from app.modules.exams.schemas import ExamStartResponse, ExamSubmitResponse


# ==============================================================================
# ROUTERS
# ==============================================================================

classrooms_router = APIRouter(prefix="/classrooms", tags=["Classrooms"])
assignments_router = APIRouter(prefix="/assignments", tags=["Assignments"])


# ==============================================================================
# CLASSROOM ENDPOINTS
# ==============================================================================

@classrooms_router.get("", response_model=List[ClassroomSummaryResponse])
async def get_classrooms(
    is_archived: Optional[bool] = Query(None, description="Lọc theo trạng thái lưu trữ"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List classrooms relevant to the authenticated user:
    - Teacher: Classes owned by this teacher.
    - Student: Classes joined by this student.
    - Admin: All system classrooms.
    """
    classes = await list_classrooms(db, user=current_user, is_archived=is_archived)
    return [
        ClassroomSummaryResponse(
            id=c.id,
            name=c.name,
            code=c.code,
            grade_id=c.grade_id,
            teacher_id=c.teacher_id,
            teacher_name=c.teacher.full_name if c.teacher else None,
            description=c.description,
            status=c.status,
            is_archived=c.is_archived,
            max_students=c.max_students,
            member_count=len(c.members),
            assignment_count=len(c.assignments),
            created_at=c.created_at,
            updated_at=c.updated_at
        )
        for c in classes
    ]


@classrooms_router.post("", response_model=ClassroomSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_new_classroom(
    data: ClassroomCreate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Create a new classroom (Teacher / Admin). Auto-generates unique invite code."""
    c = await create_classroom(db, data, teacher=current_user)
    return ClassroomSummaryResponse(
        id=c.id,
        name=c.name,
        code=c.code,
        grade_id=c.grade_id,
        teacher_id=c.teacher_id,
        teacher_name=current_user.full_name,
        description=c.description,
        status=c.status,
        is_archived=c.is_archived,
        max_students=c.max_students,
        member_count=len(c.members),
        assignment_count=len(c.assignments),
        created_at=c.created_at,
        updated_at=c.updated_at
    )


@classrooms_router.post("/join", response_model=ClassroomSummaryResponse)
async def join_classroom(
    data: ClassroomJoinRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Student joins a classroom using unique invite code."""
    c = await join_classroom_by_code(db, code=data.code, student=current_user)
    return ClassroomSummaryResponse(
        id=c.id,
        name=c.name,
        code=c.code,
        grade_id=c.grade_id,
        teacher_id=c.teacher_id,
        teacher_name=c.teacher.full_name if c.teacher else None,
        description=c.description,
        status=c.status,
        is_archived=c.is_archived,
        max_students=c.max_students,
        member_count=len(c.members),
        assignment_count=len(c.assignments),
        created_at=c.created_at,
        updated_at=c.updated_at
    )


@classrooms_router.get("/{classroom_id}", response_model=ClassroomDetailResponse)
async def get_classroom_detail(
    classroom_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve classroom details and member roster (Teacher owner, Admin, or Member)."""
    c = await get_classroom_by_id(db, classroom_id, user=current_user)
    members_data = [
        ClassroomMemberResponse(
            id=m.id,
            student_id=m.student_id,
            student_name=m.student.full_name if m.student else "Học sinh",
            student_email=m.student.email if m.student else "",
            student_avatar=m.student.avatar_url if m.student else None,
            joined_at=m.joined_at
        )
        for m in c.members
    ]
    return ClassroomDetailResponse(
        id=c.id,
        name=c.name,
        code=c.code,
        grade_id=c.grade_id,
        teacher_id=c.teacher_id,
        teacher_name=c.teacher.full_name if c.teacher else None,
        description=c.description,
        status=c.status,
        is_archived=c.is_archived,
        max_students=c.max_students,
        member_count=len(c.members),
        assignment_count=len(c.assignments),
        created_at=c.created_at,
        updated_at=c.updated_at,
        members=members_data
    )


@classrooms_router.patch("/{classroom_id}", response_model=ClassroomSummaryResponse)
async def update_classroom_info(
    classroom_id: str,
    data: ClassroomUpdate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Update classroom info (Teacher owner or Admin)."""
    c = await update_classroom(db, classroom_id, data, user=current_user)
    return ClassroomSummaryResponse(
        id=c.id,
        name=c.name,
        code=c.code,
        grade_id=c.grade_id,
        teacher_id=c.teacher_id,
        teacher_name=c.teacher.full_name if c.teacher else None,
        description=c.description,
        status=c.status,
        is_archived=c.is_archived,
        max_students=c.max_students,
        member_count=len(c.members),
        assignment_count=len(c.assignments),
        created_at=c.created_at,
        updated_at=c.updated_at
    )


@classrooms_router.post("/{classroom_id}/archive", response_model=ClassroomSummaryResponse)
async def archive_classroom_endpoint(
    classroom_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Archive classroom (Teacher owner or Admin). Closes classroom to new members."""
    c = await archive_classroom(db, classroom_id, user=current_user)
    return ClassroomSummaryResponse(
        id=c.id,
        name=c.name,
        code=c.code,
        grade_id=c.grade_id,
        teacher_id=c.teacher_id,
        teacher_name=c.teacher.full_name if c.teacher else None,
        description=c.description,
        status=c.status,
        is_archived=c.is_archived,
        max_students=c.max_students,
        member_count=len(c.members),
        assignment_count=len(c.assignments),
        created_at=c.created_at,
        updated_at=c.updated_at
    )


@classrooms_router.post("/{classroom_id}/regenerate-invite-code", response_model=Dict[str, str])
async def regenerate_code_endpoint(
    classroom_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate unique invite code for classroom (Teacher owner or Admin)."""
    new_code = await regenerate_classroom_code(db, classroom_id, user=current_user)
    return {"code": new_code}


@classrooms_router.get("/{classroom_id}/members", response_model=List[ClassroomMemberResponse])
async def get_classroom_members_endpoint(
    classroom_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """View member roster for classroom."""
    c = await get_classroom_by_id(db, classroom_id, user=current_user)
    return [
        ClassroomMemberResponse(
            id=m.id,
            student_id=m.student_id,
            student_name=m.student.full_name if m.student else "Học sinh",
            student_email=m.student.email if m.student else "",
            student_avatar=m.student.avatar_url if m.student else None,
            joined_at=m.joined_at
        )
        for m in c.members
    ]


@classrooms_router.delete("/{classroom_id}/members/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_student_endpoint(
    classroom_id: str,
    student_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Remove student from classroom (Teacher owner or Admin)."""
    await remove_student_from_classroom(db, classroom_id, student_id, user=current_user)
    return None


@classrooms_router.post("/{classroom_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_classroom_endpoint(
    classroom_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Student voluntarily leaves classroom."""
    await leave_classroom(db, classroom_id, student=current_user)
    return None


@classrooms_router.get("/{classroom_id}/statistics", response_model=ClassroomStatisticsResponse)
async def get_classroom_stats_endpoint(
    classroom_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Get aggregate performance and submission stats for classroom."""
    return await get_classroom_statistics(db, classroom_id, user=current_user)


# ==============================================================================
# CLASSROOM ASSIGNMENT ENDPOINTS
# ==============================================================================

@classrooms_router.get("/{classroom_id}/assignments", response_model=List[AssignmentSummaryResponse])
async def list_assignments_for_classroom(
    classroom_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List assignments in classroom:
    - Teacher/Admin: all assignments (Draft, Published, Cancelled).
    - Student: published assignments only.
    """
    assignments = await list_classroom_assignments(db, classroom_id, user=current_user)
    return [
        AssignmentSummaryResponse(
            id=a.id,
            classroom_id=a.classroom_id,
            classroom_name=a.classroom.name if a.classroom else None,
            exam_id=a.exam_id,
            exam_title=a.exam.title if a.exam else None,
            title=a.title,
            description=a.description,
            open_date=a.open_date,
            due_date=a.due_date,
            max_attempts=a.max_attempts,
            allow_late_submission=a.allow_late_submission,
            allow_review=a.allow_review,
            status=a.status,
            is_published=a.is_published,
            total_points=a.exam.total_points if a.exam else 10.0,
            duration_minutes=a.exam.duration_minutes if a.exam else 45,
            question_count=len(a.exam.exam_questions) if a.exam and a.exam.exam_questions else 0,
            created_at=a.created_at,
            updated_at=a.updated_at
        )
        for a in assignments
    ]


@classrooms_router.post("/{classroom_id}/assignments", response_model=AssignmentSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_new_assignment(
    classroom_id: str,
    data: AssignmentCreate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Create homework assignment for classroom from an existing published Exam."""
    a = await create_assignment(db, classroom_id, data, user=current_user)
    return AssignmentSummaryResponse(
        id=a.id,
        classroom_id=a.classroom_id,
        classroom_name=a.classroom.name if a.classroom else None,
        exam_id=a.exam_id,
        exam_title=a.exam.title if a.exam else None,
        title=a.title,
        description=a.description,
        open_date=a.open_date,
        due_date=a.due_date,
        max_attempts=a.max_attempts,
        allow_late_submission=a.allow_late_submission,
        allow_review=a.allow_review,
        status=a.status,
        is_published=a.is_published,
        total_points=a.exam.total_points if a.exam else 10.0,
        duration_minutes=a.exam.duration_minutes if a.exam else 45,
        question_count=len(a.exam.exam_questions) if a.exam and a.exam.exam_questions else 0,
        created_at=a.created_at,
        updated_at=a.updated_at
    )


# ==============================================================================
# ASSIGNMENTS STANDALONE ENDPOINTS
# ==============================================================================

@assignments_router.get("/{assignment_id}", response_model=AssignmentSummaryResponse)
async def get_assignment_detail_endpoint(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """View assignment detail."""
    a = await get_assignment_by_id(db, assignment_id, user=current_user)
    return AssignmentSummaryResponse(
        id=a.id,
        classroom_id=a.classroom_id,
        classroom_name=a.classroom.name if a.classroom else None,
        exam_id=a.exam_id,
        exam_title=a.exam.title if a.exam else None,
        title=a.title,
        description=a.description,
        open_date=a.open_date,
        due_date=a.due_date,
        max_attempts=a.max_attempts,
        allow_late_submission=a.allow_late_submission,
        allow_review=a.allow_review,
        status=a.status,
        is_published=a.is_published,
        total_points=a.exam.total_points if a.exam else 10.0,
        duration_minutes=a.exam.duration_minutes if a.exam else 45,
        question_count=len(a.exam.exam_questions) if a.exam and a.exam.exam_questions else 0,
        created_at=a.created_at,
        updated_at=a.updated_at
    )


@assignments_router.patch("/{assignment_id}", response_model=AssignmentSummaryResponse)
async def update_assignment_endpoint(
    assignment_id: str,
    data: AssignmentUpdate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Update assignment settings (Teacher owner / Admin)."""
    a = await update_assignment(db, assignment_id, data, user=current_user)
    return AssignmentSummaryResponse(
        id=a.id,
        classroom_id=a.classroom_id,
        classroom_name=a.classroom.name if a.classroom else None,
        exam_id=a.exam_id,
        exam_title=a.exam.title if a.exam else None,
        title=a.title,
        description=a.description,
        open_date=a.open_date,
        due_date=a.due_date,
        max_attempts=a.max_attempts,
        allow_late_submission=a.allow_late_submission,
        allow_review=a.allow_review,
        status=a.status,
        is_published=a.is_published,
        total_points=a.exam.total_points if a.exam else 10.0,
        duration_minutes=a.exam.duration_minutes if a.exam else 45,
        question_count=len(a.exam.exam_questions) if a.exam and a.exam.exam_questions else 0,
        created_at=a.created_at,
        updated_at=a.updated_at
    )


@assignments_router.post("/{assignment_id}/publish", response_model=AssignmentSummaryResponse)
async def publish_assignment_endpoint(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Publish assignment so students can see and start it."""
    a = await publish_assignment(db, assignment_id, user=current_user)
    return AssignmentSummaryResponse(
        id=a.id,
        classroom_id=a.classroom_id,
        classroom_name=a.classroom.name if a.classroom else None,
        exam_id=a.exam_id,
        exam_title=a.exam.title if a.exam else None,
        title=a.title,
        description=a.description,
        open_date=a.open_date,
        due_date=a.due_date,
        max_attempts=a.max_attempts,
        allow_late_submission=a.allow_late_submission,
        allow_review=a.allow_review,
        status=a.status,
        is_published=a.is_published,
        total_points=a.exam.total_points if a.exam else 10.0,
        duration_minutes=a.exam.duration_minutes if a.exam else 45,
        question_count=len(a.exam.exam_questions) if a.exam and a.exam.exam_questions else 0,
        created_at=a.created_at,
        updated_at=a.updated_at
    )


@assignments_router.post("/{assignment_id}/cancel", response_model=AssignmentSummaryResponse)
async def cancel_assignment_endpoint(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Cancel assignment (Teacher owner / Admin)."""
    a = await cancel_assignment(db, assignment_id, user=current_user)
    return AssignmentSummaryResponse(
        id=a.id,
        classroom_id=a.classroom_id,
        classroom_name=a.classroom.name if a.classroom else None,
        exam_id=a.exam_id,
        exam_title=a.exam.title if a.exam else None,
        title=a.title,
        description=a.description,
        open_date=a.open_date,
        due_date=a.due_date,
        max_attempts=a.max_attempts,
        allow_late_submission=a.allow_late_submission,
        allow_review=a.allow_review,
        status=a.status,
        is_published=a.is_published,
        total_points=a.exam.total_points if a.exam else 10.0,
        duration_minutes=a.exam.duration_minutes if a.exam else 45,
        question_count=len(a.exam.exam_questions) if a.exam and a.exam.exam_questions else 0,
        created_at=a.created_at,
        updated_at=a.updated_at
    )


@assignments_router.get("/{assignment_id}/submissions", response_model=AssignmentSubmissionsResponse)
async def get_assignment_submissions_endpoint(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full submission gradebook for an assignment (Teacher owner or Admin)."""
    return await get_assignment_submissions(db, assignment_id, user=current_user)


@assignments_router.post("/{assignment_id}/start", response_model=ExamStartResponse)
async def start_assignment_endpoint(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Student starts or resumes an assignment:
    - Enforces classroom membership.
    - Enforces opening time and server-side due date.
    - Sanitizes question snapshot (NO answer keys exposed).
    """
    attempt, snapshot = await start_assignment(db, assignment_id, student=current_user)
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


@assignments_router.get("/{assignment_id}/my-attempt", response_model=Dict[str, Any])
async def get_my_attempt_endpoint(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve current student's attempt state and saved answers."""
    return await get_my_assignment_attempt(db, assignment_id, student=current_user)


@assignments_router.post("/{assignment_id}/submit", response_model=ExamSubmitResponse)
async def submit_assignment_endpoint(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit student's active assignment attempt. Server-side auto-grading."""
    return await submit_assignment(db, assignment_id, student=current_user)
