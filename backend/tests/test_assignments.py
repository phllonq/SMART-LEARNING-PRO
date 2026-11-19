import uuid
from datetime import datetime, timezone, timedelta
import pytest
import httpx


@pytest.mark.asyncio
async def test_assignment_lifecycle_and_security(client: httpx.AsyncClient):
    """
    Test Teacher creates, publishes, edits, and cancels an assignment.
    Validates ownership boundaries and visibility rules for members vs non-members.
    """
    # 1. Login Teacher A
    login_a = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Teacher A creates classroom
    class_res = await client.post("/api/v1/classrooms", headers=headers_a, json={
        "name": "Lớp 11 Toán Chuyên Đề Bài Tập",
        "grade_id": 11
    })
    classroom_id = class_res.json()["id"]
    code = class_res.json()["code"]

    # 3. Student joins classroom
    login_stu = await client.post("/api/v1/auth/login", json={
        "email": "hocsinh.an@smartlearning.vn",
        "password": "StudentPassword123!"
    })
    headers_stu = {"Authorization": f"Bearer {login_stu.json()['access_token']}"}
    await client.post("/api/v1/classrooms/join", headers=headers_stu, json={"code": code})

    # 4. Teacher A creates assignment in DRAFT
    # Using seeded exam: exam-toan11-ptlg-45p
    now = datetime.now(timezone.utc)
    due_date = (now + timedelta(days=7)).isoformat()
    assign_payload = {
        "exam_id": "exam-toan11-ptlg-45p",
        "title": "Bài Tập Tuần 1: Phương Trình Lượng Giác",
        "description": "Làm cẩn thận các câu hỏi nhận biết và thông hiểu.",
        "due_date": due_date,
        "max_attempts": 2,
        "allow_late_submission": False,
        "allow_review": True,
        "status": "DRAFT"
    }
    assign_res = await client.post(
        f"/api/v1/classrooms/{classroom_id}/assignments",
        headers=headers_a,
        json=assign_payload
    )
    assert assign_res.status_code == 201
    assign_data = assign_res.json()
    assignment_id = assign_data["id"]
    assert assign_data["status"] == "DRAFT"
    assert assign_data["is_published"] is False

    # 5. Student cannot see DRAFT assignment in classroom assignments list
    stu_list = await client.get(f"/api/v1/classrooms/{classroom_id}/assignments", headers=headers_stu)
    assert stu_list.status_code == 200
    assert len(stu_list.json()) == 0

    # Student cannot directly access DRAFT assignment -> 403 Forbidden
    stu_get = await client.get(f"/api/v1/assignments/{assignment_id}", headers=headers_stu)
    assert stu_get.status_code == 403

    # 6. Teacher A publishes assignment
    pub_res = await client.post(f"/api/v1/assignments/{assignment_id}/publish", headers=headers_a)
    assert pub_res.status_code == 200
    assert pub_res.json()["status"] == "PUBLISHED"
    assert pub_res.json()["is_published"] is True

    # Now Student can see published assignment
    stu_list_after = await client.get(f"/api/v1/classrooms/{classroom_id}/assignments", headers=headers_stu)
    assert stu_list_after.status_code == 200
    assert len(stu_list_after.json()) == 1
    assert stu_list_after.json()[0]["id"] == assignment_id

    # 7. Non-member Student registers and tries to access assignment -> 403 Forbidden
    email_out = f"student_out_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": email_out, "password": "Password123!", "full_name": "Học Sinh Ngoài Lớp", "role": "STUDENT"
    })
    login_out = await client.post("/api/v1/auth/login", json={"email": email_out, "password": "Password123!"})
    headers_out = {"Authorization": f"Bearer {login_out.json()['access_token']}"}

    out_get = await client.get(f"/api/v1/assignments/{assignment_id}", headers=headers_out)
    assert out_get.status_code == 403
    assert "Bạn không có quyền truy cập" in out_get.json()["detail"]

    # 8. Teacher B tries to edit or cancel Teacher A's assignment -> 403 Forbidden
    email_tb = f"teacher_b_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": email_tb, "password": "Password123!", "full_name": "Giáo Viên B", "role": "TEACHER"
    })
    login_tb = await client.post("/api/v1/auth/login", json={"email": email_tb, "password": "Password123!"})
    headers_tb = {"Authorization": f"Bearer {login_tb.json()['access_token']}"}

    edit_tb = await client.patch(f"/api/v1/assignments/{assignment_id}", headers=headers_tb, json={"title": "Hacked"})
    assert edit_tb.status_code == 403

    cancel_tb = await client.post(f"/api/v1/assignments/{assignment_id}/cancel", headers=headers_tb)
    assert cancel_tb.status_code == 403


@pytest.mark.asyncio
async def test_assignment_student_workflow_and_deadline_limits(client: httpx.AsyncClient):
    """
    Test student starting assignment, answer confidentiality, autosaving,
    submitting, auto-grading result, idempotency, attempt limit, and teacher gradebook.
    """
    # 1. Login Teacher A
    login_a = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 2. Teacher A creates classroom and published assignment with 1 attempt limit
    class_res = await client.post("/api/v1/classrooms", headers=headers_a, json={
        "name": "Lớp 11 Giải Tích", "grade_id": 11
    })
    classroom_id = class_res.json()["id"]
    code = class_res.json()["code"]

    now = datetime.now(timezone.utc)
    due_date = (now + timedelta(days=3)).isoformat()
    assign_res = await client.post(
        f"/api/v1/classrooms/{classroom_id}/assignments",
        headers=headers_a,
        json={
            "exam_id": "exam-toan11-ptlg-45p",
            "title": "Kiểm Tra 45 Phút Chương 1",
            "due_date": due_date,
            "max_attempts": 1,
            "allow_late_submission": False,
            "allow_review": True,
            "status": "PUBLISHED"
        }
    )
    assignment_id = assign_res.json()["id"]

    # 3. Student joins classroom
    login_stu = await client.post("/api/v1/auth/login", json={
        "email": "hocsinh.an@smartlearning.vn",
        "password": "StudentPassword123!"
    })
    headers_stu = {"Authorization": f"Bearer {login_stu.json()['access_token']}"}
    await client.post("/api/v1/classrooms/join", headers=headers_stu, json={"code": code})

    # 4. Student starts assignment
    start_res = await client.post(f"/api/v1/assignments/{assignment_id}/start", headers=headers_stu)
    assert start_res.status_code == 200
    start_data = start_res.json()
    attempt_id = start_data["attempt_id"]
    assert start_data["attempt_number"] == 1
    assert len(start_data["questions"]) > 0

    # Verify Confidentiality: NO is_correct in student's snapshot!
    for q in start_data["questions"]:
        for opt in q["options"]:
            assert "is_correct" not in opt

    # 5. Autosave Answer
    q1 = start_data["questions"][0]
    q1_id = q1["question_id"]
    opt1_id = q1["options"][0]["id"]

    save_res = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q1_id}",
        headers=headers_stu,
        json={"selected_option_id": opt1_id, "time_spent_seconds": 30}
    )
    assert save_res.status_code == 200
    assert save_res.json()["status"] == "SAVED"

    # 6. Check student's current attempt state
    my_att = await client.get(f"/api/v1/assignments/{assignment_id}/my-attempt", headers=headers_stu)
    assert my_att.status_code == 200
    assert my_att.json()["status"] == "IN_PROGRESS"
    assert q1_id in my_att.json()["saved_answers"]
    assert my_att.json()["saved_answers"][q1_id]["selected_option_id"] == opt1_id

    # 7. Student submits assignment
    submit_res = await client.post(f"/api/v1/assignments/{assignment_id}/submit", headers=headers_stu)
    assert submit_res.status_code == 200
    sub_data = submit_res.json()
    assert sub_data["attempt_id"] == attempt_id
    assert sub_data["status"] in ["SUBMITTED", "GRADED"]
    assert sub_data["total_score"] >= 0.0
    assert sub_data["maximum_score"] == 10.0
    assert sub_data["review_allowed"] is True

    # 8. Idempotency test: duplicate submit returns same result
    dup_submit = await client.post(f"/api/v1/assignments/{assignment_id}/submit", headers=headers_stu)
    assert dup_submit.status_code == 200
    assert dup_submit.json()["total_score"] == sub_data["total_score"]

    # 9. Attempt limit check: student cannot start a 2nd attempt (max_attempts = 1)
    second_start = await client.post(f"/api/v1/assignments/{assignment_id}/start", headers=headers_stu)
    assert second_start.status_code == 403
    assert "hết số lượt làm bài" in second_start.json()["detail"]

    # 10. Teacher views submissions / gradebook
    subs_res = await client.get(f"/api/v1/assignments/{assignment_id}/submissions", headers=headers_a)
    assert subs_res.status_code == 200
    subs_data = subs_res.json()
    assert subs_data["assignment_id"] == assignment_id
    assert subs_data["total_students"] >= 1
    assert subs_data["submitted_count"] >= 1

    stu_item = next((item for item in subs_data["items"] if item["student_name"] == "Nguyễn Văn An"), None)
    assert stu_item is not None
    assert stu_item["status"] in ["SUBMITTED", "GRADED"]
    assert stu_item["score"] == sub_data["total_score"]
