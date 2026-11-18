import math
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_roles, get_token_from_request
from app.core.security import decode_token
from app.modules.auth.models import User, UserRole
from app.modules.curriculum.schemas import (
    GradeResponse,
    SubjectResponse, SubjectCreate, SubjectUpdate,
    ChapterResponse, ChapterCreate,
    TopicResponse, TopicCreate,
    LessonSummaryResponse, LessonDetailResponse, LessonCreate, LessonUpdate,
    PaginatedResponse
)
from app.modules.curriculum.service import (
    get_all_grades, get_grade_by_id,
    get_subjects, get_subject_by_id, create_subject,
    get_subject_chapters_tree, create_chapter,
    create_topic,
    get_lessons_by_topic, get_lessons_by_chapter,
    get_lesson_by_id, create_lesson, update_lesson, delete_lesson
)

router = APIRouter(prefix="/curriculum", tags=["Curriculum"])


async def is_privileged_user(token: Optional[str] = Depends(get_token_from_request)) -> bool:
    """Helper to check if user has TEACHER, ADMIN, or SUPERADMIN rights to view unpublished content."""
    if not token:
        return False
    try:
        payload = decode_token(token)
        role = payload.get("role")
        return role in [UserRole.TEACHER.value, UserRole.ADMIN.value, UserRole.SUPERADMIN.value]
    except Exception:
        return False


# --- Grades ---
@router.get("/grades", response_model=List[GradeResponse])
async def list_grades(db: AsyncSession = Depends(get_db)):
    """Retrieve all grade levels (Lớp 6 đến Lớp 12)."""
    return await get_all_grades(db)


# --- Subjects ---
@router.get("/grades/{grade_id}/subjects", response_model=PaginatedResponse[SubjectResponse])
async def list_subjects_by_grade(
    grade_id: int = Path(..., ge=1, le=12),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    privileged: bool = Depends(is_privileged_user),
    db: AsyncSession = Depends(get_db)
):
    """List published subjects for a specific grade level."""
    subjects, total = await get_subjects(
        db=db,
        grade_id=grade_id,
        include_unpublished=privileged,
        page=page,
        page_size=page_size
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[SubjectResponse.model_validate(s) for s in subjects],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/subjects", response_model=PaginatedResponse[SubjectResponse])
async def list_all_subjects(
    grade_id: Optional[int] = Query(None, ge=1, le=12),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    privileged: bool = Depends(is_privileged_user),
    db: AsyncSession = Depends(get_db)
):
    """List all subjects with optional grade filtering."""
    subjects, total = await get_subjects(
        db=db,
        grade_id=grade_id,
        include_unpublished=privileged,
        page=page,
        page_size=page_size
    )
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[SubjectResponse.model_validate(s) for s in subjects],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/subjects/{subject_id}", response_model=SubjectResponse)
async def get_subject_detail(
    subject_id: str,
    privileged: bool = Depends(is_privileged_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details of a specific subject."""
    subject = await get_subject_by_id(db, subject_id, include_unpublished=privileged)
    return SubjectResponse.model_validate(subject)


@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_new_subject(
    data: SubjectCreate,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Create a new subject. (Admin only)"""
    subject = await create_subject(db, data)
    return SubjectResponse.model_validate(subject)


# --- Chapters & Hierarchy ---
@router.get("/subjects/{subject_id}/chapters", response_model=List[ChapterResponse])
async def get_subject_chapters(
    subject_id: str,
    privileged: bool = Depends(is_privileged_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the complete chapter, topic, and lesson outline for a subject."""
    chapters = await get_subject_chapters_tree(db, subject_id, include_unpublished=privileged)
    res = []
    for c in chapters:
        topics_res = []
        for t in c.topics:
            lessons_res = [
                LessonSummaryResponse(
                    id=l.id,
                    topic_id=l.topic_id,
                    title=l.title,
                    duration_minutes=l.duration_minutes,
                    order_index=l.order_index,
                    has_video=bool(l.video_url)
                )
                for l in t.lessons
            ]
            topics_res.append(
                TopicResponse(
                    id=t.id,
                    chapter_id=t.chapter_id,
                    title=t.title,
                    description=t.description,
                    order_index=t.order_index,
                    lessons=lessons_res
                )
            )
        res.append(
            ChapterResponse(
                id=c.id,
                subject_id=c.subject_id,
                title=c.title,
                order_index=c.order_index,
                topics=topics_res
            )
        )
    return res


@router.post("/chapters", response_model=ChapterResponse, status_code=status.HTTP_201_CREATED)
async def create_new_chapter(
    data: ChapterCreate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Create a new chapter under a subject."""
    chapter = await create_chapter(db, data)
    return ChapterResponse(
        id=chapter.id,
        subject_id=chapter.subject_id,
        title=chapter.title,
        order_index=chapter.order_index,
        topics=[]
    )


# --- Topics ---
@router.post("/topics", response_model=TopicResponse, status_code=status.HTTP_201_CREATED)
async def create_new_topic(
    data: TopicCreate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Create a new topic under a chapter."""
    topic = await create_topic(db, data)
    return TopicResponse(
        id=topic.id,
        chapter_id=topic.chapter_id,
        title=topic.title,
        description=topic.description,
        order_index=topic.order_index,
        lessons=[]
    )


# --- Lessons ---
@router.get("/topics/{topic_id}/lessons", response_model=PaginatedResponse[LessonSummaryResponse])
async def list_lessons_by_topic(
    topic_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List lessons belonging to a specific topic."""
    lessons, total = await get_lessons_by_topic(db, topic_id, page=page, page_size=page_size)
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[
            LessonSummaryResponse(
                id=l.id,
                topic_id=l.topic_id,
                title=l.title,
                duration_minutes=l.duration_minutes,
                order_index=l.order_index,
                has_video=bool(l.video_url)
            )
            for l in lessons
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/chapters/{chapter_id}/lessons", response_model=PaginatedResponse[LessonSummaryResponse])
async def list_lessons_by_chapter(
    chapter_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List all lessons across topics within a chapter."""
    lessons, total = await get_lessons_by_chapter(db, chapter_id, page=page, page_size=page_size)
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[
            LessonSummaryResponse(
                id=l.id,
                topic_id=l.topic_id,
                title=l.title,
                duration_minutes=l.duration_minutes,
                order_index=l.order_index,
                has_video=bool(l.video_url)
            )
            for l in lessons
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/lessons/{lesson_id}", response_model=LessonDetailResponse)
async def get_lesson_detail(
    lesson_id: str,
    privileged: bool = Depends(is_privileged_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve full lesson content including KaTeX formulas and learning materials."""
    lesson = await get_lesson_by_id(db, lesson_id, include_unpublished=privileged)
    return LessonDetailResponse.model_validate(lesson)


@router.post("/lessons", response_model=LessonDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_new_lesson(
    data: LessonCreate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Create a new lesson. (Teacher or Admin)"""
    lesson = await create_lesson(db, data)
    return LessonDetailResponse.model_validate(lesson)


@router.patch("/lessons/{lesson_id}", response_model=LessonDetailResponse)
async def update_existing_lesson(
    lesson_id: str,
    data: LessonUpdate,
    current_user: User = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Update lesson content or metadata. (Teacher or Admin)"""
    lesson = await update_lesson(db, lesson_id, data)
    return LessonDetailResponse.model_validate(lesson)


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_lesson(
    lesson_id: str,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db)
):
    """Delete a lesson. (Admin only)"""
    await delete_lesson(db, lesson_id)
    return None
