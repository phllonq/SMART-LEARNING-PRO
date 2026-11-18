from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.modules.curriculum.models import Grade, Subject, Chapter, Topic, Lesson, LearningMaterial
from app.modules.curriculum.schemas import (
    SubjectCreate, SubjectUpdate,
    ChapterCreate,
    TopicCreate,
    LessonCreate, LessonUpdate
)
from app.core.exceptions import EntityNotFoundException, DuplicateEntityException, PermissionDeniedException


# Grade Service
async def get_all_grades(db: AsyncSession) -> List[Grade]:
    query = select(Grade).order_by(Grade.order_index)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_grade_by_id(db: AsyncSession, grade_id: int) -> Optional[Grade]:
    query = select(Grade).where(Grade.id == grade_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


# Subject Service
async def get_subjects(
    db: AsyncSession,
    grade_id: Optional[int] = None,
    include_unpublished: bool = False,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Subject], int]:
    conditions = []
    if grade_id is not None:
        conditions.append(Subject.grade_id == grade_id)
    if not include_unpublished:
        conditions.append(Subject.is_published == True)

    count_query = select(func.count(Subject.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = select(Subject)
    if conditions:
        query = query.where(and_(*conditions))
    query = query.order_by(Subject.order_index).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    subjects = list(result.scalars().all())
    return subjects, total


async def get_subject_by_id(
    db: AsyncSession,
    subject_id: str,
    include_unpublished: bool = False
) -> Subject:
    query = select(Subject).where(Subject.id == subject_id)
    result = await db.execute(query)
    subject = result.scalar_one_or_none()
    if not subject:
        raise EntityNotFoundException("Subject", subject_id)

    if not subject.is_published and not include_unpublished:
        # Hide unpublished subject from unauthorized users
        raise EntityNotFoundException("Subject", subject_id)

    return subject


async def create_subject(db: AsyncSession, data: SubjectCreate) -> Subject:
    existing = await db.execute(select(Subject).where(Subject.id == data.id))
    if existing.scalar_one_or_none():
        raise DuplicateEntityException(f"Subject with id '{data.id}' already exists.")

    grade = await get_grade_by_id(db, data.grade_id)
    if not grade:
        raise EntityNotFoundException("Grade", str(data.grade_id))

    subject = Subject(**data.model_dump())
    db.add(subject)
    await db.flush()
    await db.refresh(subject)
    return subject


# Chapter & Hierarchy Service
async def get_subject_chapters_tree(
    db: AsyncSession,
    subject_id: str,
    include_unpublished: bool = False
) -> List[Chapter]:
    # Check subject exists and publication status
    await get_subject_by_id(db, subject_id, include_unpublished)

    query = (
        select(Chapter)
        .where(Chapter.subject_id == subject_id)
        .options(
            selectinload(Chapter.topics).selectinload(Topic.lessons)
        )
        .order_by(Chapter.order_index)
    )
    result = await db.execute(query)
    chapters = list(result.scalars().all())
    return chapters


async def create_chapter(db: AsyncSession, data: ChapterCreate) -> Chapter:
    subject = await get_subject_by_id(db, data.subject_id, include_unpublished=True)
    chapter = Chapter(**data.model_dump())
    db.add(chapter)
    await db.flush()
    await db.refresh(chapter)
    return chapter


# Topic Service
async def create_topic(db: AsyncSession, data: TopicCreate) -> Topic:
    chapter_res = await db.execute(select(Chapter).where(Chapter.id == data.chapter_id))
    chapter = chapter_res.scalar_one_or_none()
    if not chapter:
        raise EntityNotFoundException("Chapter", data.chapter_id)

    topic = Topic(**data.model_dump())
    db.add(topic)
    await db.flush()
    await db.refresh(topic)
    return topic


# Lesson Service
async def get_lessons_by_topic(
    db: AsyncSession,
    topic_id: str,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Lesson], int]:
    topic_res = await db.execute(select(Topic).where(Topic.id == topic_id))
    if not topic_res.scalar_one_or_none():
        raise EntityNotFoundException("Topic", topic_id)

    count_query = select(func.count(Lesson.id)).where(Lesson.topic_id == topic_id)
    total = (await db.execute(count_query)).scalar_one()

    query = (
        select(Lesson)
        .where(Lesson.topic_id == topic_id)
        .order_by(Lesson.order_index)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    lessons = list(result.scalars().all())
    return lessons, total


async def get_lessons_by_chapter(
    db: AsyncSession,
    chapter_id: str,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Lesson], int]:
    chapter_res = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    if not chapter_res.scalar_one_or_none():
        raise EntityNotFoundException("Chapter", chapter_id)

    # Join lessons through topics
    count_query = (
        select(func.count(Lesson.id))
        .join(Topic, Lesson.topic_id == Topic.id)
        .where(Topic.chapter_id == chapter_id)
    )
    total = (await db.execute(count_query)).scalar_one()

    query = (
        select(Lesson)
        .join(Topic, Lesson.topic_id == Topic.id)
        .where(Topic.chapter_id == chapter_id)
        .order_by(Topic.order_index, Lesson.order_index)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    lessons = list(result.scalars().all())
    return lessons, total


async def get_lesson_by_id(
    db: AsyncSession,
    lesson_id: str,
    include_unpublished: bool = False
) -> Lesson:
    query = (
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .options(selectinload(Lesson.materials))
    )
    result = await db.execute(query)
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise EntityNotFoundException("Lesson", lesson_id)

    # Check whether the parent subject is published
    parent_subject_query = (
        select(Subject)
        .join(Chapter, Chapter.subject_id == Subject.id)
        .join(Topic, Topic.chapter_id == Chapter.id)
        .where(Topic.id == lesson.topic_id)
    )
    sub_res = await db.execute(parent_subject_query)
    parent_subject = sub_res.scalar_one_or_none()
    if parent_subject and not parent_subject.is_published and not include_unpublished:
        raise EntityNotFoundException("Lesson", lesson_id)

    return lesson


async def create_lesson(db: AsyncSession, data: LessonCreate) -> Lesson:
    topic_res = await db.execute(select(Topic).where(Topic.id == data.topic_id))
    if not topic_res.scalar_one_or_none():
        raise EntityNotFoundException("Topic", data.topic_id)

    lesson = Lesson(**data.model_dump())
    db.add(lesson)
    await db.flush()
    # Eagerly load relationships to avoid greenlet lazy-load issues during Pydantic serialization
    return await get_lesson_by_id(db, lesson.id, include_unpublished=True)


async def update_lesson(db: AsyncSession, lesson_id: str, data: LessonUpdate) -> Lesson:
    lesson = await get_lesson_by_id(db, lesson_id, include_unpublished=True)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(lesson, key, value)
    await db.flush()
    return await get_lesson_by_id(db, lesson_id, include_unpublished=True)


async def delete_lesson(db: AsyncSession, lesson_id: str) -> bool:
    lesson = await get_lesson_by_id(db, lesson_id, include_unpublished=True)
    await db.delete(lesson)
    return True
