import pytest
import asyncio
import httpx
import uuid


async def setup_test_exam_and_attempt(client: httpx.AsyncClient):
    """Helper to create a dedicated exam with 1 question and start an attempt for a fresh student."""
    # 1. Login Teacher to setup exam
    t_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    assert t_login.status_code == 200
    t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

    exam_res = await client.post("/api/v1/exams", headers=t_headers, json={
        "title": f"Đề Serialization Test {uuid.uuid4().hex[:6]}",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 45,
        "total_points": 10.0,
        "passing_points": 5.0,
        "status": "DRAFT"
    })
    assert exam_res.status_code == 201
    exam_id = exam_res.json()["id"]

    # Assign question q-toan11-01
    await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        headers=t_headers,
        json={"question_id": "q-toan11-01", "points": 10.0, "order_index": 1}
    )
    await client.post(f"/api/v1/exams/{exam_id}/publish", headers=t_headers)

    # 2. Register & login fresh student
    s_email = f"stu_serial_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": s_email,
        "password": "StudentPassword123!",
        "full_name": "Học Sinh Serial",
        "role": "STUDENT",
        "grade_level": 11
    })
    s_login = await client.post("/api/v1/auth/login", json={
        "email": s_email,
        "password": "StudentPassword123!"
    })
    s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    # 3. Start attempt
    start_res = await client.post(f"/api/v1/exams/{exam_id}/start", headers=s_headers)
    assert start_res.status_code == 200
    attempt_data = start_res.json()
    attempt_id = attempt_data["attempt_id"]
    q_data = attempt_data["questions"][0]
    q_id = q_data["question_id"]
    opt_a = q_data["options"][0]["id"]
    opt_b = q_data["options"][1]["id"]

    return s_headers, attempt_id, q_id, opt_a, opt_b


@pytest.mark.asyncio
async def test_backend_autosave_first_then_submit(client: httpx.AsyncClient):
    """
    Task B & C (Ordering A):
    Autosave obtains lock on ExamAttempt first and commits.
    Submit executes afterward, reads the persisted answer, and includes it in grading.
    """
    s_headers, attempt_id, q_id, opt_a, _ = await setup_test_exam_and_attempt(client)

    # 1. Autosave answer opt_a
    autosave_res = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_a, "client_version": 1}
    )
    assert autosave_res.status_code == 200
    assert autosave_res.json()["status"] == "SAVED"

    # 2. Submit attempt
    submit_res = await client.post(
        f"/api/v1/exams/attempts/{attempt_id}/submit",
        headers=s_headers
    )
    assert submit_res.status_code == 200
    sub_data = submit_res.json()
    assert sub_data["status"] in ["SUBMITTED", "GRADED", "COMPLETED"]
    # Question has points awarded from the committed autosave
    assert sub_data["correct_answers_count"] + sub_data["wrong_answers_count"] == 1
    assert sub_data["skipped_answers_count"] == 0


@pytest.mark.asyncio
async def test_backend_submit_first_then_autosave_rejected(client: httpx.AsyncClient):
    """
    Task B & C (Ordering B):
    Submit obtains lock on ExamAttempt first, transitions status to SUBMITTED/GRADED, and commits.
    Autosave executes afterward and is rejected with HTTP 403 Forbidden.
    Graded result remains strictly unchanged.
    """
    s_headers, attempt_id, q_id, opt_a, _ = await setup_test_exam_and_attempt(client)

    # 1. Submit attempt without answers
    submit_res = await client.post(
        f"/api/v1/exams/attempts/{attempt_id}/submit",
        headers=s_headers
    )
    assert submit_res.status_code == 200
    initial_score = submit_res.json()["total_score"]
    assert submit_res.json()["status"] in ["SUBMITTED", "GRADED", "COMPLETED"]

    # 2. Autosave attempt arrives afterward -> MUST be rejected with HTTP 403
    late_save = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_a, "client_version": 1}
    )
    assert late_save.status_code == 403
    assert "đã nộp hoặc kết thúc" in late_save.json()["detail"]

    # 3. Verify attempt result is completely unchanged
    chk_res = await client.get(
        f"/api/v1/exams/attempts/{attempt_id}",
        headers=s_headers
    )
    assert chk_res.status_code == 200
    assert chk_res.json()["status"] in ["SUBMITTED", "GRADED", "COMPLETED"]
    # No answer row was created after submit
    assert q_id not in chk_res.json().get("saved_answers", {})


@pytest.mark.asyncio
async def test_backend_concurrent_autosave_and_submit_gather(client: httpx.AsyncClient):
    """
    Task B & C (Concurrent Gather):
    Executes simultaneous autosave and submit requests using asyncio.gather.
    Under strict transaction serialization:
    - Either Autosave wins: Autosave 200 SAVED, Submit 200 GRADED (answer included).
    - Or Submit wins: Submit 200 GRADED, Autosave 403 Forbidden (attempt closed).
    - No 500 internal server error or corrupted state.
    """
    s_headers, attempt_id, q_id, opt_a, _ = await setup_test_exam_and_attempt(client)

    req_autosave = client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_a, "client_version": 1}
    )
    req_submit = client.post(
        f"/api/v1/exams/attempts/{attempt_id}/submit",
        headers=s_headers
    )

    res_autosave, res_submit = await asyncio.gather(req_autosave, req_submit)

    # Submit must ALWAYS succeed (HTTP 200)
    assert res_submit.status_code == 200, f"Submit failed: {res_submit.text}"
    submit_data = res_submit.json()

    # Autosave must either succeed (200 SAVED) or be rejected (403 Forbidden)
    assert res_autosave.status_code in [200, 403], f"Unexpected autosave status: {res_autosave.status_code}"

    if res_autosave.status_code == 200:
        # Autosave serialized before submit: answer was included in grading
        assert res_autosave.json()["status"] == "SAVED"
        assert submit_data["skipped_answers_count"] == 0
    else:
        # Submit serialized before autosave: autosave was rejected
        assert "đã nộp hoặc kết thúc" in res_autosave.json()["detail"]
