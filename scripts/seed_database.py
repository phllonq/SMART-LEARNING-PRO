"""
Database Seeding Script for SMART LEARNING PRO
Populates initial curriculum, sample questions, sample exams, and test accounts.
"""
import asyncio
import os
import sys

# Ensure backend app is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.database import init_db, AsyncSessionLocal
from app.core.security import hash_password
from app.modules.auth.models import User, UserRole
from app.modules.curriculum.models import Grade, Subject, Chapter, Topic, Lesson, LearningMaterial
from app.modules.questions.models import Question, QuestionOption, QuestionType, DifficultyLevel
from app.modules.exams.models import Exam, ExamQuestion
from app.modules.classrooms.models import Classroom, ClassroomMember
from sqlalchemy import select


async def seed_data():
    print("Initializing database tables...")
    await init_db()

    async with AsyncSessionLocal() as db:
        print("Checking existing seed data...")
        admin_check = await db.execute(select(User).where(User.email == "admin@smartlearning.vn"))
        if admin_check.scalar_one_or_none():
            print("Database already contains seed data. Skipping seed.")
            return

        print("Creating users...")
        # 1. Superadmin
        admin = User(
            id="user-admin-01",
            email="admin@smartlearning.vn",
            hashed_password=hash_password("AdminSecurePassword123!"),
            full_name="Quản Trị Viên Hệ Thống",
            role=UserRole.SUPERADMIN.value,
            is_active=True,
            is_verified=True,
        )

        # 2. Teacher
        teacher = User(
            id="user-teacher-01",
            email="giaovien.toan@smartlearning.vn",
            hashed_password=hash_password("TeacherPassword123!"),
            full_name="Thầy Nguyễn Hoàng Nam",
            role=UserRole.TEACHER.value,
            is_active=True,
            is_verified=True,
        )

        # 3. Student
        student = User(
            id="user-student-01",
            email="hocsinh.an@smartlearning.vn",
            hashed_password=hash_password("StudentPassword123!"),
            full_name="Nguyễn Văn An",
            role=UserRole.STUDENT.value,
            grade_level=11,
            xp_points=120,
            current_level=2,
            streak_days=5,
            is_active=True,
            is_verified=True,
        )
        db.add_all([admin, teacher, student])
        await db.flush()

        print("Creating grades & subjects...")
        # Grades
        g10 = Grade(id=10, name="Khối 10", description="Chương trình GDPT 2018 Lớp 10", order_index=1)
        g11 = Grade(id=11, name="Khối 11", description="Chương trình GDPT 2018 Lớp 11", order_index=2)
        g12 = Grade(id=12, name="Khối 12", description="Chương trình GDPT 2018 Lớp 12", order_index=3)
        db.add_all([g10, g11, g12])
        await db.flush()

        # Subject: Toán 11
        sub_math11 = Subject(
            id="toan-11",
            grade_id=11,
            name="Toán học 11",
            code="MATH11",
            icon="Calculator",
            color="#635BFF",
            is_published=True,
            order_index=1
        )
        # Subject: Vật lí 11
        sub_phys11 = Subject(
            id="vat-ly-11",
            grade_id=11,
            name="Vật lí 11",
            code="PHYS11",
            icon="Zap",
            color="#0EA5E9",
            is_published=True,
            order_index=2
        )
        # Subject: Hóa học 11
        sub_chem11 = Subject(
            id="hoa-hoc-11",
            grade_id=11,
            name="Hóa học 11",
            code="CHEM11",
            icon="FlaskConical",
            color="#10B981",
            is_published=True,
            order_index=3
        )
        db.add_all([sub_math11, sub_phys11, sub_chem11])
        await db.flush()

        # Chapter: Hàm số lượng giác
        chap1 = Chapter(
            id="chap-toan11-01",
            subject_id="toan-11",
            title="Chương 1: Hàm số lượng giác và phương trình lượng giác",
            order_index=1
        )
        db.add(chap1)
        await db.flush()

        # Topic: Phương trình lượng giác cơ bản
        topic1 = Topic(
            id="topic-toan11-ptlg",
            chapter_id="chap-toan11-01",
            title="Phương trình lượng giác cơ bản",
            description="Nắm vững cách giải các phương trình sin x = m, cos x = m, tan x = m, cot x = m",
            order_index=1
        )
        db.add(topic1)
        await db.flush()

        # Lesson
        lesson1 = Lesson(
            id="lesson-toan11-01",
            topic_id="topic-toan11-ptlg",
            title="Bài 1: Phương trình bậc nhất đối với một hàm số lượng giác",
            content_markdown="""# Phương trình lượng giác cơ bản

## 1. Phương trình $\\sin x = m$

- Nếu $|m| > 1$: Phương trình vô nghiệm vì $-1 \\le \\sin x \\le 1$.
- Nếu $|m| \\le 1$: Gọi $\\alpha$ là một góc thỏa mãn $\\sin \\alpha = m$, nghiệm của phương trình là:
$$\\begin{cases} x = \\alpha + k2\\pi \\\\ x = \\pi - \\alpha + k2\\pi \\end{cases} \\quad (k \\in \\mathbb{Z})$$

> **Lưu ý đặc biệt**:
> - $\\sin x = 0 \\iff x = k\\pi$
> - $\\sin x = 1 \\iff x = \\frac{\\pi}{2} + k2\\pi$
> - $\\sin x = -1 \\iff x = -\\frac{\\pi}{2} + k2\\pi$

## 2. Phương trình $\\cos x = m$

- Nếu $|m| > 1$: Phương trình vô nghiệm.
- Nếu $|m| \\le 1$: Gọi $\\alpha$ thỏa mãn $\\cos \\alpha = m$, ta có:
$$x = \\pm \\alpha + k2\\pi \\quad (k \\in \\mathbb{Z})$$
""",
            video_url="https://www.youtube.com/embed/dQw4w9WgXcQ",
            duration_minutes=45,
            order_index=1
        )
        db.add(lesson1)
        await db.flush()

        print("Creating sample questions with KaTeX and solutions...")
        # Question 1: sin x = 1/2
        q1 = Question(
            id="q-toan11-01",
            topic_id="topic-toan11-ptlg",
            creator_id="user-teacher-01",
            question_type=QuestionType.SINGLE_CHOICE.value,
            content="Tìm tất cả các nghiệm của phương trình $\\sin x = \\frac{1}{2}$.",
            difficulty_level=DifficultyLevel.RECOGNITION.value,
            explanation="Ta có $\\sin x = \\frac{1}{2} = \\sin \\frac{\\pi}{6}$. Do đó: $\\begin{cases} x = \\frac{\\pi}{6} + k2\\pi \\\\ x = \\pi - \\frac{\\pi}{6} + k2\\pi = \\frac{5\\pi}{6} + k2\\pi \\end{cases} (k \\in \\mathbb{Z})$.",
            hint="Nhớ lại góc đặc biệt có $\\sin$ bằng $\\frac{1}{2}$ là $\\frac{\\pi}{6}$."
        )
        db.add(q1)
        await db.flush()

        opt1_a = QuestionOption(id="opt-q1-a", question_id=q1.id, option_key="A", content="$x = \\pm \\frac{\\pi}{6} + k2\\pi, k \\in \\mathbb{Z}$", is_correct=False, order_index=1)
        opt1_b = QuestionOption(id="opt-q1-b", question_id=q1.id, option_key="B", content="$\\left[ \\begin{array}{l} x = \\frac{\\pi}{6} + k2\\pi \\\\ x = \\frac{5\\pi}{6} + k2\\pi \\end{array} \\right., k \\in \\mathbb{Z}$", is_correct=True, order_index=2)
        opt1_c = QuestionOption(id="opt-q1-c", question_id=q1.id, option_key="C", content="$x = \\frac{\\pi}{6} + k\\pi, k \\in \\mathbb{Z}$", is_correct=False, order_index=3)
        opt1_d = QuestionOption(id="opt-q1-d", question_id=q1.id, option_key="D", content="$\\left[ \\begin{array}{l} x = \\frac{\\pi}{3} + k2\\pi \\\\ x = \\frac{2\\pi}{3} + k2\\pi \\end{array} \\right., k \\in \\mathbb{Z}$", is_correct=False, order_index=4)
        db.add_all([opt1_a, opt1_b, opt1_c, opt1_d])

        # Question 2: cos 2x = 0
        q2 = Question(
            id="q-toan11-02",
            topic_id="topic-toan11-ptlg",
            creator_id="user-teacher-01",
            question_type=QuestionType.SINGLE_CHOICE.value,
            content="Nghiệm của phương trình $\\cos 2x = 0$ là:",
            difficulty_level=DifficultyLevel.COMPREHENSION.value,
            explanation="Ta có $\\cos 2x = 0 \\iff 2x = \\frac{\\pi}{2} + k\\pi \\iff x = \\frac{\\pi}{4} + k\\frac{\\pi}{2} (k \\in \\mathbb{Z})$.",
            hint="Trường hợp đặc biệt $\\cos u = 0 \\iff u = \\frac{\\pi}{2} + k\\pi$."
        )
        db.add(q2)
        await db.flush()

        opt2_a = QuestionOption(id="opt-q2-a", question_id=q2.id, option_key="A", content="$x = \\frac{\\pi}{4} + k\\frac{\\pi}{2}, k \\in \\mathbb{Z}$", is_correct=True, order_index=1)
        opt2_b = QuestionOption(id="opt-q2-b", question_id=q2.id, option_key="B", content="$x = \\frac{\\pi}{2} + k\\pi, k \\in \\mathbb{Z}$", is_correct=False, order_index=2)
        opt2_c = QuestionOption(id="opt-q2-c", question_id=q2.id, option_key="C", content="$x = \\pm \\frac{\\pi}{4} + k\\pi, k \\in \\mathbb{Z}$", is_correct=False, order_index=3)
        opt2_d = QuestionOption(id="opt-q2-d", question_id=q2.id, option_key="D", content="$x = \\frac{\\pi}{4} + k\\pi, k \\in \\mathbb{Z}$", is_correct=False, order_index=4)
        db.add_all([opt2_a, opt2_b, opt2_c, opt2_d])

        # Question 3: tan x = sqrt(3)
        q3 = Question(
            id="q-toan11-03",
            topic_id="topic-toan11-ptlg",
            creator_id="user-teacher-01",
            question_type=QuestionType.SINGLE_CHOICE.value,
            content="Phương trình $\\tan x = \\sqrt{3}$ có họ nghiệm là:",
            difficulty_level=DifficultyLevel.RECOGNITION.value,
            explanation="Ta có $\\tan x = \\sqrt{3} = \\tan \\frac{\\pi}{3} \\iff x = \\frac{\\pi}{3} + k\\pi (k \\in \\mathbb{Z})$.",
            hint="Hàm số $\\tan$ có chu kỳ tuần hoàn là $\\pi$."
        )
        db.add(q3)
        await db.flush()

        opt3_a = QuestionOption(id="opt-q3-a", question_id=q3.id, option_key="A", content="$x = \\frac{\\pi}{3} + k2\\pi, k \\in \\mathbb{Z}$", is_correct=False, order_index=1)
        opt3_b = QuestionOption(id="opt-q3-b", question_id=q3.id, option_key="B", content="$x = \\frac{\\pi}{6} + k\\pi, k \\in \\mathbb{Z}$", is_correct=False, order_index=2)
        opt3_c = QuestionOption(id="opt-q3-c", question_id=q3.id, option_key="C", content="$x = \\frac{\\pi}{3} + k\\pi, k \\in \\mathbb{Z}$", is_correct=True, order_index=3)
        opt3_d = QuestionOption(id="opt-q3-d", question_id=q3.id, option_key="D", content="$x = \\pm \\frac{\\pi}{3} + k\\pi, k \\in \\mathbb{Z}$", is_correct=False, order_index=4)
        db.add_all([opt3_a, opt3_b, opt3_c, opt3_d])

        print("Creating sample exam...")
        exam1 = Exam(
            id="exam-toan11-ptlg-45p",
            creator_id="user-teacher-01",
            subject_id="toan-11",
            title="Kiểm Tra 45 Phút: Phương Trình Lượng Giác Cơ Bản",
            description="Đề kiểm tra định kỳ đánh giá khả năng giải phương trình sin, cos, tan chuẩn GDPT 2018.",
            duration_minutes=45,
            total_points=10.0,
            passing_points=5.0,
            shuffle_questions=True,
            shuffle_options=True,
            allow_review=True,
            max_attempts=3,
            is_published=True
        )
        db.add(exam1)
        await db.flush()

        eq1 = ExamQuestion(id="eq-01", exam_id=exam1.id, question_id=q1.id, points=3.3, order_index=1)
        eq2 = ExamQuestion(id="eq-02", exam_id=exam1.id, question_id=q2.id, points=3.3, order_index=2)
        eq3 = ExamQuestion(id="eq-03", exam_id=exam1.id, question_id=q3.id, points=3.4, order_index=3)
        db.add_all([eq1, eq2, eq3])

        print("Creating sample classroom...")
        classroom = Classroom(
            id="class-11a1",
            teacher_id="user-teacher-01",
            name="Lớp 11A1 - Toán Chuyên",
            code="SL11A1",
            grade_id=11,
            description="Lớp học bồi dưỡng nâng cao Toán 11 năm học 2026-2027"
        )
        db.add(classroom)
        await db.flush()

        member = ClassroomMember(
            id="member-01",
            classroom_id=classroom.id,
            student_id="user-student-01"
        )
        db.add(member)

        await db.commit()
        print("SEEDING COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(seed_data())
