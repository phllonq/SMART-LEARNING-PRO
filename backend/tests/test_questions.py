import pytest
import httpx
import uuid
from app.modules.auth.models import UserRole


@pytest.mark.asyncio
async def test_list_questions_and_filters(client: httpx.AsyncClient):
    """Test listing questions with pagination, difficulty filtering, and keyword search."""
    # 1. Unauthenticated / Student list
    res = await client.get("/api/v1/questions?page=1&page_size=10")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 3

    # 2. Filter by topic_id (seed topic: topic-toan11-ptlg)
    res_topic = await client.get("/api/v1/questions?topic_id=topic-toan11-ptlg")
    assert res_topic.status_code == 200
    assert len(res_topic.json()["items"]) >= 3

    # 3. Filter by difficulty
    res_diff = await client.get("/api/v1/questions?difficulty_level=RECOGNITION")
    assert res_diff.status_code == 200
    for q in res_diff.json()["items"]:
        assert q["difficulty_level"] == "RECOGNITION"

    # 4. Search keyword (search for 'lượng giác' or 'cos')
    res_search = await client.get("/api/v1/questions?search=cos")
    assert res_search.status_code == 200
    assert len(res_search.json()["items"]) >= 1


@pytest.mark.asyncio
async def test_answer_confidentiality_for_students(client: httpx.AsyncClient):
    """
    CRITICAL SECURITY & CHEAT-PREVENTION TEST:
    Verify that students and anonymous users NEVER receive the `is_correct` attribute,
    while teachers and admins do receive it for question management.
    """
    # 1. Student logs in
    student_login = await client.post("/api/v1/auth/login", json={
        "email": "hocsinh.an@smartlearning.vn",
        "password": "StudentPassword123!"
    })
    assert student_login.status_code == 200
    student_token = student_login.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # Student requests question list
    res_stu_list = await client.get("/api/v1/questions", headers=student_headers)
    assert res_stu_list.status_code == 200
    for item in res_stu_list.json()["items"]:
        for opt in item["options"]:
            assert "is_correct" not in opt, f"LEAK DETECTED: is_correct found in student option: {opt}"

    # Student requests question detail
    res_stu_detail = await client.get("/api/v1/questions/q-toan11-01", headers=student_headers)
    assert res_stu_detail.status_code == 200
    stu_q = res_stu_detail.json()
    for opt in stu_q["options"]:
        assert "is_correct" not in opt, f"LEAK DETECTED: is_correct found in student question detail: {opt}"

    # 2. Teacher logs in
    teacher_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    teacher_token = teacher_login.json()["access_token"]
    teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

    # Teacher requests question detail -> must receive `is_correct`
    res_tea_detail = await client.get("/api/v1/questions/q-toan11-01", headers=teacher_headers)
    assert res_tea_detail.status_code == 200
    tea_q = res_tea_detail.json()
    assert any("is_correct" in opt for opt in tea_q["options"]), "Teacher should receive is_correct in management API"
    assert any(opt["is_correct"] is True for opt in tea_q["options"])


@pytest.mark.asyncio
async def test_create_question_validation_rules(client: httpx.AsyncClient):
    """Test question validation constraints (e.g. single choice must have 1 correct, duplicate keys)."""
    # Login Teacher
    teacher_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    teacher_headers = {"Authorization": f"Bearer {teacher_login.json()['access_token']}"}

    # 1. Invalid: Single choice with 0 correct answers
    bad_q1 = {
        "content": "Tính đạo hàm của $y = x^2$",
        "question_type": "SINGLE_CHOICE",
        "difficulty_level": "RECOGNITION",
        "options": [
            {"option_key": "A", "content": "$y' = x$", "is_correct": False},
            {"option_key": "B", "content": "$y' = 2x$", "is_correct": False}
        ]
    }
    res_bad1 = await client.post("/api/v1/questions", headers=teacher_headers, json=bad_q1)
    assert res_bad1.status_code == 422

    # 2. Invalid: Single choice with 2 correct answers
    bad_q2 = {
        "content": "Tính đạo hàm của $y = x^2$",
        "question_type": "SINGLE_CHOICE",
        "difficulty_level": "RECOGNITION",
        "options": [
            {"option_key": "A", "content": "$y' = 2x$", "is_correct": True},
            {"option_key": "B", "content": "$y' = 2x$", "is_correct": True}
        ]
    }
    res_bad2 = await client.post("/api/v1/questions", headers=teacher_headers, json=bad_q2)
    assert res_bad2.status_code == 422

    # 3. Invalid: Duplicate option keys (two 'A's)
    bad_q3 = {
        "content": "Chọn mệnh đề đúng",
        "question_type": "SINGLE_CHOICE",
        "options": [
            {"option_key": "A", "content": "Phương án 1", "is_correct": True},
            {"option_key": "A", "content": "Phương án 2", "is_correct": False}
        ]
    }
    res_bad3 = await client.post("/api/v1/questions", headers=teacher_headers, json=bad_q3)
    assert res_bad3.status_code == 422

    # 4. Student attempts to create question -> 403 Forbidden
    student_login = await client.post("/api/v1/auth/login", json={
        "email": "hocsinh.an@smartlearning.vn",
        "password": "StudentPassword123!"
    })
    student_headers = {"Authorization": f"Bearer {student_login.json()['access_token']}"}
    valid_q = {
        "content": "Tính $\\lim_{x \\to 0} \\frac{\\sin x}{x}$",
        "question_type": "SINGLE_CHOICE",
        "options": [
            {"option_key": "A", "content": "$1$", "is_correct": True},
            {"option_key": "B", "content": "$0$", "is_correct": False}
        ]
    }
    res_stu_create = await client.post("/api/v1/questions", headers=student_headers, json=valid_q)
    assert res_stu_create.status_code == 403


@pytest.mark.asyncio
async def test_create_and_retrieve_katex_question(client: httpx.AsyncClient):
    """Test creating a question with complex KaTeX formulas and verifying persistence."""
    teacher_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    teacher_headers = {"Authorization": f"Bearer {teacher_login.json()['access_token']}"}

    katex_content = "Cho tích phân $I = \\int_0^\\pi \\sin^2(x) dx$. Giá trị của $I$ bằng:"
    create_payload = {
        "topic_id": "topic-toan11-ptlg",
        "content": katex_content,
        "question_type": "SINGLE_CHOICE",
        "difficulty_level": "APPLICATION",
        "explanation": "Ta có $\\sin^2(x) = \\frac{1 - \\cos(2x)}{2}$. Tích phân $I = \\left[ \\frac{x}{2} - \\frac{\\sin(2x)}{4} \\right]_0^\\pi = \\frac{\\pi}{2}$.",
        "hint": "Hạ bậc hàm $\\sin^2(x)$ trước khi lấy nguyên hàm.",
        "tags": "tích phân, lượng giác, 11",
        "is_public": True,
        "options": [
            {"option_key": "A", "content": "$\\frac{\\pi}{2}$", "is_correct": True, "order_index": 1},
            {"option_key": "B", "content": "$\\pi$", "is_correct": False, "order_index": 2},
            {"option_key": "C", "content": "$\\frac{\\pi}{4}$", "is_correct": False, "order_index": 3},
            {"option_key": "D", "content": "$0$", "is_correct": False, "order_index": 4}
        ]
    }

    res = await client.post("/api/v1/questions", headers=teacher_headers, json=create_payload)
    assert res.status_code == 201
    q_data = res.json()
    q_id = q_data["id"]
    assert q_data["content"] == katex_content
    assert len(q_data["options"]) == 4

    # Verify retrieval
    get_res = await client.get(f"/api/v1/questions/{q_id}", headers=teacher_headers)
    assert get_res.status_code == 200
    assert "tích phân" in get_res.json()["tags"]


@pytest.mark.asyncio
async def test_teacher_ownership_boundaries_and_admin_override(client: httpx.AsyncClient):
    """
    Test RBAC ownership boundaries:
    - Teacher A creates Question A.
    - Teacher B cannot edit or delete Question A (403).
    - Admin CAN edit and delete Question A (200, 204).
    """
    # 1. Teacher A creates Question
    teacher_a_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    headers_a = {"Authorization": f"Bearer {teacher_a_login.json()['access_token']}"}

    q_res = await client.post("/api/v1/questions", headers=headers_a, json={
        "content": "Câu hỏi của Thầy A: $1 + 1 = ?$",
        "question_type": "SINGLE_CHOICE",
        "options": [
            {"option_key": "A", "content": "2", "is_correct": True},
            {"option_key": "B", "content": "3", "is_correct": False}
        ]
    })
    assert q_res.status_code == 201
    q_id = q_res.json()["id"]

    # 2. Register and login Teacher B
    teacher_b_email = f"teacher_b_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    reg_b = await client.post("/api/v1/auth/register", json={
        "email": teacher_b_email,
        "password": "Password123!",
        "full_name": "Cô Giáo Viên B",
        "role": "TEACHER"
    })
    assert reg_b.status_code == 201
    login_b = await client.post("/api/v1/auth/login", json={"email": teacher_b_email, "password": "Password123!"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # 3. Teacher B attempts to update Question A -> 403 Forbidden
    res_b_update = await client.patch(
        f"/api/v1/questions/{q_id}",
        headers=headers_b,
        json={"content": "Bị sửa bởi Thầy B"}
    )
    assert res_b_update.status_code == 403
    assert "không có quyền" in res_b_update.json()["detail"]

    # 4. Teacher B attempts to delete Question A -> 403 Forbidden
    res_b_delete = await client.delete(f"/api/v1/questions/{q_id}", headers=headers_b)
    assert res_b_delete.status_code == 403

    # 5. Admin overrides: Admin can update
    admin_login = await client.post("/api/v1/auth/login", json={
        "email": "admin@smartlearning.vn",
        "password": "AdminSecurePassword123!"
    })
    headers_admin = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    res_adm_update = await client.patch(
        f"/api/v1/questions/{q_id}",
        headers=headers_admin,
        json={"content": "Admin đã duyệt và chỉnh sửa chuẩn KaTeX"}
    )
    assert res_adm_update.status_code == 200
    assert "Admin đã duyệt" in res_adm_update.json()["content"]

    # 6. Admin deletes Question A -> 204 No Content
    res_adm_del = await client.delete(f"/api/v1/questions/{q_id}", headers=headers_admin)
    assert res_adm_del.status_code == 204

    # Verify deleted
    res_check = await client.get(f"/api/v1/questions/{q_id}", headers=headers_admin)
    assert res_check.status_code == 404


@pytest.mark.asyncio
async def test_unpublished_question_visibility_and_toggle(client: httpx.AsyncClient):
    """Test draft question hiding from students and toggle-publish action."""
    # 1. Teacher creates draft question (is_public: False)
    teacher_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    headers_teacher = {"Authorization": f"Bearer {teacher_login.json()['access_token']}"}

    draft_res = await client.post("/api/v1/questions", headers=headers_teacher, json={
        "content": "Đề thi bí mật chưa công bố: $f'(x) = 0$",
        "question_type": "SINGLE_CHOICE",
        "is_public": False,
        "options": [
            {"option_key": "A", "content": "$x = 0$", "is_correct": True},
            {"option_key": "B", "content": "$x = 1$", "is_correct": False}
        ]
    })
    assert draft_res.status_code == 201
    draft_id = draft_res.json()["id"]
    assert draft_res.json()["is_public"] is False

    # 2. Student attempts to access draft question -> 404 Not Found
    student_login = await client.post("/api/v1/auth/login", json={
        "email": "hocsinh.an@smartlearning.vn",
        "password": "StudentPassword123!"
    })
    headers_student = {"Authorization": f"Bearer {student_login.json()['access_token']}"}

    res_stu = await client.get(f"/api/v1/questions/{draft_id}", headers=headers_student)
    assert res_stu.status_code == 404

    # 3. Teacher toggles publish status
    toggle_res = await client.post(f"/api/v1/questions/{draft_id}/toggle-publish", headers=headers_teacher)
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_public"] is True

    # 4. Student can now access the question
    res_stu_now = await client.get(f"/api/v1/questions/{draft_id}", headers=headers_student)
    assert res_stu_now.status_code == 200
    assert res_stu_now.json()["id"] == draft_id
