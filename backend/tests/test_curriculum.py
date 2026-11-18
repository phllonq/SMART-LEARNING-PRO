import pytest
import httpx
import uuid
from app.modules.auth.models import UserRole


@pytest.mark.asyncio
async def test_list_grades(client: httpx.AsyncClient):
    """Test listing all educational grade levels."""
    res = await client.get("/api/v1/curriculum/grades")
    assert res.status_code == 200
    grades = res.json()
    assert len(grades) >= 3
    grade_ids = [g["id"] for g in grades]
    assert 10 in grade_ids
    assert 11 in grade_ids
    assert 12 in grade_ids


@pytest.mark.asyncio
async def test_list_subjects_and_detail(client: httpx.AsyncClient):
    """Test listing subjects by grade and retrieving subject details."""
    # List subjects for Grade 11
    res = await client.get("/api/v1/curriculum/grades/11/subjects")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert data["total"] >= 3
    subject_codes = [s["code"] for s in data["items"]]
    assert "MATH11" in subject_codes

    # Get subject detail for "toan-11"
    sub_res = await client.get("/api/v1/curriculum/subjects/toan-11")
    assert sub_res.status_code == 200
    subject = sub_res.json()
    assert subject["id"] == "toan-11"
    assert subject["name"] == "Toán học 11"
    assert subject["code"] == "MATH11"
    assert subject["is_published"] is True


@pytest.mark.asyncio
async def test_subject_chapters_and_hierarchy(client: httpx.AsyncClient):
    """Test retrieving full curriculum outline (Subject -> Chapters -> Topics -> Lessons)."""
    res = await client.get("/api/v1/curriculum/subjects/toan-11/chapters")
    assert res.status_code == 200
    chapters = res.json()
    assert len(chapters) >= 1
    chap = chapters[0]
    assert "Hàm số lượng giác" in chap["title"]
    assert len(chap["topics"]) >= 1
    topic = chap["topics"][0]
    assert "Phương trình lượng giác" in topic["title"]
    assert len(topic["lessons"]) >= 1
    lesson = topic["lessons"][0]
    assert "Bài 1" in lesson["title"]


@pytest.mark.asyncio
async def test_get_lesson_detail_with_katex(client: httpx.AsyncClient):
    """Test retrieving full lesson content including KaTeX math expressions."""
    res = await client.get("/api/v1/curriculum/lessons/lesson-toan11-01")
    assert res.status_code == 200
    lesson = res.json()
    assert lesson["id"] == "lesson-toan11-01"
    assert "content_markdown" in lesson
    # Verify presence of KaTeX math formulas
    assert "\\sin x = m" in lesson["content_markdown"]
    assert "\\cos x = m" in lesson["content_markdown"]
    assert "\\begin{cases}" in lesson["content_markdown"]


@pytest.mark.asyncio
async def test_missing_resources_return_404(client: httpx.AsyncClient):
    """Test that requesting non-existent subjects, chapters, topics, or lessons returns 404."""
    fake_id = f"non-existent-{uuid.uuid4().hex[:6]}"

    res_sub = await client.get(f"/api/v1/curriculum/subjects/{fake_id}")
    assert res_sub.status_code == 404

    res_chap = await client.get(f"/api/v1/curriculum/chapters/{fake_id}/lessons")
    assert res_chap.status_code == 404

    res_topic = await client.get(f"/api/v1/curriculum/topics/{fake_id}/lessons")
    assert res_topic.status_code == 404

    res_lesson = await client.get(f"/api/v1/curriculum/lessons/{fake_id}")
    assert res_lesson.status_code == 404


@pytest.mark.asyncio
async def test_input_validation_errors(client: httpx.AsyncClient):
    """Test parameter validation rules (e.g. invalid grade, invalid pagination)."""
    # Grade ID out of range
    res_bad_grade = await client.get("/api/v1/curriculum/grades/99/subjects")
    assert res_bad_grade.status_code == 422

    res_neg_grade = await client.get("/api/v1/curriculum/grades/0/subjects")
    assert res_neg_grade.status_code == 422

    # Negative or zero page number
    res_bad_page = await client.get("/api/v1/curriculum/grades/11/subjects?page=0")
    assert res_bad_page.status_code == 422


@pytest.mark.asyncio
async def test_unpublished_content_access_control(client: httpx.AsyncClient):
    """
    Test that unpublished subjects cannot be viewed by students or unauthenticated users,
    but can be accessed by teachers and administrators.
    """
    # 1. Login as Admin
    admin_login = await client.post("/api/v1/auth/login", json={
        "email": "admin@smartlearning.vn",
        "password": "AdminSecurePassword123!"
    })
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Admin creates an unpublished draft subject
    draft_sub_id = f"draft-{uuid.uuid4().hex[:6]}"
    create_res = await client.post(
        "/api/v1/curriculum/subjects",
        headers=admin_headers,
        json={
            "id": draft_sub_id,
            "grade_id": 12,
            "name": "Toán Nâng Cao 12 (Bản Nháp)",
            "code": "DRAFT12",
            "is_published": False,
            "order_index": 99
        }
    )
    assert create_res.status_code == 201

    # 3. Student logs in
    student_login = await client.post("/api/v1/auth/login", json={
        "email": "hocsinh.an@smartlearning.vn",
        "password": "StudentPassword123!"
    })
    student_token = student_login.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # 4. Student attempts to access draft subject -> 404 Not Found (hidden)
    stu_res = await client.get(f"/api/v1/curriculum/subjects/{draft_sub_id}", headers=student_headers)
    assert stu_res.status_code == 404

    # 5. Teacher logs in
    teacher_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    teacher_token = teacher_login.json()["access_token"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    # 6. Teacher can view the draft subject
    tea_res = await client.get(f"/api/v1/curriculum/subjects/{draft_sub_id}", headers=teacher_headers)
    assert tea_res.status_code == 200
    assert tea_res.json()["is_published"] is False


@pytest.mark.asyncio
async def test_teacher_and_admin_curriculum_management(client: httpx.AsyncClient):
    """Test creating, updating, and deleting curriculum entities with RBAC."""
    # 1. Login Teacher
    teacher_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    teacher_token = teacher_login.json()["access_token"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    # 2. Teacher creates Chapter under "toan-11"
    chap_res = await client.post(
        "/api/v1/curriculum/chapters",
        headers=teacher_headers,
        json={"subject_id": "toan-11", "title": "Chương 2: Dãy số, cấp số cộng và cấp số nhân", "order_index": 2}
    )
    assert chap_res.status_code == 201
    chap_id = chap_res.json()["id"]

    # 3. Teacher creates Topic under that chapter
    topic_res = await client.post(
        "/api/v1/curriculum/topics",
        headers=teacher_headers,
        json={"chapter_id": chap_id, "title": "Cấp số cộng", "description": "Công thức số hạng tổng quát", "order_index": 1}
    )
    assert topic_res.status_code == 201
    topic_id = topic_res.json()["id"]

    # 4. Teacher creates Lesson under that topic
    lesson_res = await client.post(
        "/api/v1/curriculum/lessons",
        headers=teacher_headers,
        json={
            "topic_id": topic_id,
            "title": "Bài 1: Định nghĩa và tính chất của cấp số cộng",
            "content_markdown": "# Cấp số cộng\n\nSố hạng tổng quát: $u_n = u_1 + (n-1)d$",
            "duration_minutes": 45,
            "order_index": 1
        }
    )
    assert lesson_res.status_code == 201
    lesson_id = lesson_res.json()["id"]

    # 5. Teacher updates Lesson
    update_res = await client.patch(
        f"/api/v1/curriculum/lessons/{lesson_id}",
        headers=teacher_headers,
        json={"title": "Bài 1: Định nghĩa cấp số cộng (Cập nhật)", "duration_minutes": 50}
    )
    assert update_res.status_code == 200
    assert update_res.json()["duration_minutes"] == 50
    assert "Cập nhật" in update_res.json()["title"]

    # 6. Student attempts to delete lesson -> 403 Forbidden
    student_login = await client.post("/api/v1/auth/login", json={
        "email": "hocsinh.an@smartlearning.vn",
        "password": "StudentPassword123!"
    })
    student_token = student_login.json()["access_token"]
    del_stu = await client.delete(f"/api/v1/curriculum/lessons/{lesson_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert del_stu.status_code == 403

    # 7. Admin deletes lesson -> 204 No Content
    admin_login = await client.post("/api/v1/auth/login", json={
        "email": "admin@smartlearning.vn",
        "password": "AdminSecurePassword123!"
    })
    admin_token = admin_login.json()["access_token"]
    del_adm = await client.delete(f"/api/v1/curriculum/lessons/{lesson_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert del_adm.status_code == 204

    # 8. Verify lesson is gone
    check_res = await client.get(f"/api/v1/curriculum/lessons/{lesson_id}")
    assert check_res.status_code == 404
