from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles
from app.modules.auth.models import User, UserRole
from app.modules.classrooms.models import Assignment, AssignmentStatus, AssignmentType
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
    AssignmentSubmissionsResponse,
    FileSubmissionResponse,
    FileSubmissionGradeRequest,
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
    create_file_assignment,
    get_assignment_by_id,
    get_assignment_attachment_path,
    list_classroom_assignments,
    update_assignment,
    publish_assignment,
    cancel_assignment,
    get_assignment_submissions,
    start_assignment,
    get_my_assignment_attempt,
    submit_assignment,
    submit_file_assignment,
    get_file_submission_download_path,
    grade_file_submission,
)
from app.modules.exams.schemas import ExamStartResponse, ExamSubmitResponse


def _serialize_assignment_summary(a: Assignment, current_user: User) -> AssignmentSummaryResponse:
    """Serialize Assignment ORM into AssignmentSummaryResponse for both EXAM and FILE types."""
    is_file = (a.assignment_type == AssignmentType.FILE.value)
    has_att = bool(a.attachment_url)
    att_url = f"/api/v1/assignments/{a.id}/attachment" if has_att else None

    my_status: Optional[str] = None
    my_score: Optional[float] = None
    my_attempts_count = 0
    my_file_sub: Optional[FileSubmissionResponse] = None

    if current_user.role == UserRole.STUDENT.value:
        if is_file:
            sub = next((s for s in (a.file_submissions or []) if s.student_id == current_user.id), None)
            if sub:
                my_status = sub.status
                my_score = sub.score
                my_attempts_count = 1
                my_file_sub = FileSubmissionResponse(
                    id=sub.id,
                    assignment_id=sub.assignment_id,
                    student_id=sub.student_id,
                    file_name=sub.file_name,
                    file_size=sub.file_size,
                    content_type=sub.content_type,
                    student_note=sub.student_note,
                    status=sub.status,
                    score=sub.score,
                    teacher_feedback=sub.teacher_feedback,
                    submitted_at=sub.submitted_at,
                    graded_at=sub.graded_at,
                    download_url=f"/api/v1/assignments/{a.id}/file-submissions/{sub.id}/download",
                )
            else:
                my_status = "NOT_STARTED"
        else:
            my_atts = [att for att in (a.attempts or []) if att.student_id == current_user.id]
            my_attempts_count = len(my_atts)
            if my_atts:
                latest = sorted(my_atts, key=lambda x: x.started_at, reverse=True)[0]
                my_status = latest.status
                my_score = latest.score
            else:
                my_status = "NOT_STARTED"

    return AssignmentSummaryResponse(
        id=a.id,
        classroom_id=a.classroom_id,
        classroom_name=a.classroom.name if a.classroom else None,
        assignment_type=a.assignment_type or AssignmentType.EXAM.value,
        exam_id=a.exam_id,
        exam_title=a.exam.title if a.exam else None,
        attachment_name=a.attachment_name,
        has_attachment=has_att,
        attachment_download_url=att_url,
        title=a.title,
        description=a.description,
        open_date=a.open_date,
        due_date=a.due_date,
        max_attempts=a.max_attempts,
        allow_late_submission=a.allow_late_submission,
        allow_review=a.allow_review,
        status=a.status,
        is_published=a.is_published,
        total_points=a.exam.total_points if a.exam else (a.total_points or 10.0),
        duration_minutes=a.exam.duration_minutes if a.exam else 45,
        question_count=len(a.exam.exam_questions) if a.exam and a.exam.exam_questions else 0,
        my_status=my_status,
        my_score=my_score,
        my_attempts_count=my_attempts_count,
        my_file_submission=my_file_sub,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


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
    return [_serialize_assignment_summary(a, current_user) for a in assignments]


@classrooms_router.post("/{classroom_id}/assignments", response_model=AssignmentSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_new_assignment(
    classroom_id: str,
    data: AssignmentCreate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Create homework assignment for classroom from an existing published Exam."""
    a = await create_assignment(db, classroom_id, data, user=current_user)
    return _serialize_assignment_summary(a, current_user)


@classrooms_router.post("/{classroom_id}/assignments/upload", response_model=AssignmentSummaryResponse, status_code=status.HTTP_201_CREATED)
async def create_new_file_assignment(
    classroom_id: str,
    title: str = Form(..., min_length=3, max_length=255),
    due_date: datetime = Form(...),
    file: UploadFile = File(..., description="Tệp đề bài/bài tập (.pdf, .docx, .xlsx, ảnh, .txt, .zip)"),
    description: Optional[str] = Form(None),
    open_date: Optional[datetime] = Form(None),
    allow_late_submission: bool = Form(False),
    total_points: float = Form(10.0),
    assignment_status: AssignmentStatus = Form(AssignmentStatus.PUBLISHED, alias="status"),
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Create a file-attachment assignment uploaded directly from teacher's computer."""
    a = await create_file_assignment(
        db=db,
        classroom_id=classroom_id,
        title=title,
        due_date=due_date,
        upload_file=file,
        user=current_user,
        description=description,
        open_date=open_date,
        allow_late_submission=allow_late_submission,
        total_points=total_points,
        status=assignment_status,
    )
    return _serialize_assignment_summary(a, current_user)


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
    return _serialize_assignment_summary(a, current_user)


@assignments_router.patch("/{assignment_id}", response_model=AssignmentSummaryResponse)
async def update_assignment_endpoint(
    assignment_id: str,
    data: AssignmentUpdate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Update assignment settings (Teacher owner / Admin)."""
    a = await update_assignment(db, assignment_id, data, user=current_user)
    return _serialize_assignment_summary(a, current_user)


@assignments_router.post("/{assignment_id}/publish", response_model=AssignmentSummaryResponse)
async def publish_assignment_endpoint(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Publish assignment so students can see and start it."""
    a = await publish_assignment(db, assignment_id, user=current_user)
    return _serialize_assignment_summary(a, current_user)


@assignments_router.post("/{assignment_id}/cancel", response_model=AssignmentSummaryResponse)
async def cancel_assignment_endpoint(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Cancel assignment (Teacher owner / Admin)."""
    a = await cancel_assignment(db, assignment_id, user=current_user)
    return _serialize_assignment_summary(a, current_user)


@assignments_router.get("/{assignment_id}/attachment")
async def download_assignment_attachment_endpoint(
    assignment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download the teacher-attached file for a FILE assignment (members/owner/admin only)."""
    file_path, download_name = await get_assignment_attachment_path(db, assignment_id, user=current_user)
    return FileResponse(path=str(file_path), filename=download_name)


@assignments_router.get("/{assignment_id}/submissions", response_model=AssignmentSubmissionsResponse)
async def get_assignment_submissions_endpoint(
    assignment_id: str,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full submission gradebook for an assignment (Teacher owner or Admin)."""
    return await get_assignment_submissions(db, assignment_id, user=current_user)


@assignments_router.post("/{assignment_id}/file-submission", response_model=FileSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_file_assignment_endpoint(
    assignment_id: str,
    file: UploadFile = File(..., description="Tệp bài làm của học sinh"),
    note: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Student uploads a file submission for a FILE-type assignment."""
    sub = await submit_file_assignment(
        db=db,
        assignment_id=assignment_id,
        upload_file=file,
        student=current_user,
        student_note=note,
    )
    return FileSubmissionResponse(
        id=sub.id,
        assignment_id=sub.assignment_id,
        student_id=sub.student_id,
        file_name=sub.file_name,
        file_size=sub.file_size,
        content_type=sub.content_type,
        download_url=f"/api/v1/assignments/{assignment_id}/file-submissions/{sub.id}/download",
        student_note=sub.student_note,
        status=sub.status,
        score=sub.score,
        teacher_feedback=sub.teacher_feedback,
        submitted_at=sub.submitted_at,
        graded_at=sub.graded_at,
    )


@assignments_router.get("/{assignment_id}/file-submissions/{submission_id}/download")
async def download_file_submission_endpoint(
    assignment_id: str,
    submission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a student's file submission (owner student, teacher owner, or admin)."""
    file_path, download_name = await get_file_submission_download_path(
        db, assignment_id, submission_id, user=current_user
    )
    return FileResponse(path=str(file_path), filename=download_name)


@assignments_router.post("/{assignment_id}/file-submissions/{submission_id}/grade", response_model=FileSubmissionResponse)
async def grade_file_submission_endpoint(
    assignment_id: str,
    submission_id: str,
    data: FileSubmissionGradeRequest,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Teacher grades and writes feedback for a student's file submission."""
    sub = await grade_file_submission(
        db, assignment_id, submission_id, data, user=current_user
    )
    return FileSubmissionResponse(
        id=sub.id,
        assignment_id=sub.assignment_id,
        student_id=sub.student_id,
        file_name=sub.file_name,
        file_size=sub.file_size,
        content_type=sub.content_type,
        download_url=f"/api/v1/assignments/{assignment_id}/file-submissions/{sub.id}/download",
        student_note=sub.student_note,
        status=sub.status,
        score=sub.score,
        teacher_feedback=sub.teacher_feedback,
        submitted_at=sub.submitted_at,
        graded_at=sub.graded_at,
    )


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
