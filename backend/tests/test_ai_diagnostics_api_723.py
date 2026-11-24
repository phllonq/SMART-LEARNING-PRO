"""
API Integration Tests for AI Diagnostics — Phase 7.2.3
SMART LEARNING PRO

Endpoint: POST /api/v1/ai/diagnostics/wrong-answer

Test Matrix (30 Cases):
1-4:   Authentication (Anonymous, Valid Student, Teacher Forbidden, Admin Forbidden)
5-10:  Authorization (Cross-student IDOR, Nonexistent attempt, Question not in attempt,
       In-progress attempt, Correct answer, Terminal attempt)
11-14: Request Validation (Invalid UUID, Missing fields, Disallowed extra fields, Spoofing rejection)
15-20: AI Error Mapping (Timeout 504, Unavailable 503, Malformed 502, Upstream 503,
       Grading missing 422, Internal error without trace leak)
21-24: Read-Only Invariants (ExamAttempt, StudentAnswer, ExamResult, Question unchanged)
25-27: Cache & Idempotency (Repeat hit, Single generation on miss, Pre-cache ownership enforcement)
28-30: Response Contract & Security (Schema validation, Detail envelope, Zero secret/stack leak)
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import httpx
import pytest
from sqlalchemy import select

from app.core.cache import CacheService
from app.core.database import AsyncSessionLocal
from app.core.security import create_access_token
from app.main import app
from app.modules.ai_engine.contracts import NormalizedChatRequest, NormalizedChatResponse
from app.modules.ai_engine.diagnostics.dependencies import get_diagnostic_service
from app.modules.ai_engine.diagnostics.exceptions import (
    AIMalformedOutputException,
    AIProviderUnavailableException,
    AITimeoutException,
)
from app.modules.ai_engine.diagnostics.prompts import PROMPT_VERSION
from app.modules.ai_engine.diagnostics.schemas import (
    ErrorCategory,
    WrongAnswerDiagnosticResponse,
)
from app.modules.ai_engine.diagnostics.service import WrongAnswerDiagnosticService
from app.modules.ai_engine.exceptions import (
    AIMalformedResponseError,
    AIRateLimitError,
    AIServerError,
    AITimeoutError,
)
from app.modules.ai_engine.providers.mock import MockAIProvider
from app.modules.auth.models import User, UserRole
from app.modules.exams.models import (
    AttemptStatus,
    Exam,
    ExamAttempt,
    ExamQuestion,
    ExamResult,
    ExamStatus,
    StudentAnswer,
)
from app.modules.questions.models import (
    DifficultyLevel,
    Question,
    QuestionOption,
    QuestionType,
)

VALID_AI_JSON = json.dumps({
    "error_category": "CALCULATION_ERROR",
    "error_summary": "Lỗi tính toán sai số học trong bước nhân.",
    "misconception_analysis": "Học sinh hiểu đúng công thức f'(x) nhưng nhầm lẫn phép nhân 2*2=5.",
    "step_by_step_guidance": "1. Viết lại f'(x) = 2x.\n2. Thay x=2 được 2*(2) = 4.\n3. Đối chiếu đáp án đúng.",
    "key_takeaway": "Cần kiểm tra kỹ các phép tính nhân cộng số học cơ bản.",
    "suggested_review": "Đại số: Phép tính cơ bản"
}, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Database Fixture Helpers
# ---------------------------------------------------------------------------

async def _seed_test_world() -> Dict[str, Any]:
    """Seed users of various roles and an exam attempt with a wrong answer."""
    async with AsyncSessionLocal() as session:
        # 1. Student 1 (Owner)
        s1 = User(
            id=str(uuid.uuid4()),
            email=f"student1_{uuid.uuid4().hex[:6]}@smartlearning.vn",
            hashed_password="hash",
            full_name="Nguyễn Văn Học Sinh",
            role=UserRole.STUDENT.value,
            is_active=True,
            is_verified=True,
            grade_level=11,
        )
        # 2. Student 2 (Attacker / Other student)
        s2 = User(
            id=str(uuid.uuid4()),
            email=f"student2_{uuid.uuid4().hex[:6]}@smartlearning.vn",
            hashed_password="hash",
            full_name="Trần Thị Học Sinh 2",
            role=UserRole.STUDENT.value,
            is_active=True,
            is_verified=True,
            grade_level=11,
        )
        # 3. Teacher
        teacher = User(
            id=str(uuid.uuid4()),
            email=f"teacher_{uuid.uuid4().hex[:6]}@smartlearning.vn",
            hashed_password="hash",
            full_name="Thầy Giáo Viên",
            role=UserRole.TEACHER.value,
            is_active=True,
            is_verified=True,
        )
        # 4. Admin
        admin = User(
            id=str(uuid.uuid4()),
            email=f"admin_{uuid.uuid4().hex[:6]}@smartlearning.vn",
            hashed_password="hash",
            full_name="Quản Trị Viên",
            role=UserRole.ADMIN.value,
            is_active=True,
            is_verified=True,
        )
        session.add_all([s1, s2, teacher, admin])
        await session.flush()

        # 5. Question 1 (Wrong Answer in Attempt)
        q1 = Question(
            id=str(uuid.uuid4()),
            question_type=QuestionType.SINGLE_CHOICE.value,
            content="Tính đạo hàm của f(x) = x^2 tại x = 2.",
            difficulty_level=DifficultyLevel.COMPREHENSION.value,
            explanation="Ta có f'(x) = 2x, suy ra f'(2) = 4.",
        )
        session.add(q1)
        await session.flush()

        opt_a = QuestionOption(
            id=str(uuid.uuid4()),
            question_id=q1.id,
            option_key="A",
            content="4",
            is_correct=True,
            order_index=1,
        )
        opt_b = QuestionOption(
            id=str(uuid.uuid4()),
            question_id=q1.id,
            option_key="B",
            content="5",
            is_correct=False,
            order_index=2,
        )
        session.add_all([opt_a, opt_b])

        # 6. Question 2 (Correct Answer in Attempt)
        q2 = Question(
            id=str(uuid.uuid4()),
            question_type=QuestionType.SINGLE_CHOICE.value,
            content="Tập xác định của hàm số y = 1/x là gì?",
            difficulty_level=DifficultyLevel.RECOGNITION.value,
            explanation="Mẫu số x phải khác 0.",
        )
        session.add(q2)
        await session.flush()

        opt2_a = QuestionOption(
            id=str(uuid.uuid4()),
            question_id=q2.id,
            option_key="A",
            content="R \\ {0}",
            is_correct=True,
            order_index=1,
        )
        session.add(opt2_a)

        # 7. Exam
        exam = Exam(
            id=str(uuid.uuid4()),
            title="Đề Thi Khảo Sát Toán 11",
            duration_minutes=45,
            total_points=10.0,
            passing_points=5.0,
            status=ExamStatus.PUBLISHED.value,
            is_published=True,
        )
        session.add(exam)
        await session.flush()

        eq1 = ExamQuestion(id=str(uuid.uuid4()), exam_id=exam.id, question_id=q1.id, points=5.0, order_index=1)
        eq2 = ExamQuestion(id=str(uuid.uuid4()), exam_id=exam.id, question_id=q2.id, points=5.0, order_index=2)
        session.add_all([eq1, eq2])
        await session.flush()

        # Snapshots
        q_snapshot = [
            {"question_id": q1.id, "content": q1.content, "question_type": q1.question_type, "points": 5.0, "options": [{"id": opt_a.id, "option_key": "A", "content": "4"}, {"id": opt_b.id, "option_key": "B", "content": "5"}]},
            {"question_id": q2.id, "content": q2.content, "question_type": q2.question_type, "points": 5.0, "options": [{"id": opt2_a.id, "option_key": "A", "content": "R \\ {0}"}]},
        ]
        key_snapshot = [
            {"question_id": q1.id, "content": q1.content, "question_type": q1.question_type, "points": 5.0, "explanation": q1.explanation, "options": [{"id": opt_a.id, "option_key": "A", "content": "4", "is_correct": True}, {"id": opt_b.id, "option_key": "B", "content": "5", "is_correct": False}]},
            {"question_id": q2.id, "content": q2.content, "question_type": q2.question_type, "points": 5.0, "explanation": q2.explanation, "options": [{"id": opt2_a.id, "option_key": "A", "content": "R \\ {0}", "is_correct": True}]},
        ]

        # 8. Attempt for Student 1 (GRADED)
        attempt = ExamAttempt(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            student_id=s1.id,
            status=AttemptStatus.GRADED.value,
            started_at=datetime.now(timezone.utc),
            submitted_at=datetime.now(timezone.utc),
            score=5.0,
            maximum_score=10.0,
            questions_snapshot_json=json.dumps(q_snapshot, ensure_ascii=False),
            answer_key_snapshot_json=json.dumps(key_snapshot, ensure_ascii=False),
        )
        session.add(attempt)
        await session.flush()

        # Student 1 Answer for Question 1 (Wrong: chosen B)
        ans_wrong = StudentAnswer(
            id=str(uuid.uuid4()),
            attempt_id=attempt.id,
            question_id=q1.id,
            selected_option_id=opt_b.id,
            is_correct=False,
            points_awarded=0.0,
            version=1,
        )
        # Student 1 Answer for Question 2 (Correct: chosen A)
        ans_correct = StudentAnswer(
            id=str(uuid.uuid4()),
            attempt_id=attempt.id,
            question_id=q2.id,
            selected_option_id=opt2_a.id,
            is_correct=True,
            points_awarded=5.0,
            version=1,
        )
        session.add_all([ans_wrong, ans_correct])

        # 9. Result
        result = ExamResult(
            attempt_id=attempt.id,
            total_score=5.0,
            correct_answers_count=1,
            wrong_answers_count=1,
            accuracy_percentage=50.0,
        )
        session.add(result)

        # 10. Attempt in progress for Student 1 (IN_PROGRESS)
        attempt_inprogress = ExamAttempt(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            student_id=s1.id,
            status=AttemptStatus.IN_PROGRESS.value,
            started_at=datetime.now(timezone.utc),
            questions_snapshot_json=json.dumps(q_snapshot, ensure_ascii=False),
            answer_key_snapshot_json=json.dumps(key_snapshot, ensure_ascii=False),
        )
        session.add(attempt_inprogress)

        # Student 1 Answer in in-progress attempt
        ans_inprogress = StudentAnswer(
            id=str(uuid.uuid4()),
            attempt_id=attempt_inprogress.id,
            question_id=q1.id,
            selected_option_id=opt_b.id,
            is_correct=False,
            points_awarded=0.0,
            version=1,
        )
        session.add(ans_inprogress)

        await session.commit()

        return {
            "s1": s1,
            "s2": s2,
            "teacher": teacher,
            "admin": admin,
            "exam": exam,
            "q1": q1,
            "q2": q2,
            "attempt": attempt,
            "ans_wrong": ans_wrong,
            "ans_correct": ans_correct,
            "attempt_inprogress": attempt_inprogress,
            "opt_a": opt_a,
            "opt_b": opt_b,
        }


def _auth_headers(user: User) -> Dict[str, str]:
    """Generate Authorization header with valid JWT token."""
    token = create_access_token({"sub": user.id, "type": "access"})
    return {"Authorization": f"Bearer {token}"}


def _make_mock_service(response_text: str = VALID_AI_JSON) -> WrongAnswerDiagnosticService:
    provider = MockAIProvider(
        default_text=response_text,
        model_name="mock-model-v1",
        simulated_input_tokens=150,
        simulated_output_tokens=80,
    )
    cache = CacheService()
    cache.redis_client = None  # in-memory for testing
    return WrongAnswerDiagnosticService(provider=provider, cache=cache)


# ===========================================================================
# 1. AUTHENTICATION TESTS (Cases 1 - 4)
# ===========================================================================

@pytest.mark.asyncio
async def test_auth_anonymous_request_rejected(client: httpx.AsyncClient):
    """Case 1: Anonymous request without Authorization header returns 401."""
    data = await _seed_test_world()
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", json=payload)
    assert resp.status_code == 401
    assert "detail" in resp.json()


@pytest.mark.asyncio
async def test_auth_valid_student_request_accepted(client: httpx.AsyncClient):
    """Case 2: Authenticated STUDENT request with their own wrong answer returns 200 OK."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    # Override service with mock provider to ensure deterministic offline execution
    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 200
        body = resp.json()
        assert body["cached"] is False
        assert body["diagnostic"]["error_category"] == "CALCULATION_ERROR"
        assert body["diagnostic"]["error_summary"] != ""
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_auth_teacher_request_forbidden(client: httpx.AsyncClient):
    """Case 3: TEACHER role is restricted from diagnostic endpoint, returns 403 Forbidden."""
    data = await _seed_test_world()
    headers = _auth_headers(data["teacher"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
    assert resp.status_code == 403
    assert "chỉ dành riêng cho học sinh" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auth_admin_not_bypass_ownership(client: httpx.AsyncClient):
    """Case 4: ADMIN role does not bypass STUDENT role check, returns 403 Forbidden."""
    data = await _seed_test_world()
    headers = _auth_headers(data["admin"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
    assert resp.status_code == 403
    assert "chỉ dành riêng cho học sinh" in resp.json()["detail"]


# ===========================================================================
# 2. AUTHORIZATION TESTS (Cases 5 - 10)
# ===========================================================================

@pytest.mark.asyncio
async def test_authz_student_cannot_access_other_student_attempt(client: httpx.AsyncClient):
    """Case 5: Student 2 attempting to access Student 1's attempt returns 403 Forbidden."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s2"])  # Student 2 tries to access Student 1's attempt
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 403
        assert "Bạn không phải chủ sở hữu" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_authz_nonexistent_attempt(client: httpx.AsyncClient):
    """Case 6: Nonexistent attempt_id returns 404 Not Found."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    nonexistent_attempt_id = str(uuid.uuid4())
    payload = {"attempt_id": nonexistent_attempt_id, "question_id": data["q1"].id}

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 404
        assert "không tồn tại" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_authz_question_not_in_attempt(client: httpx.AsyncClient):
    """Case 7: Question ID not in the attempt returns 404 Not Found."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    alien_question_id = str(uuid.uuid4())
    payload = {"attempt_id": data["attempt"].id, "question_id": alien_question_id}

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 404
        assert "không thuộc về bài thi" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_authz_attempt_in_progress_rejected(client: httpx.AsyncClient):
    """Case 8: Attempt with IN_PROGRESS status returns 400 Bad Request."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt_inprogress"].id, "question_id": data["q1"].id}

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 400
        assert "chưa kết thúc" in resp.json()["detail"] or "IN_PROGRESS" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_authz_question_already_correct_rejected(client: httpx.AsyncClient):
    """Case 9: Correct answer (Question 2) cannot be diagnosed, returns 400 Bad Request."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q2"].id}

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 400
        assert "đã được trả lời chính xác" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_authz_terminal_attempt_accepted(client: httpx.AsyncClient):
    """Case 10: Attempt in terminal status (SUBMITTED / GRADED) is accepted."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


# ===========================================================================
# 3. REQUEST VALIDATION TESTS (Cases 11 - 14)
# ===========================================================================

@pytest.mark.asyncio
async def test_validation_invalid_uuid_rejected(client: httpx.AsyncClient):
    """Case 11: Invalid UUID format returns 422 Unprocessable Entity."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": "not-a-valid-uuid", "question_id": data["q1"].id}

    resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_validation_missing_required_fields(client: httpx.AsyncClient):
    """Case 12: Missing attempt_id or question_id returns 422."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])

    resp1 = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json={"question_id": data["q1"].id})
    assert resp1.status_code == 422

    resp2 = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json={"attempt_id": data["attempt"].id})
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_validation_disallowed_extra_fields(client: httpx.AsyncClient):
    """Case 13: Payload with disallowed extra fields is rejected with 422 (extra='forbid')."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {
        "attempt_id": data["attempt"].id,
        "question_id": data["q1"].id,
        "unexpected_field": "hacker_data",
    }

    resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_validation_cannot_spoof_correctness(client: httpx.AsyncClient):
    """Case 14: Client cannot supply 'is_correct' or 'correct_answer' to override DB truth."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {
        "attempt_id": data["attempt"].id,
        "question_id": data["q1"].id,
        "is_correct": False,
        "correct_answer": "B",
    }

    resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
    assert resp.status_code == 422


# ===========================================================================
# 4. AI ERROR MAPPING TESTS (Cases 15 - 20)
# ===========================================================================

@pytest.mark.asyncio
async def test_ai_error_mapping_timeout_returns_504(client: httpx.AsyncClient):
    """Case 15: AI Provider timeout maps to HTTP 504 Gateway Timeout."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    provider = MockAIProvider(model_name="mock-model-v1")
    provider.error_to_raise = AITimeoutError("Simulated LLM network timeout")
    service = WrongAnswerDiagnosticService(provider=provider)
    app.dependency_overrides[get_diagnostic_service] = lambda: service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 504
        assert "Quá thời gian" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_ai_error_mapping_unavailable_returns_503(client: httpx.AsyncClient):
    """Case 16: AI Provider unavailable / rate limit maps to HTTP 503."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    provider = MockAIProvider(model_name="mock-model-v1")
    provider.error_to_raise = AIRateLimitError("Quota exhausted")
    service = WrongAnswerDiagnosticService(provider=provider)
    app.dependency_overrides[get_diagnostic_service] = lambda: service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 503
        assert "không khả dụng" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_ai_error_mapping_malformed_returns_502(client: httpx.AsyncClient):
    """Case 17: AI malformed response maps to HTTP 502 Bad Gateway."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    # Provider returning broken JSON
    provider = MockAIProvider(default_text="NOT JSON {broken", model_name="mock-model-v1")
    service = WrongAnswerDiagnosticService(provider=provider)
    app.dependency_overrides[get_diagnostic_service] = lambda: service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 502
        assert "không đúng cấu trúc" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_ai_error_mapping_upstream_error_returns_503(client: httpx.AsyncClient):
    """Case 18: Upstream server error (AIServerError) maps to HTTP 503."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    provider = MockAIProvider(model_name="mock-model-v1")
    provider.error_to_raise = AIServerError("Gemini internal server error 500")
    service = WrongAnswerDiagnosticService(provider=provider)
    app.dependency_overrides[get_diagnostic_service] = lambda: service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 503
        assert "không khả dụng" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_ai_error_mapping_domain_grading_unavailable_returns_422(client: httpx.AsyncClient):
    """Case 19: Missing grading result maps to HTTP 422 Unprocessable Entity."""
    data = await _seed_test_world()
    # Set student answer is_correct to None
    async with AsyncSessionLocal() as session:
        ans = await session.get(StudentAnswer, data["ans_wrong"].id)
        ans.is_correct = None
        await session.commit()

    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 422
        assert "chưa sẵn sàng" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_ai_error_mapping_unexpected_error_handled_safely(client: httpx.AsyncClient):
    """Case 20: Unexpected exception does not expose stack trace or crash server."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    # Simulate unexpected runtime error
    provider = MockAIProvider(model_name="mock-model-v1")
    provider.error_to_raise = RuntimeError("Fatal internal driver fault")
    service = WrongAnswerDiagnosticService(provider=provider)
    app.dependency_overrides[get_diagnostic_service] = lambda: service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        # Should be mapped cleanly to 503
        assert resp.status_code == 503
        body = resp.json()
        assert "detail" in body
        # Ensure no traceback or internal line leak in response body
        assert "Traceback" not in str(body)
        assert "RuntimeError" not in str(body)
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


# ===========================================================================
# 5. READ-ONLY INVARIANT TESTS (Cases 21 - 24)
# ===========================================================================

@pytest.mark.asyncio
async def test_readonly_invariant_attempt_unchanged(client: httpx.AsyncClient):
    """Case 21: ExamAttempt record is strictly identical before and after diagnostic API call."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    # Snapshot before
    async with AsyncSessionLocal() as session:
        att_before = await session.get(ExamAttempt, data["attempt"].id)
        score_before = att_before.score
        status_before = att_before.status
        submitted_before = att_before.submitted_at

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 200

        # Verify after
        async with AsyncSessionLocal() as session:
            att_after = await session.get(ExamAttempt, data["attempt"].id)
            assert att_after.score == score_before
            assert att_after.status == status_before
            assert att_after.submitted_at == submitted_before
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_readonly_invariant_student_answer_unchanged(client: httpx.AsyncClient):
    """Case 22: StudentAnswer record is strictly unchanged after diagnostic API call."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    async with AsyncSessionLocal() as session:
        ans_before = await session.get(StudentAnswer, data["ans_wrong"].id)
        is_corr_before = ans_before.is_correct
        points_before = ans_before.points_awarded
        ver_before = ans_before.version

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 200

        async with AsyncSessionLocal() as session:
            ans_after = await session.get(StudentAnswer, data["ans_wrong"].id)
            assert ans_after.is_correct == is_corr_before
            assert ans_after.points_awarded == points_before
            assert ans_after.version == ver_before
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_readonly_invariant_exam_result_unchanged(client: httpx.AsyncClient):
    """Case 23: ExamResult record is strictly unchanged after diagnostic API call."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    async with AsyncSessionLocal() as session:
        res = await session.execute(select(ExamResult).where(ExamResult.attempt_id == data["attempt"].id))
        res_before = res.scalar_one_or_none()
        assert res_before is not None
        score_before = res_before.total_score

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 200

        async with AsyncSessionLocal() as session:
            res = await session.execute(select(ExamResult).where(ExamResult.attempt_id == data["attempt"].id))
            res_after = res.scalar_one_or_none()
            assert res_after is not None
            assert res_after.total_score == score_before
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_readonly_invariant_canonical_question_unchanged(client: httpx.AsyncClient):
    """Case 24: Canonical question, explanation, and options are completely untouched."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    async with AsyncSessionLocal() as session:
        q_before = await session.get(Question, data["q1"].id)
        expl_before = q_before.explanation

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 200

        async with AsyncSessionLocal() as session:
            q_after = await session.get(Question, data["q1"].id)
            assert q_after.explanation == expl_before
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


# ===========================================================================
# 6. CACHE & IDEMPOTENCY TESTS (Cases 25 - 27)
# ===========================================================================

@pytest.mark.asyncio
async def test_cache_hit_on_repeat_request(client: httpx.AsyncClient):
    """Case 25: First call misses cache; second identical call hits cache with cached=True."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        # Call 1: Miss
        resp1 = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp1.status_code == 200
        assert resp1.json()["cached"] is False

        # Call 2: Hit
        resp2 = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp2.status_code == 200
        assert resp2.json()["cached"] is True
        assert resp2.json()["latency_ms"] == 0.0
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_cache_miss_calls_service_once(client: httpx.AsyncClient):
    """Case 26: On cache miss, provider is called exactly once."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    provider = MockAIProvider(default_text=VALID_AI_JSON, model_name="mock-model-v1", simulated_input_tokens=100, simulated_output_tokens=50)
    service = WrongAnswerDiagnosticService(provider=provider, cache=CacheService())
    app.dependency_overrides[get_diagnostic_service] = lambda: service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 200
        assert provider.call_count == 1
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_cache_hit_does_not_bypass_ownership(client: httpx.AsyncClient):
    """Case 27: Pre-cache authorization check prevents Student 2 from reading cached data of Student 1."""
    data = await _seed_test_world()
    headers1 = _auth_headers(data["s1"])
    headers2 = _auth_headers(data["s2"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        # Student 1 primes the cache
        resp1 = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers1, json=payload)
        assert resp1.status_code == 200

        # Student 2 makes request for the same attempt
        resp2 = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers2, json=payload)
        # MUST BE 403 Forbidden: Ownership is checked BEFORE cache lookup!
        assert resp2.status_code == 403
        assert "Bạn không phải chủ sở hữu" in resp2.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


# ===========================================================================
# 7. RESPONSE CONTRACT & SECURITY TESTS (Cases 28 - 30)
# ===========================================================================

@pytest.mark.asyncio
async def test_response_contract_matches_schema(client: httpx.AsyncClient):
    """Case 28: Response structure strictly validates against WrongAnswerDiagnosticResponse schema."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 200
        data_json = resp.json()
        validated = WrongAnswerDiagnosticResponse.model_validate(data_json)
        assert validated.prompt_version == PROMPT_VERSION
        assert validated.is_sufficient is True
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_response_does_not_expose_canonical_answer_if_forbidden(client: httpx.AsyncClient):
    """Case 29: Response provides conceptual guidance without exposing internal DB option IDs."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    mock_service = _make_mock_service()
    app.dependency_overrides[get_diagnostic_service] = lambda: mock_service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 200
        raw_text = resp.text
        # Ensure raw internal option UUIDs are not leaked in diagnostic payload
        assert data["opt_a"].id not in raw_text
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)


@pytest.mark.asyncio
async def test_response_does_not_leak_secrets_or_stack_trace(client: httpx.AsyncClient):
    """Case 30: Error responses never leak API keys, system paths, or Python tracebacks."""
    data = await _seed_test_world()
    headers = _auth_headers(data["s1"])
    payload = {"attempt_id": data["attempt"].id, "question_id": data["q1"].id}

    provider = MockAIProvider(model_name="mock-model-v1")
    provider.error_to_raise = AIServerError("Gemini Key secret_api_key_12345 expired at /home/user/backend")
    service = WrongAnswerDiagnosticService(provider=provider)
    app.dependency_overrides[get_diagnostic_service] = lambda: service

    try:
        resp = await client.post("/api/v1/ai/diagnostics/wrong-answer", headers=headers, json=payload)
        assert resp.status_code == 503
        body = resp.text
        assert "secret_api_key" not in body
        assert "/home/user" not in body
        assert "Traceback" not in body
    finally:
        app.dependency_overrides.pop(get_diagnostic_service, None)
