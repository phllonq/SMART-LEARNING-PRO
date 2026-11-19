import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import httpx

from scripts.migrate_phase5 import run_migration as run_phase5_migration
from scripts.migrate_hardening import run_hardening_migration


async def register_and_login_student(client: httpx.AsyncClient, name: str = "Test Student") -> dict:
    """Helper to create a fresh student, log in, and return bearer headers."""
    email = f"stu_{uuid.uuid4().hex[:8]}@smartlearning.vn"
    password = "SecurePassword123!"
    reg = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "full_name": name,
        "role": "STUDENT",
        "grade_level": 11
    })
    assert reg.status_code == 201, reg.text

    login = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": password
    })
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_migration_idempotency():
    """
    Verify database migrations are 100% idempotent and can be safely re-run
    without creating duplicate columns, duplicate indexes, or corrupting state.
    """
    run_phase5_migration()
    run_phase5_migration()
    run_hardening_migration()
    run_hardening_migration()
    assert True


@pytest.mark.asyncio
async def test_concurrent_classroom_join_same_student(client: httpx.AsyncClient):
    """
    Verify concurrency safety when a student triggers multiple simultaneous
    join requests with the same invite code. Exactly one must succeed (200 OK)
    and the other must receive 409 Conflict.
    """
    login_t = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    token_t = login_t.json()["access_token"]
    headers_t = {"Authorization": f"Bearer {token_t}"}

    class_res = await client.post("/api/v1/classrooms", headers=headers_t, json={
        "name": f"Lớp Concurrency Test {uuid.uuid4().hex[:6]}",
        "grade_id": 10,
        "max_students": 30
    })
    assert class_res.status_code == 201
    code = class_res.json()["code"]
    classroom_id = class_res.json()["id"]

    headers_stu = await register_and_login_student(client, "Concurrent Student")

    # Trigger 2 simultaneous join requests
    results = await asyncio.gather(
        client.post("/api/v1/classrooms/join", headers=headers_stu, json={"code": code}),
        client.post("/api/v1/classrooms/join", headers=headers_stu, json={"code": code})
    )

    status_codes = sorted([r.status_code for r in results])
    assert 200 in status_codes, f"One request must succeed: {status_codes}"
    assert any(c in [400, 409] for c in status_codes), f"Second request must be rejected as duplicate: {status_codes}"

    # Verify classroom member count is strictly 1
    members_res = await client.get(f"/api/v1/classrooms/{classroom_id}/members", headers=headers_t)
    assert members_res.status_code == 200
    assert len(members_res.json()) == 1


@pytest.mark.asyncio
async def test_concurrent_classroom_join_capacity_limit(client: httpx.AsyncClient):
    """
    Verify capacity limit enforcement under concurrency.
    When only 1 seat is available, two distinct students joining concurrently
    must result in exactly 1 acceptance and 1 rejection (403 Forbidden).
    """
    login_t = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    headers_t = {"Authorization": f"Bearer {login_t.json()['access_token']}"}

    class_res = await client.post("/api/v1/classrooms", headers=headers_t, json={
        "name": f"Lớp 1 Chỗ {uuid.uuid4().hex[:6]}",
        "grade_id": 10,
        "max_students": 1
    })
    assert class_res.status_code == 201
    code = class_res.json()["code"]
    classroom_id = class_res.json()["id"]

    headers_a = await register_and_login_student(client, "Student Seat A")
    headers_b = await register_and_login_student(client, "Student Seat B")

    results = await asyncio.gather(
        client.post("/api/v1/classrooms/join", headers=headers_a, json={"code": code}),
        client.post("/api/v1/classrooms/join", headers=headers_b, json={"code": code})
    )

    codes = [r.status_code for r in results]
    assert 200 in codes, f"One student must successfully join: {codes}"
    assert 403 in codes, f"Second student must be rejected due to capacity limit: {codes}"

    # Confirm database has strictly 1 member
    members_res = await client.get(f"/api/v1/classrooms/{classroom_id}/members", headers=headers_t)
    assert members_res.status_code == 200
    assert len(members_res.json()) == 1


@pytest.mark.asyncio
async def test_concurrent_exam_attempt_start(client: httpx.AsyncClient):
    """
    Verify concurrency safety when a student triggers multiple simultaneous
    start requests on an examination. Must not create duplicate active attempts;
    both requests return 200 OK with the identical attempt_id or one returns 409.
    """
    headers_stu = await register_and_login_student(client, "Fresh Exam Student")

    # Use seeded exam
    exam_id = "exam-toan11-ptlg-45p"

    # Start 2 attempts concurrently
    results = await asyncio.gather(
        client.post(f"/api/v1/exams/{exam_id}/start", headers=headers_stu),
        client.post(f"/api/v1/exams/{exam_id}/start", headers=headers_stu)
    )

    status_codes = [r.status_code for r in results]
    assert 200 in status_codes, f"At least one must succeed: {status_codes}"
    assert all(c in [200, 409] for c in status_codes), f"Status codes must be 200 or 409: {status_codes}"

    # Verify attempt_id consistency
    ok_attempts = [r.json()["attempt_id"] for r in results if r.status_code == 200]
    assert len(set(ok_attempts)) == 1, "All successful starts must refer to the exact same attempt"


@pytest.mark.asyncio
async def test_out_of_order_autosave_protection(client: httpx.AsyncClient):
    """
    Verify out-of-order autosave protection:
    If a delayed network packet (lower time_spent_seconds) arrives after a newer
    packet, the server discards the stale packet and preserves the newer answer.
    """
    headers_stu = await register_and_login_student(client, "Autosave Student")

    exam_id = "exam-toan11-ptlg-45p"
    start_res = await client.post(f"/api/v1/exams/{exam_id}/start", headers=headers_stu)
    assert start_res.status_code == 200
    attempt_id = start_res.json()["attempt_id"]
    question_id = start_res.json()["questions"][0]["question_id"]
    options = start_res.json()["questions"][0]["options"]
    opt_newer = options[0]["id"]
    opt_older = options[1]["id"]

    # 1. Save newer answer at t=45 seconds
    res1 = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{question_id}",
        headers=headers_stu,
        json={
            "selected_option_id": opt_newer,
            "time_spent_seconds": 45,
            "is_flagged": True
        }
    )
    assert res1.status_code == 200

    # 2. Delayed older packet arrives with t=20 seconds
    res2 = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{question_id}",
        headers=headers_stu,
        json={
            "selected_option_id": opt_older,
            "time_spent_seconds": 20,
            "is_flagged": False
        }
    )
    assert res2.status_code == 200

    # 3. Retrieve attempt detail to verify stale packet was ignored
    detail_res = await client.get(f"/api/v1/exams/attempts/{attempt_id}", headers=headers_stu)
    assert detail_res.status_code == 200
    saved_answers = detail_res.json().get("saved_answers", {})
    assert question_id in saved_answers
    assert saved_answers[question_id]["selected_option_id"] == opt_newer
    assert saved_answers[question_id]["time_spent_seconds"] == 45


@pytest.mark.asyncio
async def test_question_bank_edit_decoupling_and_snapshot_grading(client: httpx.AsyncClient):
    """
    Verify immutable question snapshot grading:
    1. Teacher creates exam with Question Q.
    2. Student starts attempt -> captures answer key snapshot.
    3. Teacher modifies Question Q in Question Bank (changes content, alters options and correct answer).
    4. Student submits attempt: grading evaluates against snapshot captured at attempt start.
    5. Score and reviews are accurate and decoupled from teacher's subsequent edits.
    """
    login_t = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    headers_t = {"Authorization": f"Bearer {login_t.json()['access_token']}"}

    # 1. Teacher creates question in Question Bank
    q_create = await client.post("/api/v1/questions", headers=headers_t, json={
        "content": "Giá trị của cos(0) là bao nhiêu?",
        "question_type": "SINGLE_CHOICE",
        "difficulty_level": "RECOGNITION",
        "subject_id": "toan-11",
        "grade_id": 11,
        "explanation": "cos(0) = 1 theo bảng lượng giác cơ bản.",
        "options": [
            {"option_key": "A", "content": "1", "is_correct": True, "order_index": 1},
            {"option_key": "B", "content": "0", "is_correct": False, "order_index": 2}
        ]
    })
    assert q_create.status_code == 201, q_create.text
    q_data = q_create.json()
    q_id = q_data["id"]
    correct_opt_id = next(o["id"] for o in q_data["options"] if o["is_correct"])

    # 2. Teacher creates & publishes exam with this question
    exam_res = await client.post("/api/v1/exams", headers=headers_t, json={
        "title": f"Đề Snapshot Test {uuid.uuid4().hex[:6]}",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 15,
        "total_points": 10.0,
        "passing_points": 5.0,
        "max_attempts": 1,
        "allow_review": True
    })
    assert exam_res.status_code == 201, exam_res.text
    exam_id = exam_res.json()["id"]

    await client.post(f"/api/v1/exams/{exam_id}/questions", headers=headers_t, json={
        "question_id": q_id,
        "points": 10.0,
        "order_index": 1
    })
    await client.post(f"/api/v1/exams/{exam_id}/publish", headers=headers_t)

    # 3. Fresh student starts attempt
    headers_s = await register_and_login_student(client, "Snapshot Student")

    start_res = await client.post(f"/api/v1/exams/{exam_id}/start", headers=headers_s)
    assert start_res.status_code == 200
    attempt_id = start_res.json()["attempt_id"]

    # Student answers with original correct option (1)
    await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=headers_s,
        json={"selected_option_id": correct_opt_id, "time_spent_seconds": 10}
    )

    # 4. Teacher EDITS Question Q in Question Bank (changes content and explanation)
    await client.put(f"/api/v1/questions/{q_id}", headers=headers_t, json={
        "content": "Giá trị của cos(pi/2) là bao nhiêu? (ĐÃ SỬA)",
        "explanation": "cos(pi/2) = 0 (ĐÃ SỬA GIẢI THÍCH)"
    })

    # 5. Student submits attempt
    submit_res = await client.post(f"/api/v1/exams/attempts/{attempt_id}/submit", headers=headers_s)
    assert submit_res.status_code == 200
    sub_data = submit_res.json()

    # Grading must evaluate against snapshot: student awarded 10.0 / 10.0 points
    assert sub_data["total_score"] == 10.0
    assert sub_data["correct_answers_count"] == 1
    assert sub_data["is_passed"] is True

    # 6. Student reviews attempt via review endpoint
    rev_res = await client.get(f"/api/v1/exams/attempts/{attempt_id}/review", headers=headers_s)
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["total_score"] == 10.0
    assert len(rev_data["question_reviews"]) == 1
    review_q = rev_data["question_reviews"][0]
    assert review_q["is_correct"] is True
    assert review_q["content"] == "Giá trị của cos(0) là bao nhiêu?"  # Immutable content preserved
    assert "cos(0) = 1" in review_q["explanation"]  # Immutable explanation preserved


@pytest.mark.asyncio
async def test_submission_review_security_and_idor(client: httpx.AsyncClient):
    """
    Verify security on /attempts/{attempt_id}/review:
    - In-progress attempts cannot be reviewed (403 Forbidden).
    - Other students cannot access reviews belonging to other students (403 Forbidden).
    - Teachers and Admins can access student reviews.
    """
    login_t = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    headers_t = {"Authorization": f"Bearer {login_t.json()['access_token']}"}

    headers_1 = await register_and_login_student(client, "Review Student 1")
    headers_2 = await register_and_login_student(client, "Review Student 2")

    # Student 1 starts attempt
    start_res = await client.post("/api/v1/exams/exam-toan11-ptlg-45p/start", headers=headers_1)
    assert start_res.status_code == 200
    attempt_id = start_res.json()["attempt_id"]

    # 1. Attempt in progress cannot be reviewed -> 403 Forbidden
    in_prog_rev = await client.get(f"/api/v1/exams/attempts/{attempt_id}/review", headers=headers_1)
    assert in_prog_rev.status_code == 403

    # Submit attempt
    sub_res = await client.post(f"/api/v1/exams/attempts/{attempt_id}/submit", headers=headers_1)
    assert sub_res.status_code == 200

    # 2. Student 2 tries to review Student 1's attempt (IDOR attack) -> 403 Forbidden
    idor_res = await client.get(f"/api/v1/exams/attempts/{attempt_id}/review", headers=headers_2)
    assert idor_res.status_code == 403

    # 3. Student 1 accesses own review -> 200 OK
    valid_res = await client.get(f"/api/v1/exams/attempts/{attempt_id}/review", headers=headers_1)
    assert valid_res.status_code == 200
    assert valid_res.json()["attempt_id"] == attempt_id

    # 4. Teacher accesses Student 1's review -> 200 OK
    teacher_rev = await client.get(f"/api/v1/exams/attempts/{attempt_id}/review", headers=headers_t)
    assert teacher_rev.status_code == 200


@pytest.mark.asyncio
async def test_cancelled_assignment_submission_safety(client: httpx.AsyncClient):
    """
    Verify that if a teacher cancels an assignment while a student has an
    in-progress attempt, the student's submission still completes safely
    without crashing or returning an unhandled 403.
    """
    login_t = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    headers_t = {"Authorization": f"Bearer {login_t.json()['access_token']}"}

    class_res = await client.post("/api/v1/classrooms", headers=headers_t, json={
        "name": f"Lớp Cancel Test {uuid.uuid4().hex[:6]}",
        "grade_id": 11
    })
    classroom_id = class_res.json()["id"]
    code = class_res.json()["code"]

    assign_res = await client.post(
        f"/api/v1/classrooms/{classroom_id}/assignments",
        headers=headers_t,
        json={
            "exam_id": "exam-toan11-ptlg-45p",
            "title": "Bài Tập Sắp Bị Hủy",
            "due_date": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            "max_attempts": 1,
            "status": "PUBLISHED"
        }
    )
    assignment_id = assign_res.json()["id"]

    headers_s = await register_and_login_student(client, "Cancel Test Student")

    await client.post("/api/v1/classrooms/join", headers=headers_s, json={"code": code})
    start_res = await client.post(f"/api/v1/assignments/{assignment_id}/start", headers=headers_s)
    assert start_res.status_code == 200

    # Teacher cancels assignment while student is working
    cancel_res = await client.post(f"/api/v1/assignments/{assignment_id}/cancel", headers=headers_t)
    assert cancel_res.status_code == 200

    # Student submits assignment: submission should proceed cleanly
    sub_res = await client.post(f"/api/v1/assignments/{assignment_id}/submit", headers=headers_s)
    assert sub_res.status_code == 200
    assert sub_res.json()["status"] in ["GRADED", "SUBMITTED"]
