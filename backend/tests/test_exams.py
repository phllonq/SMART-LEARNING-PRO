import pytest
import httpx
import uuid
from datetime import datetime, timezone, timedelta
from app.modules.auth.models import UserRole


@pytest.mark.asyncio
async def test_teacher_exam_management_and_ownership(client: httpx.AsyncClient):
    """Test creating, adding questions, publishing, archiving, and ownership checks."""
    # 1. Login Teacher A
    login_a = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Teacher A creates an exam in DRAFT
    create_payload = {
        "title": "Đề Khảo Sát Toán 11 Đầu Năm",
        "description": "Đánh giá kiến thức nền tảng",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 30,
        "total_points": 10.0,
        "passing_points": 5.0,
        "max_attempts": 2,
        "status": "DRAFT"
    }
    exam_res = await client.post("/api/v1/exams", headers=headers_a, json=create_payload)
    assert exam_res.status_code == 201
    exam = exam_res.json()
    exam_id = exam["id"]
    assert exam["status"] == "DRAFT"
    assert exam["is_published"] is False

    # 3. Publishing an exam with 0 questions must fail
    pub_fail = await client.post(f"/api/v1/exams/{exam_id}/publish", headers=headers_a)
    assert pub_fail.status_code == 403
    assert "chưa có câu hỏi nào" in pub_fail.json()["detail"]

    # 4. Add question from Question Bank (seeded question: q-toan11-01)
    add_q = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        headers=headers_a,
        json={"question_id": "q-toan11-01", "points": 5.0, "order_index": 1}
    )
    assert add_q.status_code == 200
    assert add_q.json()["question_count"] == 1

    # Add second question (q-toan11-02)
    add_q2 = await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        headers=headers_a,
        json={"question_id": "q-toan11-02", "points": 5.0, "order_index": 2}
    )
    assert add_q2.status_code == 200
    assert add_q2.json()["question_count"] == 2

    # 5. Now publish exam
    pub_ok = await client.post(f"/api/v1/exams/{exam_id}/publish", headers=headers_a)
    assert pub_ok.status_code == 200
    assert pub_ok.json()["status"] == "PUBLISHED"
    assert pub_ok.json()["is_published"] is True

    # 6. Register & Login Teacher B
    b_email = f"teacher_exam_b_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": b_email, "password": "Password123!", "full_name": "Giáo Viên B", "role": "TEACHER"
    })
    login_b = await client.post("/api/v1/auth/login", json={"email": b_email, "password": "Password123!"})
    headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

    # Teacher B tries to edit Teacher A's exam -> 403 Forbidden
    edit_b = await client.patch(f"/api/v1/exams/{exam_id}", headers=headers_b, json={"title": "Hack by Teacher B"})
    assert edit_b.status_code == 403

    # Teacher B tries to archive Teacher A's exam -> 403 Forbidden
    arch_b = await client.post(f"/api/v1/exams/{exam_id}/archive", headers=headers_b)
    assert arch_b.status_code == 403

    # 7. Admin Override: Admin can edit
    admin_login = await client.post("/api/v1/auth/login", json={
        "email": "admin@smartlearning.vn", "password": "AdminSecurePassword123!"
    })
    headers_admin = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    edit_adm = await client.patch(f"/api/v1/exams/{exam_id}", headers=headers_admin, json={"title": "Đề Chuẩn Đã Duyệt"})
    assert edit_adm.status_code == 200
    assert edit_adm.json()["title"] == "Đề Chuẩn Đã Duyệt"


@pytest.mark.asyncio
async def test_student_examination_flow_and_confidentiality(client: httpx.AsyncClient):
    """
    Test student taking an exam:
    - View available exams.
    - Start exam attempt & verify answer confidentiality.
    - Autosave student answer.
    - Submit attempt & automatic grading.
    - Verify server-side score calculation.
    """
    # 1. Login Student
    student_login = await client.post("/api/v1/auth/login", json={
        "email": "hocsinh.an@smartlearning.vn",
        "password": "StudentPassword123!"
    })
    student_token = student_login.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}

    # 2. Check available exams
    avail_res = await client.get("/api/v1/exams/available", headers=student_headers)
    assert avail_res.status_code == 200
    available_list = avail_res.json()
    assert len(available_list) >= 1
    target_exam = next((e for e in available_list if e["id"] == "exam-toan11-ptlg-45p"), available_list[0])
    exam_id = target_exam["id"]

    # 3. Student starts exam attempt
    start_res = await client.post(f"/api/v1/exams/{exam_id}/start", headers=student_headers)
    assert start_res.status_code == 200
    attempt_data = start_res.json()
    attempt_id = attempt_data["attempt_id"]
    assert attempt_data["exam_id"] == exam_id
    assert "questions" in attempt_data
    assert len(attempt_data["questions"]) >= 1

    # CRITICAL CONFIDENTIALITY CHECK:
    # Verify that NO question in the active exam attempt exposes `is_correct`!
    for q in attempt_data["questions"]:
        for opt in q["options"]:
            assert "is_correct" not in opt, f"SECURITY LEAK: is_correct found in active exam option: {opt}"

    # 4. Autosave answers for questions
    first_q = attempt_data["questions"][0]
    q_id = first_q["question_id"]
    chosen_opt_id = first_q["options"][0]["id"]

    save_res = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=student_headers,
        json={"selected_option_id": chosen_opt_id, "is_flagged": True, "time_spent_seconds": 15}
    )
    assert save_res.status_code == 200
    assert save_res.json()["status"] == "SAVED"

    # Verify attempt state
    att_state = await client.get(f"/api/v1/exams/attempts/{attempt_id}", headers=student_headers)
    assert att_state.status_code == 200
    state_data = att_state.json()
    assert q_id in state_data["saved_answers"]
    assert state_data["saved_answers"][q_id]["selected_option_id"] == chosen_opt_id

    # 5. Security: Another student cannot autosave to this attempt
    other_email = f"student_other_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": other_email, "password": "Password123!", "full_name": "Học Sinh Khác", "role": "STUDENT", "grade_level": 11
    })
    other_login = await client.post("/api/v1/auth/login", json={"email": other_email, "password": "Password123!"})
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    hack_save = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=other_headers,
        json={"selected_option_id": chosen_opt_id}
    )
    assert hack_save.status_code == 403

    # 6. Submit examination & trigger server-side automatic grading
    submit_res = await client.post(f"/api/v1/exams/attempts/{attempt_id}/submit", headers=student_headers)
    assert submit_res.status_code == 200
    sub_data = submit_res.json()
    assert sub_data["status"] == "GRADED"
    assert "total_score" in sub_data
    assert "accuracy_percentage" in sub_data
    assert "is_passed" in sub_data

    # 7. Idempotent submission: submitting again returns the same result
    repeat_res = await client.post(f"/api/v1/exams/attempts/{attempt_id}/submit", headers=student_headers)
    assert repeat_res.status_code == 200
    assert repeat_res.json()["total_score"] == sub_data["total_score"]

    # 8. Teacher views submissions
    teacher_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    teacher_headers = {"Authorization": f"Bearer {teacher_login.json()['access_token']}"}

    subs_res = await client.get(f"/api/v1/exams/{exam_id}/submissions", headers=teacher_headers)
    assert subs_res.status_code == 200
    subs_list = subs_res.json()
    assert len(subs_list) >= 1
    my_sub = next((s for s in subs_list if s["attempt_id"] == attempt_id), None)
    assert my_sub is not None
    assert my_sub["score"] == sub_data["total_score"]
