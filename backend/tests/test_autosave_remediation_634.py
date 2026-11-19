import pytest
import httpx
import uuid
from app.modules.auth.models import UserRole


@pytest.mark.asyncio
async def test_autosave_page_reload_consistency(client: httpx.AsyncClient):
    """
    Task A & F:
    Verifies that after simulating a page reload (F5) where client fetches
    the attempt from GET /attempts/{id}, the version counter is restored
    and subsequent autosave increments correctly without being silently ignored.
    """
    # 1. Login Teacher to setup exam
    t_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    assert t_login.status_code == 200
    t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

    exam_res = await client.post("/api/v1/exams", headers=t_headers, json={
        "title": f"Đề Reload Consistency {uuid.uuid4().hex[:6]}",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 45,
        "total_points": 10.0,
        "passing_points": 5.0,
        "status": "DRAFT"
    })
    assert exam_res.status_code == 201
    exam_id = exam_res.json()["id"]

    await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        headers=t_headers,
        json={"question_id": "q-toan11-01", "points": 10.0, "order_index": 1}
    )
    await client.post(f"/api/v1/exams/{exam_id}/publish", headers=t_headers)

    # 2. Register & login student
    s_email = f"stu_reload_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": s_email,
        "password": "StudentPassword123!",
        "full_name": "Học Sinh Reload",
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
    opt_c = q_data["options"][2]["id"]

    # 4. First save: choose opt_a (v1)
    res_v1 = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_a, "client_version": 1}
    )
    assert res_v1.status_code == 200
    data_v1 = res_v1.json()
    assert data_v1["status"] == "SAVED"
    assert data_v1["version"] == 1
    assert data_v1["selected_option_id"] == opt_a

    # 5. Second save: change to opt_b (v2)
    res_v2 = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_b, "client_version": 2, "expected_version": 1}
    )
    assert res_v2.status_code == 200
    data_v2 = res_v2.json()
    assert data_v2["status"] == "SAVED"
    assert data_v2["version"] == 2
    assert data_v2["selected_option_id"] == opt_b

    # 6. SIMULATE PAGE RELOAD (F5)
    # The client fetches GET /attempts/{attempt_id}
    reload_res = await client.get(f"/api/v1/exams/attempts/{attempt_id}", headers=s_headers)
    assert reload_res.status_code == 200
    reloaded_data = reload_res.json()
    assert q_id in reloaded_data["saved_answers"]
    saved_answer = reloaded_data["saved_answers"][q_id]
    assert saved_answer["version"] == 2
    assert saved_answer["selected_option_id"] == opt_b

    # Frontend restores versionCounters.current[q_id] = 2 from saved_answers[q_id]["version"]
    # Student now selects opt_c. Client sends expected_version=2, client_version=3
    res_v3 = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_c, "client_version": 3, "expected_version": 2}
    )
    assert res_v3.status_code == 200
    data_v3 = res_v3.json()
    assert data_v3["status"] == "SAVED"
    assert data_v3["version"] == 3
    assert data_v3["selected_option_id"] == opt_c

    # 7. Verify authoritative state in database has updated to opt_c
    verify_res = await client.get(f"/api/v1/exams/attempts/{attempt_id}", headers=s_headers)
    assert verify_res.status_code == 200
    final_saved = verify_res.json()["saved_answers"][q_id]
    assert final_saved["selected_option_id"] == opt_c
    assert final_saved["version"] == 3


@pytest.mark.asyncio
async def test_autosave_atomic_occ_and_version_conflict(client: httpx.AsyncClient):
    """
    Task B, C, E & F:
    Verifies database-level atomic conditional update (OCC):
    - When two requests with the same expected_version are executed,
      one succeeds with SAVED and increments version.
    - The conflicting second request receives VERSION_CONFLICT (not silent SAVED).
    - Client can synchronize to current authoritative version and retry.
    """
    t_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

    exam_res = await client.post("/api/v1/exams", headers=t_headers, json={
        "title": f"Đề OCC Conflict {uuid.uuid4().hex[:6]}",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 30,
        "total_points": 10.0,
        "passing_points": 5.0,
        "status": "DRAFT"
    })
    exam_id = exam_res.json()["id"]
    await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        headers=t_headers,
        json={"question_id": "q-toan11-01", "points": 10.0, "order_index": 1}
    )
    await client.post(f"/api/v1/exams/{exam_id}/publish", headers=t_headers)

    s_email = f"stu_occ_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": s_email,
        "password": "StudentPassword123!",
        "full_name": "Học Sinh OCC",
        "role": "STUDENT",
        "grade_level": 11
    })
    s_login = await client.post("/api/v1/auth/login", json={
        "email": s_email,
        "password": "StudentPassword123!"
    })
    s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    start_res = await client.post(f"/api/v1/exams/{exam_id}/start", headers=s_headers)
    att = start_res.json()
    attempt_id = att["attempt_id"]
    q_data = att["questions"][0]
    q_id = q_data["question_id"]
    opt_a = q_data["options"][0]["id"]
    opt_b = q_data["options"][1]["id"]
    opt_c = q_data["options"][2]["id"]

    # Seed baseline answer v1
    init_res = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_a, "client_version": 1}
    )
    assert init_res.status_code == 200
    assert init_res.json()["version"] == 1

    # Simulate two tabs both at version 1:
    # Tab 1 sends expected_version=1, client_version=2, selecting opt_b
    tab1_res = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_b, "expected_version": 1, "client_version": 2}
    )
    assert tab1_res.status_code == 200
    tab1_data = tab1_res.json()
    assert tab1_data["status"] == "SAVED"
    assert tab1_data["version"] == 2
    assert tab1_data["selected_option_id"] == opt_b

    # Tab 2 (stale) now also sends expected_version=1, client_version=2, selecting opt_c
    tab2_res = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_c, "expected_version": 1, "client_version": 2}
    )
    assert tab2_res.status_code == 200
    tab2_data = tab2_res.json()
    # MUST return VERSION_CONFLICT, not SAVED!
    assert tab2_data["status"] == "VERSION_CONFLICT"
    assert tab2_data["version"] == 2
    # Persisted answer remains opt_b from Tab 1
    assert tab2_data["selected_option_id"] == opt_b

    # Verify DB still has opt_b
    chk_res = await client.get(f"/api/v1/exams/attempts/{attempt_id}", headers=s_headers)
    assert chk_res.json()["saved_answers"][q_id]["selected_option_id"] == opt_b

    # Tab 2 receives VERSION_CONFLICT, syncs base to version 2, and retries with expected_version=2, client_version=3
    tab2_retry = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_c, "expected_version": 2, "client_version": 3}
    )
    assert tab2_retry.status_code == 200
    assert tab2_retry.json()["status"] == "SAVED"
    assert tab2_retry.json()["version"] == 3
    assert tab2_retry.json()["selected_option_id"] == opt_c


@pytest.mark.asyncio
async def test_autosave_stale_request_rejection(client: httpx.AsyncClient):
    """
    Task B & C:
    Verifies that when a request with client_version < current_version arrives,
    the server returns STALE_IGNORED and does NOT overwrite newer data.
    """
    t_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

    exam_res = await client.post("/api/v1/exams", headers=t_headers, json={
        "title": f"Đề Stale Test {uuid.uuid4().hex[:6]}",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 30,
        "total_points": 10.0,
        "passing_points": 5.0,
        "status": "DRAFT"
    })
    exam_id = exam_res.json()["id"]
    await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        headers=t_headers,
        json={"question_id": "q-toan11-01", "points": 10.0, "order_index": 1}
    )
    await client.post(f"/api/v1/exams/{exam_id}/publish", headers=t_headers)

    s_email = f"stu_stale_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": s_email,
        "password": "StudentPassword123!",
        "full_name": "Học Sinh Stale",
        "role": "STUDENT",
        "grade_level": 11
    })
    s_login = await client.post("/api/v1/auth/login", json={
        "email": s_email,
        "password": "StudentPassword123!"
    })
    s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    start_res = await client.post(f"/api/v1/exams/{exam_id}/start", headers=s_headers)
    attempt_id = start_res.json()["attempt_id"]
    q_data = start_res.json()["questions"][0]
    q_id = q_data["question_id"]
    opt_a = q_data["options"][0]["id"]
    opt_b = q_data["options"][1]["id"]

    # Save version 1
    await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_a, "client_version": 1}
    )

    # Save version 5
    v5_res = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_b, "client_version": 5, "expected_version": 1}
    )
    assert v5_res.status_code == 200
    assert v5_res.json()["status"] == "SAVED"
    assert v5_res.json()["version"] == 5

    # Out-of-order stale request with client_version=2 arriving now
    stale_res = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt_a, "client_version": 2}
    )
    assert stale_res.status_code == 200
    stale_data = stale_res.json()
    assert stale_data["status"] == "STALE_IGNORED"
    assert stale_data["version"] == 5
    assert stale_data["selected_option_id"] == opt_b

    # Verify attempt data is still opt_b at v5
    chk_res = await client.get(f"/api/v1/exams/attempts/{attempt_id}", headers=s_headers)
    assert chk_res.json()["saved_answers"][q_id]["selected_option_id"] == opt_b
    assert chk_res.json()["saved_answers"][q_id]["version"] == 5


@pytest.mark.asyncio
async def test_autosave_short_answer_lifecycle(client: httpx.AsyncClient):
    """
    Verifies SHORT_ANSWER debounced typing lifecycle:
    - Text updates version correctly.
    - Persisted text is returned in AutosaveAnswerResponse and GET /attempts/{id}.
    """
    t_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

    # Create short answer question
    q_res = await client.post("/api/v1/questions", headers=t_headers, json={
        "content": "2 + 2 bằng mấy?",
        "question_type": "SHORT_ANSWER",
        "difficulty_level": "RECOGNITION",
        "subject_id": "toan-11",
        "grade_id": 11,
        "options": [{"option_key": "A", "content": "4", "is_correct": True}]
    })
    assert q_res.status_code == 201
    q_id = q_res.json()["id"]

    exam_res = await client.post("/api/v1/exams", headers=t_headers, json={
        "title": f"Đề Short Autosave {uuid.uuid4().hex[:6]}",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 20,
        "total_points": 10.0,
        "passing_points": 5.0,
        "status": "DRAFT"
    })
    exam_id = exam_res.json()["id"]
    await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        headers=t_headers,
        json={"question_id": q_id, "points": 10.0, "order_index": 1}
    )
    await client.post(f"/api/v1/exams/{exam_id}/publish", headers=t_headers)

    s_email = f"stu_sa_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": s_email,
        "password": "StudentPassword123!",
        "full_name": "Học Sinh SA",
        "role": "STUDENT",
        "grade_level": 11
    })
    s_login = await client.post("/api/v1/auth/login", json={
        "email": s_email,
        "password": "StudentPassword123!"
    })
    s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    start_res = await client.post(f"/api/v1/exams/{exam_id}/start", headers=s_headers)
    attempt_id = start_res.json()["attempt_id"]

    # Student types "4"
    save_res = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"answer_text": "4", "client_version": 1}
    )
    assert save_res.status_code == 200
    save_data = save_res.json()
    assert save_data["status"] == "SAVED"
    assert save_data["answer_text"] == "4"
    assert save_data["version"] == 1

    # Student edits to "bốn"
    save_res2 = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"answer_text": "bốn", "expected_version": 1, "client_version": 2}
    )
    assert save_res2.status_code == 200
    save_data2 = save_res2.json()
    assert save_data2["status"] == "SAVED"
    assert save_data2["answer_text"] == "bốn"
    assert save_data2["version"] == 2
