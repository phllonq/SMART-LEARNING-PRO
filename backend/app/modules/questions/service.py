from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.modules.questions.models import Question, QuestionOption, QuestionType, DifficultyLevel
from app.modules.questions.schemas import QuestionCreate, QuestionUpdate
from app.modules.curriculum.models import Topic, Chapter, Subject, Lesson
from app.modules.auth.models import User, UserRole
from app.core.exceptions import EntityNotFoundException, PermissionDeniedException


async def get_questions(
    db: AsyncSession,
    grade_id: Optional[int] = None,
    subject_id: Optional[str] = None,
    chapter_id: Optional[str] = None,
    topic_id: Optional[str] = None,
    lesson_id: Optional[str] = None,
    difficulty_level: Optional[str] = None,
    question_type: Optional[str] = None,
    creator_id: Optional[str] = None,
    is_public: Optional[bool] = None,
    search: Optional[str] = None,
    user: Optional[User] = None,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Question], int]:
    """Retrieve filtered and paginated questions."""
    conditions = []

    # 1. Access & publication rules:
    # If unauthenticated or student: ONLY return public questions
    is_privileged = user and user.role in [UserRole.TEACHER.value, UserRole.ADMIN.value, UserRole.SUPERADMIN.value]
    if not is_privileged:
        conditions.append(Question.is_public == True)
    elif is_public is not None:
        conditions.append(Question.is_public == is_public)

    # 2. Direct filters
    if topic_id:
        conditions.append(Question.topic_id == topic_id)
    if lesson_id:
        conditions.append(Question.lesson_id == lesson_id)
    if difficulty_level:
        conditions.append(Question.difficulty_level == difficulty_level)
    if question_type:
        conditions.append(Question.question_type == question_type)
    if creator_id:
        conditions.append(Question.creator_id == creator_id)

    # 3. Search query
    if search:
        search_pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                Question.content.ilike(search_pattern),
                Question.tags.ilike(search_pattern)
            )
        )

    # 4. Hierarchical Curriculum filters (chapter, subject, grade)
    joins_needed = False
    join_target = Topic
    if chapter_id or subject_id or grade_id:
        joins_needed = True

    count_query = select(func.count(func.distinct(Question.id)))
    query = (
        select(Question)
        .options(
            selectinload(Question.options),
            selectinload(Question.creator),
            selectinload(Question.topic)
        )
        .order_by(Question.created_at.desc())
    )

    if joins_needed:
        # Join hierarchy
        count_query = count_query.join(Topic, Question.topic_id == Topic.id)
        query = query.join(Topic, Question.topic_id == Topic.id)

        if chapter_id:
            count_query = count_query.where(Topic.chapter_id == chapter_id)
            query = query.where(Topic.chapter_id == chapter_id)

        if subject_id or grade_id:
            count_query = count_query.join(Chapter, Topic.chapter_id == Chapter.id)
            query = query.join(Chapter, Topic.chapter_id == Chapter.id)

            if subject_id:
                count_query = count_query.where(Chapter.subject_id == subject_id)
                query = query.where(Chapter.subject_id == subject_id)

            if grade_id:
                count_query = count_query.join(Subject, Chapter.subject_id == Subject.id)
                query = query.join(Subject, Chapter.subject_id == Subject.id)
                count_query = count_query.where(Subject.grade_id == grade_id)
                query = query.where(Subject.grade_id == grade_id)

    if conditions:
        count_query = count_query.where(and_(*conditions))
        query = query.where(and_(*conditions))

    total = (await db.execute(count_query)).scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    questions = list(result.scalars().all())

    return questions, total


async def get_question_by_id(
    db: AsyncSession,
    question_id: str,
    user: Optional[User] = None
) -> Question:
    """Retrieve full question details with options."""
    query = (
        select(Question)
        .where(Question.id == question_id)
        .options(
            selectinload(Question.options),
            selectinload(Question.creator),
            selectinload(Question.topic)
        )
    )
    result = await db.execute(query)
    question = result.scalar_one_or_none()
    if not question:
        raise EntityNotFoundException("Question", question_id)

    is_privileged = user and user.role in [UserRole.TEACHER.value, UserRole.ADMIN.value, UserRole.SUPERADMIN.value]
    if not question.is_public and not is_privileged:
        raise EntityNotFoundException("Question", question_id)

    return question


async def create_question(
    db: AsyncSession,
    data: QuestionCreate,
    creator: User
) -> Question:
    """Create a new question and its options."""
    # Verify topic exists if provided
    if data.topic_id:
        topic_res = await db.execute(select(Topic).where(Topic.id == data.topic_id))
        if not topic_res.scalar_one_or_none():
            raise EntityNotFoundException("Topic", data.topic_id)

    # Verify lesson exists if provided
    if data.lesson_id:
        lesson_res = await db.execute(select(Lesson).where(Lesson.id == data.lesson_id))
        if not lesson_res.scalar_one_or_none():
            raise EntityNotFoundException("Lesson", data.lesson_id)

    question_data = data.model_dump(exclude={"options"})
    question = Question(
        **question_data,
        creator_id=creator.id
    )
    db.add(question)
    await db.flush()

    # Add options
    for opt_in in data.options:
        opt = QuestionOption(
            question_id=question.id,
            option_key=opt_in.option_key.strip().upper(),
            content=opt_in.content,
            is_correct=opt_in.is_correct,
            order_index=opt_in.order_index
        )
        db.add(opt)

    await db.flush()
    return await get_question_by_id(db, question.id, user=creator)


def check_question_ownership(question: Question, user: User):
    """Enforce teacher question ownership: only the creator or an Admin/Superadmin can modify."""
    if user.role in [UserRole.ADMIN.value, UserRole.SUPERADMIN.value]:
        return  # Admins have full access
    if user.role == UserRole.TEACHER.value:
        if question.creator_id != user.id:
            raise PermissionDeniedException("Bạn không có quyền chỉnh sửa hoặc xóa câu hỏi của giáo viên khác.")
        return
    raise PermissionDeniedException("Chỉ giáo viên hoặc quản trị viên mới có quyền thao tác.")


async def update_question(
    db: AsyncSession,
    question_id: str,
    data: QuestionUpdate,
    user: User
) -> Question:
    """Update question metadata, content, and options."""
    question = await get_question_by_id(db, question_id, user=user)
    check_question_ownership(question, user)

    update_dict = data.model_dump(exclude_unset=True, exclude={"options"})
    for key, value in update_dict.items():
        setattr(question, key, value)

    # If options are explicitly passed, replace them
    if data.options is not None:
        # Delete existing options
        for old_opt in question.options:
            await db.delete(old_opt)
        await db.flush()

        # Add new options
        for opt_in in data.options:
            new_opt = QuestionOption(
                question_id=question.id,
                option_key=opt_in.option_key.strip().upper(),
                content=opt_in.content,
                is_correct=opt_in.is_correct,
                order_index=opt_in.order_index
            )
            db.add(new_opt)

    await db.flush()
    return await get_question_by_id(db, question.id, user=user)


async def delete_question(
    db: AsyncSession,
    question_id: str,
    user: User
) -> bool:
    """Delete a question."""
    question = await get_question_by_id(db, question_id, user=user)
    check_question_ownership(question, user)
    await db.delete(question)
    await db.flush()
    return True


async def toggle_question_publish(
    db: AsyncSession,
    question_id: str,
    user: User
) -> Question:
    """Toggle publication status between draft and public."""
    question = await get_question_by_id(db, question_id, user=user)
    check_question_ownership(question, user)
    question.is_public = not question.is_public
    await db.flush()
    return await get_question_by_id(db, question.id, user=user)
