import pytest
import httpx
import uuid
import json
from datetime import datetime, timezone, timedelta
from app.modules.auth.models import UserRole


@pytest.mark.asyncio
async def test_short_answer_confidentiality_and_validation(client: httpx.AsyncClient):
    """
    TASK A & F:
    - Validation: SHORT_ANSWER without correct options is rejected with 422.
    - Confidentiality: Active exam payload strips options for SHORT_ANSWER (options == []).
    - Grading & Review: Auto-grades normalized answer and exposes correct_answer_texts in review.
    """
    # 1. Login Teacher
    t_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    assert t_login.status_code == 200
    t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

    # 2. Validation check: SHORT_ANSWER with NO correct option must fail (422)
    invalid_short_q = {
        "content": "Thủ đô của Việt Nam là gì?",
        "question_type": "SHORT_ANSWER",
        "difficulty_level": "RECOGNITION",
        "subject_id": "toan-11",
        "grade_id": 11,
        "options": [
            {"option_key": "A", "content": "Hà Nội", "is_correct": False}
        ]
    }
    fail_q_res = await client.post("/api/v1/questions", headers=t_headers, json=invalid_short_q)
    assert fail_q_res.status_code == 422, f"Expected 422 validation error, got {fail_q_res.status_code}"

    # 3. Create valid SHORT_ANSWER question with correct option
    valid_short_q = {
        "content": "Thủ đô của Việt Nam là gì?",
        "question_type": "SHORT_ANSWER",
        "difficulty_level": "RECOGNITION",
        "subject_id": "toan-11",
        "grade_id": 11,
        "explanation": "Hà Nội là thủ đô của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam.",
        "options": [
            {"option_key": "A", "content": "Hà Nội", "is_correct": True}
        ]
    }
    q_res = await client.post("/api/v1/questions", headers=t_headers, json=valid_short_q)
    assert q_res.status_code == 201
    q_data = q_res.json()
    q_id = q_data["id"]

    # 4. Create Exam and add SHORT_ANSWER question
    exam_payload = {
        "title": f"Đề Thi Tự Luận Ngắn {uuid.uuid4().hex[:6]}",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 30,
        "total_points": 10.0,
        "passing_points": 5.0,
        "allow_review": True,
        "status": "DRAFT"
    }
    exam_res = await client.post("/api/v1/exams", headers=t_headers, json=exam_payload)
    assert exam_res.status_code == 201
    exam_id = exam_res.json()["id"]

    await client.post(
        f"/api/v1/exams/{exam_id}/questions",
        headers=t_headers,
        json={"question_id": q_id, "points": 10.0, "order_index": 1}
    )
    pub_res = await client.post(f"/api/v1/exams/{exam_id}/publish", headers=t_headers)
    assert pub_res.status_code == 200

    # 5. Register fresh student & start attempt
    s_email = f"stu_short_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": s_email, "password": "StudentPassword123!", "full_name": "Học Sinh Tự Luận", "role": "STUDENT", "grade_level": 11
    })
    s_login = await client.post("/api/v1/auth/login", json={"email": s_email, "password": "StudentPassword123!"})
    s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    start_res = await client.post(f"/api/v1/exams/{exam_id}/start", headers=s_headers)
    assert start_res.status_code == 200
    start_data = start_res.json()
    attempt_id = start_data["attempt_id"]

    # CRITICAL CONFIDENTIALITY ASSERTION:
    # Student MUST NOT see options or answers for SHORT_ANSWER question
    target_q = next((q for q in start_data["questions"] if q["question_id"] == q_id), None)
    assert target_q is not None
    assert target_q["question_type"] == "SHORT_ANSWER"
    assert len(target_q["options"]) == 0, f"LEAK: SHORT_ANSWER exposed options: {target_q['options']}"
    assert "Hà Nội" not in json.dumps(target_q), "LEAK: Solution text 'Hà Nội' leaked in student question snapshot!"

    # 6. Student answers via autosave
    save_res = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"answer_text": "  hà nội  ", "client_version": 1}
    )
    assert save_res.status_code == 200
    assert save_res.json()["status"] == "SAVED"

    # 7. Student submits attempt
    sub_res = await client.post(f"/api/v1/exams/attempts/{attempt_id}/submit", headers=s_headers)
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["total_score"] == 10.0
    assert sub_data["correct_answers_count"] == 1
    assert sub_data["is_passed"] is True

    # 8. Student reviews attempt
    rev_res = await client.get(f"/api/v1/exams/attempts/{attempt_id}/review", headers=s_headers)
    assert rev_res.status_code == 200
    rev_data = rev_res.json()
    assert rev_data["review_allowed"] is True
    assert len(rev_data["question_reviews"]) == 1
    rev_q = rev_data["question_reviews"][0]
    assert rev_q["question_type"] == "SHORT_ANSWER"
    assert rev_q["is_correct"] is True
    assert rev_q["student_answer_text"] == "  hà nội  "
    assert "Hà Nội" in rev_q["correct_answer_texts"]


@pytest.mark.asyncio
async def test_student_answers_unique_constraint_and_autosave_versions(client: httpx.AsyncClient):
    """
    TASK B & C:
    - Verifies optimistic concurrency and atomic versioning on student_answers.
    - Prevents stale autosaves from overwriting newer answers.
    """
    t_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

    # Teacher creates an exam
    exam_res = await client.post("/api/v1/exams", headers=t_headers, json={
        "title": f"Đề Test Autosave {uuid.uuid4().hex[:6]}",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 30,
        "total_points": 10.0,
        "passing_points": 5.0,
        "status": "DRAFT"
    })
    exam_id = exam_res.json()["id"]
    await client.post(f"/api/v1/exams/{exam_id}/questions", headers=t_headers, json={"question_id": "q-toan11-01", "points": 10.0, "order_index": 1})
    await client.post(f"/api/v1/exams/{exam_id}/publish", headers=t_headers)

    # Fresh student starts attempt
    s_email = f"stu_autosave_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": s_email, "password": "StudentPassword123!", "full_name": "Học Sinh Autosave", "role": "STUDENT", "grade_level": 11
    })
    s_login = await client.post("/api/v1/auth/login", json={"email": s_email, "password": "StudentPassword123!"})
    s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    start_res = await client.post(f"/api/v1/exams/{exam_id}/start", headers=s_headers)
    assert start_res.status_code == 200
    att_data = start_res.json()
    attempt_id = att_data["attempt_id"]
    q = att_data["questions"][0]
    q_id = q["question_id"]
    opt1_id = q["options"][0]["id"]
    opt2_id = q["options"][1]["id"]

    # Save version 1 with opt1
    save1 = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt1_id, "client_version": 1}
    )
    assert save1.status_code == 200
    v1 = save1.json()["version"]
    assert v1 >= 1

    # Save version 2 with opt2
    save2 = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt2_id, "client_version": v1 + 1}
    )
    assert save2.status_code == 200
    v2 = save2.json()["version"]
    assert v2 > v1

    # Stale request arriving late with version 1 and opt1 -> must be discarded / not overwrite opt2
    save_stale = await client.put(
        f"/api/v1/exams/attempts/{attempt_id}/answers/{q_id}",
        headers=s_headers,
        json={"selected_option_id": opt1_id, "client_version": 1}
    )
    assert save_stale.status_code == 200

    # Verify attempt state: answer remains opt2 with version v2
    att_get = await client.get(f"/api/v1/exams/attempts/{attempt_id}", headers=s_headers)
    assert att_get.status_code == 200
    saved = att_get.json()["saved_answers"][q_id]
    assert saved["selected_option_id"] == opt2_id
    assert saved["version"] == v2


@pytest.mark.asyncio
async def test_assignment_policy_enforcement(client: httpx.AsyncClient):
    """
    TASK D:
    - If attempt belongs to an assignment, assignment policies override exam policies.
    - Case 1: Exam allow_review=True, Assignment allow_review=False -> 403 on review.
    - Case 2: Exam allow_review=False, Assignment allow_review=True -> 200 on review.
    """
    # 1. Login Teacher
    t_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

    # 2. Create Exam with allow_review = True
    exam1_res = await client.post("/api/v1/exams", headers=t_headers, json={
        "title": f"Đề Review True {uuid.uuid4().hex[:6]}",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 30,
        "total_points": 10.0,
        "passing_points": 5.0,
        "allow_review": True,
        "status": "DRAFT"
    })
    exam1_id = exam1_res.json()["id"]
    await client.post(f"/api/v1/exams/{exam1_id}/questions", headers=t_headers, json={"question_id": "q-toan11-01", "points": 10.0, "order_index": 1})
    await client.post(f"/api/v1/exams/{exam1_id}/publish", headers=t_headers)

    # 3. Create Classroom & Student
    cls_res = await client.post("/api/v1/classrooms", headers=t_headers, json={
        "name": f"Lớp Kiểm Thử Chính Sách {uuid.uuid4().hex[:6]}",
        "grade_id": 11
    })
    classroom_id = cls_res.json()["id"]
    join_code = cls_res.json()["code"]

    stu_email = f"stu_policy_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": stu_email, "password": "StudentPassword123!", "full_name": "Học Sinh Chính Sách", "role": "STUDENT", "grade_level": 11
    })
    s_login = await client.post("/api/v1/auth/login", json={"email": stu_email, "password": "StudentPassword123!"})
    s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    # Student joins classroom
    await client.post("/api/v1/classrooms/join", headers=s_headers, json={"code": join_code})

    # 4. Create Assignment with allow_review = False (Strictly forbidding review)
    now = datetime.now(timezone.utc)
    asg1_res = await client.post(f"/api/v1/classrooms/{classroom_id}/assignments", headers=t_headers, json={
        "title": "BTVN Không Cho Xem Lời Giải",
        "exam_id": exam1_id,
        "open_date": (now - timedelta(hours=1)).isoformat(),
        "due_date": (now + timedelta(days=2)).isoformat(),
        "allow_review": False,
        "allow_late_submission": False,
        "max_attempts": 1,
        "status": "PUBLISHED"
    })
    asg1_id = asg1_res.json()["id"]

    # 5. Student starts assignment attempt
    start_asg1 = await client.post(f"/api/v1/assignments/{asg1_id}/start", headers=s_headers)
    assert start_asg1.status_code == 200
    att1_id = start_asg1.json()["attempt_id"]

    # Student submits
    sub1 = await client.post(f"/api/v1/exams/attempts/{att1_id}/submit", headers=s_headers)
    assert sub1.status_code == 200
    assert sub1.json()["review_allowed"] is False
    assert sub1.json()["question_reviews"] is None

    # Student tries to review directly via /exams/attempts/{id}/review -> MUST BE 403 FORBIDDEN!
    rev1 = await client.get(f"/api/v1/exams/attempts/{att1_id}/review", headers=s_headers)
    assert rev1.status_code == 403, f"Expected 403 Forbidden due to assignment policy, got {rev1.status_code}"

    # 6. Case 2: Exam allow_review = False, Assignment allow_review = True
    exam2_res = await client.post("/api/v1/exams", headers=t_headers, json={
        "title": f"Đề Review False {uuid.uuid4().hex[:6]}",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 30,
        "total_points": 10.0,
        "passing_points": 5.0,
        "allow_review": False,
        "status": "DRAFT"
    })
    exam2_id = exam2_res.json()["id"]
    await client.post(f"/api/v1/exams/{exam2_id}/questions", headers=t_headers, json={"question_id": "q-toan11-01", "points": 10.0, "order_index": 1})
    await client.post(f"/api/v1/exams/{exam2_id}/publish", headers=t_headers)

    asg2_res = await client.post(f"/api/v1/classrooms/{classroom_id}/assignments", headers=t_headers, json={
        "title": "BTVN Cho Phép Xem Lời Giải",
        "exam_id": exam2_id,
        "open_date": (now - timedelta(hours=1)).isoformat(),
        "due_date": (now + timedelta(days=2)).isoformat(),
        "allow_review": True,
        "allow_late_submission": False,
        "max_attempts": 1,
        "status": "PUBLISHED"
    })
    asg2_id = asg2_res.json()["id"]

    start_asg2 = await client.post(f"/api/v1/assignments/{asg2_id}/start", headers=s_headers)
    assert start_asg2.status_code == 200
    att2_id = start_asg2.json()["attempt_id"]

    sub2 = await client.post(f"/api/v1/exams/attempts/{att2_id}/submit", headers=s_headers)
    assert sub2.status_code == 200
    assert sub2.json()["review_allowed"] is True

    # Review via endpoint must be 200 OK because Assignment policy allows it
    rev2 = await client.get(f"/api/v1/exams/attempts/{att2_id}/review", headers=s_headers)
    assert rev2.status_code == 200
    assert rev2.json()["review_allowed"] is True
    assert len(rev2.json()["question_reviews"]) >= 1


@pytest.mark.asyncio
async def test_all_four_question_types_e2e(client: httpx.AsyncClient):
    """
    TASK F: Complete coverage of all 4 question types:
    1. SINGLE_CHOICE
    2. MULTIPLE_CHOICE
    3. TRUE_FALSE
    4. SHORT_ANSWER
    """
    # 1. Login Teacher
    t_login = await client.post("/api/v1/auth/login", json={
        "email": "giaovien.toan@smartlearning.vn",
        "password": "TeacherPassword123!"
    })
    t_headers = {"Authorization": f"Bearer {t_login.json()['access_token']}"}

    # Create 4 questions of 4 distinct types
    # Q1: SINGLE_CHOICE
    q1_res = await client.post("/api/v1/questions", headers=t_headers, json={
        "content": "Phương trình sin(x) = 0 có nghiệm là gì?",
        "question_type": "SINGLE_CHOICE",
        "difficulty_level": "RECOGNITION",
        "subject_id": "toan-11",
        "grade_id": 11,
        "options": [
            {"option_key": "A", "content": "x = k*pi", "is_correct": True},
            {"option_key": "B", "content": "x = pi/2 + k*pi", "is_correct": False}
        ]
    })
    assert q1_res.status_code == 201
    q1_id = q1_res.json()["id"]

    # Q2: MULTIPLE_CHOICE
    q2_res = await client.post("/api/v1/questions", headers=t_headers, json={
        "content": "Các số nào sau đây là số nguyên tố chẵn hoặc lẻ?",
        "question_type": "MULTIPLE_CHOICE",
        "difficulty_level": "COMPREHENSION",
        "subject_id": "toan-11",
        "grade_id": 11,
        "options": [
            {"option_key": "A", "content": "2 (nguyên tố)", "is_correct": True},
            {"option_key": "B", "content": "3 (nguyên tố)", "is_correct": True},
            {"option_key": "C", "content": "4 (hợp số)", "is_correct": False}
        ]
    })
    assert q2_res.status_code == 201
    q2_id = q2_res.json()["id"]

    # Q3: TRUE_FALSE
    q3_res = await client.post("/api/v1/questions", headers=t_headers, json={
        "content": "Hàm số y = cos(x) là hàm số chẵn. Đúng hay Sai?",
        "question_type": "TRUE_FALSE",
        "difficulty_level": "RECOGNITION",
        "subject_id": "toan-11",
        "grade_id": 11,
        "options": [
            {"option_key": "A", "content": "Đúng", "is_correct": True},
            {"option_key": "B", "content": "Sai", "is_correct": False}
        ]
    })
    assert q3_res.status_code == 201
    q3_id = q3_res.json()["id"]

    # Q4: SHORT_ANSWER
    q4_res = await client.post("/api/v1/questions", headers=t_headers, json={
        "content": "Hàm số tuần hoàn với chu kỳ cơ bản bằng bao nhiêu rad đối với hàm sin(x)?",
        "question_type": "SHORT_ANSWER",
        "difficulty_level": "COMPREHENSION",
        "subject_id": "toan-11",
        "grade_id": 11,
        "options": [
            {"option_key": "A", "content": "2pi", "is_correct": True}
        ]
    })
    assert q4_res.status_code == 201
    q4_id = q4_res.json()["id"]

    # Create exam and assemble all 4 questions (2.5 points each = 10.0 points)
    exam_res = await client.post("/api/v1/exams", headers=t_headers, json={
        "title": f"Đề Tổng Hợp 4 Dạng Câu Hỏi {uuid.uuid4().hex[:6]}",
        "subject_id": "toan-11",
        "grade_id": 11,
        "duration_minutes": 45,
        "total_points": 10.0,
        "passing_points": 5.0,
        "allow_review": True,
        "status": "DRAFT"
    })
    assert exam_res.status_code == 201
    exam_id = exam_res.json()["id"]

    for idx, qid in enumerate([q1_id, q2_id, q3_id, q4_id], start=1):
        await client.post(f"/api/v1/exams/{exam_id}/questions", headers=t_headers, json={"question_id": qid, "points": 2.5, "order_index": idx})

    pub_res = await client.post(f"/api/v1/exams/{exam_id}/publish", headers=t_headers)
    assert pub_res.status_code == 200

    # 2. Fresh student starts exam
    s_email = f"stu_4types_{uuid.uuid4().hex[:6]}@smartlearning.vn"
    await client.post("/api/v1/auth/register", json={
        "email": s_email, "password": "StudentPassword123!", "full_name": "Học Sinh 4 Dạng", "role": "STUDENT", "grade_level": 11
    })
    s_login = await client.post("/api/v1/auth/login", json={"email": s_email, "password": "StudentPassword123!"})
    s_headers = {"Authorization": f"Bearer {s_login.json()['access_token']}"}

    start_res = await client.post(f"/api/v1/exams/{exam_id}/start", headers=s_headers)
    assert start_res.status_code == 200
    att_data = start_res.json()
    attempt_id = att_data["attempt_id"]
    q_map = {q["question_id"]: q for q in att_data["questions"]}

    # Verify SHORT_ANSWER has empty options in student payload
    assert len(q_map[q4_id]["options"]) == 0

    # 3. Autosave answers for each type (select by content to handle option shuffling)
    # Q1: SINGLE_CHOICE
    q1_opt = next(o["id"] for o in q_map[q1_id]["options"] if o["content"] == "x = k*pi")
    await client.put(f"/api/v1/exams/attempts/{attempt_id}/answers/{q1_id}", headers=s_headers, json={"selected_option_id": q1_opt})

    # Q2: MULTIPLE_CHOICE (select both correct options A and B by content)
    q2_opts = [o["id"] for o in q_map[q2_id]["options"] if o["content"] in ["2 (nguyên tố)", "3 (nguyên tố)"]]
    await client.put(f"/api/v1/exams/attempts/{attempt_id}/answers/{q2_id}", headers=s_headers, json={"selected_option_ids": q2_opts})

    # Q3: TRUE_FALSE
    q3_opt = next(o["id"] for o in q_map[q3_id]["options"] if o["content"] == "Đúng")
    await client.put(f"/api/v1/exams/attempts/{attempt_id}/answers/{q3_id}", headers=s_headers, json={"selected_option_id": q3_opt})

    # Q4: SHORT_ANSWER
    await client.put(f"/api/v1/exams/attempts/{attempt_id}/answers/{q4_id}", headers=s_headers, json={"answer_text": "2pi"})

    # 4. Submit attempt
    sub_res = await client.post(f"/api/v1/exams/attempts/{attempt_id}/submit", headers=s_headers)
    assert sub_res.status_code == 200
    res = sub_res.json()

    assert res["status"] == "GRADED"
    assert res["total_score"] == 10.0
    assert res["correct_answers_count"] == 4
    assert res["wrong_answers_count"] == 0
    assert res["skipped_answers_count"] == 0
    assert res["accuracy_percentage"] == 100.0
    assert res["is_passed"] is True

    # 5. Review attempt
    rev_res = await client.get(f"/api/v1/exams/attempts/{attempt_id}/review", headers=s_headers)
    assert rev_res.status_code == 200
    rev_items = rev_res.json()["question_reviews"]
    assert len(rev_items) == 4

    rev_map = {r["question_id"]: r for r in rev_items}
    assert rev_map[q1_id]["is_correct"] is True
    assert rev_map[q1_id]["question_type"] == "SINGLE_CHOICE"

    assert rev_map[q2_id]["is_correct"] is True
    assert rev_map[q2_id]["question_type"] == "MULTIPLE_CHOICE"

    assert rev_map[q3_id]["is_correct"] is True
    assert rev_map[q3_id]["question_type"] == "TRUE_FALSE"

    assert rev_map[q4_id]["is_correct"] is True
    assert rev_map[q4_id]["question_type"] == "SHORT_ANSWER"
    assert rev_map[q4_id]["student_answer_text"] == "2pi"
    assert "2pi" in rev_map[q4_id]["correct_answer_texts"]
