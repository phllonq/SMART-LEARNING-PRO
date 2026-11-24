"""
Comprehensive Test Suite for Phase 7.2.2: Wrong Answer Diagnostic Service
SMART LEARNING PRO

Covers all 5 mandatory test areas:
1. Authorization:
   - Own attempt
   - Another student's attempt
   - Cross-tenant attempt
   - Unknown attempt
   - Question from another exam
   - Invalid question ID
2. Exam State:
   - IN_PROGRESS
   - SUBMITTED
   - AUTO_SUBMITTED
   - GRADED
   - Correct answer
   - Incorrect answer
   - Missing grading result
3. Read-Only Invariants:
   - ExamAttempt unchanged
   - Student answer unchanged
   - Score unchanged
   - Grading record unchanged
   - Question unchanged
4. AI Integration:
   - Valid response
   - Malformed JSON
   - Invalid category
   - Insufficient information
   - Provider unavailable
   - Timeout
   - Cancellation propagation
5. Cache & Concurrency:
   - Cache miss then cache hit
   - Cache expiration
   - Prompt version change
   - Authoritative answer fingerprint change
   - Redis unavailable fallback
   - Redis restart
   - Concurrent duplicate requests
   - Lock expiration
   - Lock release after failure
   - Cache isolation between tenants/users
"""

import asyncio
import json
import uuid
import pytest
from datetime import datetime, timezone
from typing import Dict, Any, Tuple
from unittest.mock import MagicMock, patch

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.cache import CacheService, InMemoryCache
from app.core.database import AsyncSessionLocal
from app.modules.ai_engine.contracts import (
    ChatMessage,
    NormalizedChatRequest,
    NormalizedChatResponse,
)
from app.modules.ai_engine.diagnostics.exceptions import (
    AIProviderUnavailableException,
    AITimeoutException,
    AIMalformedOutputException,
    AttemptNotFoundException,
    AttemptNotSubmittedException,
    CacheCoordinationException,
    DiagnosticUnauthorizedException,
    GradingUnavailableException,
    QuestionAlreadyCorrectException,
    QuestionNotInAttemptException,
)
from app.modules.ai_engine.diagnostics.prompts import PROMPT_VERSION
from app.modules.ai_engine.diagnostics.schemas import (
    DiagnosticDetail,
    ErrorCategory,
    WrongAnswerDiagnosticResponse,
)
from app.modules.ai_engine.diagnostics.service import (
    WrongAnswerDiagnosticService,
    ALLOWED_TERMINAL_STATUSES,
)
from app.modules.ai_engine.exceptions import (
    AIServerError,
    AITimeoutError,
    AIMalformedResponseError,
    AIAuthenticationError,
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


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------

VALID_AI_JSON = json.dumps({
    "error_category": "CALCULATION_ERROR",
    "error_summary": "Học sinh tính sai giá trị đạo hàm tại điểm x=2.",
    "misconception_analysis": "Học sinh hiểu đúng công thức f'(x) nhưng nhầm lẫn phép nhân 2*2=5.",
    "step_by_step_guidance": "1. Viết lại f'(x) = 2x.\n2. Thay x=2 được 2*(2) = 4.\n3. Đối chiếu đáp án đúng.",
    "key_takeaway": "Cần kiểm tra kỹ các phép tính nhân cộng số học cơ bản.",
    "suggested_review": "Đại số: Phép tính cơ bản"
}, ensure_ascii=False)

INSUFFICIENT_AI_JSON = json.dumps({
    "error_category": "INSUFFICIENT_INFORMATION",
    "error_summary": "Không có đủ cơ sở dữ liệu để xác định nguyên nhân lỗi sai.",
    "misconception_analysis": "Học sinh không để lại bước làm trung gian và câu hỏi chưa có giải thích chi tiết.",
    "step_by_step_guidance": "1. Xem lại bài giảng về đạo hàm.\n2. Thực hiện lại các bài tập tương tự.",
    "key_takeaway": "Cần ghi chép rõ các bước làm nháp.",
    "suggested_review": None
}, ensure_ascii=False)


def _make_mock_provider(response_text: str = VALID_AI_JSON) -> MockAIProvider:
    return MockAIProvider(
        default_text=response_text,
        model_name="mock-model-v1",
        simulated_input_tokens=150,
        simulated_output_tokens=80,
    )


async def _create_test_entities() -> Tuple[User, User, Exam, Question, ExamAttempt, StudentAnswer]:
    """Helper to create a standard test scenario in database."""
    async with AsyncSessionLocal() as session:
        # Student 1
        s1 = User(
            id=str(uuid.uuid4()),
            email=f"stu1_{uuid.uuid4().hex[:6]}@smartlearning.vn",
            hashed_password="hash",
            full_name="Nguyễn Văn A",
            role=UserRole.STUDENT.value,
            grade_level=11,
        )
        # Student 2
        s2 = User(
            id=str(uuid.uuid4()),
            email=f"stu2_{uuid.uuid4().hex[:6]}@smartlearning.vn",
            hashed_password="hash",
            full_name="Trần Thị B",
            role=UserRole.STUDENT.value,
            grade_level=11,
        )
        session.add_all([s1, s2])
        await session.flush()

        # Question
        q = Question(
            id=str(uuid.uuid4()),
            question_type=QuestionType.SINGLE_CHOICE.value,
            content="Tính đạo hàm của f(x) = x^2 tại x = 2.",
            difficulty_level=DifficultyLevel.COMPREHENSION.value,
            explanation="Ta có f'(x) = 2x, suy ra f'(2) = 4.",
        )
        session.add(q)
        await session.flush()

        opt_a = QuestionOption(
            id=str(uuid.uuid4()),
            question_id=q.id,
            option_key="A",
            content="4",
            is_correct=True,
            order_index=1,
        )
        opt_b = QuestionOption(
            id=str(uuid.uuid4()),
            question_id=q.id,
            option_key="B",
            content="5",
            is_correct=False,
            order_index=2,
        )
        session.add_all([opt_a, opt_b])
        await session.flush()

        # Exam
        exam = Exam(
            id=str(uuid.uuid4()),
            title="Đề Khảo Sát Toán 11",
            duration_minutes=45,
            total_points=10.0,
            passing_points=5.0,
            status=ExamStatus.PUBLISHED.value,
            is_published=True,
        )
        session.add(exam)
        await session.flush()

        eq = ExamQuestion(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            question_id=q.id,
            points=10.0,
            order_index=1,
        )
        session.add(eq)
        await session.flush()

        # Snapshot structure
        sanitized_snapshot = [{
            "question_id": q.id,
            "content": q.content,
            "question_type": q.question_type,
            "points": 10.0,
            "options": [
                {"id": opt_a.id, "option_key": "A", "content": "4"},
                {"id": opt_b.id, "option_key": "B", "content": "5"},
            ]
        }]
        answer_key_snapshot = [{
            "question_id": q.id,
            "content": q.content,
            "question_type": q.question_type,
            "points": 10.0,
            "explanation": q.explanation,
            "options": [
                {"id": opt_a.id, "option_key": "A", "content": "4", "is_correct": True},
                {"id": opt_b.id, "option_key": "B", "content": "5", "is_correct": False},
            ]
        }]

        # Attempt for Student 1
        attempt = ExamAttempt(
            id=str(uuid.uuid4()),
            exam_id=exam.id,
            student_id=s1.id,
            status=AttemptStatus.GRADED.value,
            started_at=datetime.now(timezone.utc),
            submitted_at=datetime.now(timezone.utc),
            score=0.0,
            maximum_score=10.0,
            questions_snapshot_json=json.dumps(sanitized_snapshot, ensure_ascii=False),
            answer_key_snapshot_json=json.dumps(answer_key_snapshot, ensure_ascii=False),
        )
        session.add(attempt)
        await session.flush()

        # Incorrect student answer (selected B instead of A)
        ans = StudentAnswer(
            id=str(uuid.uuid4()),
            attempt_id=attempt.id,
            question_id=q.id,
            selected_option_id=opt_b.id,
            is_correct=False,
            points_awarded=0.0,
            version=1,
        )
        session.add(ans)

        # ExamResult
        res = ExamResult(
            attempt_id=attempt.id,
            total_score=0.0,
            correct_answers_count=0,
            wrong_answers_count=1,
            accuracy_percentage=0.0,
        )
        session.add(res)
        await session.commit()

        return s1, s2, exam, q, attempt, ans


# ===========================================================================
# 1. AUTHORIZATION TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_auth_own_attempt():
    """Student can diagnose wrong answer for their own attempt."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        resp = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp is not None
        assert resp.diagnostic is not None
        assert resp.diagnostic.error_category == ErrorCategory.CALCULATION_ERROR
        assert resp.is_sufficient is True


@pytest.mark.asyncio
async def test_auth_another_student_attempt():
    """Accessing another student's attempt raises DiagnosticUnauthorizedException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        with pytest.raises(DiagnosticUnauthorizedException) as exc_info:
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s2,  # Student 2 tries to access Student 1's attempt
            )
        assert "không phải chủ sở hữu" in str(exc_info.value)


@pytest.mark.asyncio
async def test_auth_cross_tenant_attempt():
    """Accessing attempt with mismatched tenant raises DiagnosticUnauthorizedException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    # Attach tenant to student and attempt
    setattr(s1, "tenant_id", "school-a")
    setattr(attempt, "tenant_id", "school-b")

    async with AsyncSessionLocal() as session:
        # Re-attach attempt to session
        att_db = (await session.execute(select(ExamAttempt).where(ExamAttempt.id == attempt.id))).scalar_one()
        setattr(att_db, "tenant_id", "school-b")

        with pytest.raises(DiagnosticUnauthorizedException) as exc_info:
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
                tenant_id="school-a",
            )
        assert "tenant" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_auth_unknown_attempt():
    """Attempt that does not exist raises AttemptNotFoundException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        with pytest.raises(AttemptNotFoundException):
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=str(uuid.uuid4()),
                question_id=q.id,
                student=s1,
            )


@pytest.mark.asyncio
async def test_auth_question_from_another_exam():
    """Question that belongs to another exam raises QuestionNotInAttemptException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    # Create another question not in this exam
    async with AsyncSessionLocal() as session:
        q_other = Question(
            id=str(uuid.uuid4()),
            question_type=QuestionType.SINGLE_CHOICE.value,
            content="Câu hỏi thuộc đề khác.",
            explanation="Giải thích khác",
        )
        session.add(q_other)
        await session.commit()

        with pytest.raises(QuestionNotInAttemptException):
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q_other.id,
                student=s1,
            )


@pytest.mark.asyncio
async def test_auth_invalid_question_id():
    """Completely non-existent question ID raises QuestionNotInAttemptException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        with pytest.raises(QuestionNotInAttemptException):
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=str(uuid.uuid4()),
                student=s1,
            )


# ===========================================================================
# 2. EXAM STATE TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_exam_state_in_progress():
    """Attempt in IN_PROGRESS state raises AttemptNotSubmittedException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        att_db = (await session.execute(select(ExamAttempt).where(ExamAttempt.id == attempt.id))).scalar_one()
        att_db.status = AttemptStatus.IN_PROGRESS.value
        await session.commit()

        with pytest.raises(AttemptNotSubmittedException) as exc_info:
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
            )
        assert "chưa kết thúc" in str(exc_info.value) or "chưa nộp" in str(exc_info.value)


@pytest.mark.asyncio
async def test_exam_state_submitted():
    """Attempt in SUBMITTED state succeeds."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        att_db = (await session.execute(select(ExamAttempt).where(ExamAttempt.id == attempt.id))).scalar_one()
        att_db.status = AttemptStatus.SUBMITTED.value
        await session.commit()

        resp = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp is not None
        assert resp.diagnostic is not None


@pytest.mark.asyncio
async def test_exam_state_auto_submitted():
    """Attempt in AUTO_SUBMITTED state succeeds."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        att_db = (await session.execute(select(ExamAttempt).where(ExamAttempt.id == attempt.id))).scalar_one()
        att_db.status = AttemptStatus.AUTO_SUBMITTED.value
        await session.commit()

        resp = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp is not None


@pytest.mark.asyncio
async def test_exam_state_graded():
    """Attempt in GRADED state succeeds."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        resp = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp is not None


@pytest.mark.asyncio
async def test_exam_state_correct_answer():
    """Question answered correctly raises QuestionAlreadyCorrectException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        ans_db = (await session.execute(select(StudentAnswer).where(StudentAnswer.id == ans.id))).scalar_one()
        ans_db.is_correct = True
        await session.commit()

        with pytest.raises(QuestionAlreadyCorrectException):
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
            )


@pytest.mark.asyncio
async def test_exam_state_incorrect_answer():
    """Question answered incorrectly succeeds."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        resp = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp.diagnostic.error_category == ErrorCategory.CALCULATION_ERROR


@pytest.mark.asyncio
async def test_exam_state_missing_grading_result():
    """Question without authoritative is_correct raises GradingUnavailableException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        ans_db = (await session.execute(select(StudentAnswer).where(StudentAnswer.id == ans.id))).scalar_one()
        ans_db.is_correct = None
        await session.commit()

        with pytest.raises(GradingUnavailableException):
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
            )


# ===========================================================================
# 3. READ-ONLY INVARIANTS TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_read_only_invariants_all_entities_unchanged():
    """
    Snapshots all relevant examination domain fields before diagnosis
    and verifies that 100% of fields remain unchanged after diagnosis.
    """
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider()
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        # Pre-diagnosis snapshot
        att_before = (await session.execute(select(ExamAttempt).where(ExamAttempt.id == attempt.id))).scalar_one()
        ans_before = (await session.execute(select(StudentAnswer).where(StudentAnswer.id == ans.id))).scalar_one()
        q_before = (await session.execute(select(Question).where(Question.id == q.id))).scalar_one()
        res_before = (await session.execute(select(ExamResult).where(ExamResult.attempt_id == attempt.id))).scalar_one()

        att_snapshot = {
            "status": att_before.status,
            "score": att_before.score,
            "maximum_score": att_before.maximum_score,
            "submitted_at": att_before.submitted_at,
            "questions_snapshot_json": att_before.questions_snapshot_json,
            "answer_key_snapshot_json": att_before.answer_key_snapshot_json,
        }
        ans_snapshot = {
            "selected_option_id": ans_before.selected_option_id,
            "answer_text": ans_before.answer_text,
            "is_correct": ans_before.is_correct,
            "points_awarded": ans_before.points_awarded,
            "version": ans_before.version,
        }
        q_snapshot = {
            "content": q_before.content,
            "explanation": q_before.explanation,
            "difficulty_level": q_before.difficulty_level,
        }
        res_snapshot = {
            "total_score": res_before.total_score,
            "correct_answers_count": res_before.correct_answers_count,
            "wrong_answers_count": res_before.wrong_answers_count,
            "accuracy_percentage": res_before.accuracy_percentage,
        }

        # Run diagnostic service
        resp = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp is not None

        # Re-fetch entities fresh from database
        session.expire_all()
        att_after = (await session.execute(select(ExamAttempt).where(ExamAttempt.id == attempt.id))).scalar_one()
        ans_after = (await session.execute(select(StudentAnswer).where(StudentAnswer.id == ans.id))).scalar_one()
        q_after = (await session.execute(select(Question).where(Question.id == q.id))).scalar_one()
        res_after = (await session.execute(select(ExamResult).where(ExamResult.attempt_id == attempt.id))).scalar_one()

        # Strict equality check across all fields
        assert att_after.status == att_snapshot["status"]
        assert att_after.score == att_snapshot["score"]
        assert att_after.maximum_score == att_snapshot["maximum_score"]
        assert att_after.submitted_at == att_snapshot["submitted_at"]
        assert att_after.questions_snapshot_json == att_snapshot["questions_snapshot_json"]
        assert att_after.answer_key_snapshot_json == att_snapshot["answer_key_snapshot_json"]

        assert ans_after.selected_option_id == ans_snapshot["selected_option_id"]
        assert ans_after.answer_text == ans_snapshot["answer_text"]
        assert ans_after.is_correct == ans_snapshot["is_correct"]
        assert ans_after.points_awarded == ans_snapshot["points_awarded"]
        assert ans_after.version == ans_snapshot["version"]

        assert q_after.content == q_snapshot["content"]
        assert q_after.explanation == q_snapshot["explanation"]
        assert q_after.difficulty_level == q_snapshot["difficulty_level"]

        assert res_after.total_score == res_snapshot["total_score"]
        assert res_after.correct_answers_count == res_snapshot["correct_answers_count"]
        assert res_after.wrong_answers_count == res_snapshot["wrong_answers_count"]
        assert res_after.accuracy_percentage == res_snapshot["accuracy_percentage"]


# ===========================================================================
# 4. AI INTEGRATION TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_ai_valid_response():
    """Valid AI response is parsed into DiagnosticDetail and returned."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider(VALID_AI_JSON)
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        resp = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp.is_sufficient is True
        assert resp.diagnostic.error_category == ErrorCategory.CALCULATION_ERROR
        assert resp.diagnostic.suggested_review == "Đại số: Phép tính cơ bản"


@pytest.mark.asyncio
async def test_ai_malformed_json():
    """AI returning malformed non-JSON raises AIMalformedOutputException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider("This is not JSON at all!")
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        with pytest.raises(AIMalformedOutputException):
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
            )


@pytest.mark.asyncio
async def test_ai_invalid_category():
    """AI returning invalid enum category raises AIMalformedOutputException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    bad_json = json.dumps({
        "error_category": "NON_EXISTENT_CATEGORY_XYZ",
        "error_summary": "Tóm tắt",
        "misconception_analysis": "Phân tích",
        "step_by_step_guidance": "Hướng dẫn",
        "key_takeaway": "Bài học",
    })
    provider = _make_mock_provider(bad_json)
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        with pytest.raises(AIMalformedOutputException):
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
            )


@pytest.mark.asyncio
async def test_ai_insufficient_information():
    """AI returning INSUFFICIENT_INFORMATION sets is_sufficient=False."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider(INSUFFICIENT_AI_JSON)
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        resp = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp.is_sufficient is False
        assert resp.diagnostic.error_category == ErrorCategory.INSUFFICIENT_INFORMATION


@pytest.mark.asyncio
async def test_ai_provider_unavailable():
    """Provider raising server error maps to AIProviderUnavailableException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = MockAIProvider(model_name="mock-model-v1")
    provider.set_simulated_error("server")
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        with pytest.raises(AIProviderUnavailableException):
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
            )


@pytest.mark.asyncio
async def test_ai_timeout():
    """Provider timeout maps to AITimeoutException."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = MockAIProvider(model_name="mock-model-v1")
    provider.set_simulated_error("timeout")
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        with pytest.raises(AITimeoutException):
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
            )


@pytest.mark.asyncio
async def test_ai_cancellation_propagation():
    """asyncio.CancelledError propagates directly and is not caught."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()

    class CancellingProvider(MockAIProvider):
        async def generate(self, request):
            raise asyncio.CancelledError()

    provider = CancellingProvider(model_name="mock-model-v1")
    service = WrongAnswerDiagnosticService(provider=provider)

    async with AsyncSessionLocal() as session:
        with pytest.raises(asyncio.CancelledError):
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
            )


# ===========================================================================
# 5. CACHE & CONCURRENCY TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_cache_miss_then_hit():
    """First call misses cache and queries AI; second call hits cache without calling AI."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider(VALID_AI_JSON)
    cache = CacheService()
    service = WrongAnswerDiagnosticService(provider=provider, cache=cache)

    async with AsyncSessionLocal() as session:
        # First call: cache miss
        resp1 = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp1.cached is False

        # Second call: cache hit
        resp2 = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp2.cached is True
        assert resp2.latency_ms == 0.0
        assert resp2.diagnostic.error_summary == resp1.diagnostic.error_summary


@pytest.mark.asyncio
async def test_cache_expiration():
    """When cache key expires, service re-queries AI."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = MockAIProvider(model_name="mock-model-v1")
    provider.queue_response(VALID_AI_JSON)
    provider.queue_response(VALID_AI_JSON)

    # Set cache TTL to 1 second
    cache = CacheService()
    service = WrongAnswerDiagnosticService(provider=provider, cache=cache, cache_ttl_seconds=1)

    async with AsyncSessionLocal() as session:
        resp1 = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp1.cached is False

        # Simulate expiration by clearing cache
        cache.in_memory._store.clear()
        cache.in_memory._expires.clear()
        if cache.redis_client:
            cache.redis_client.flushdb()

        resp2 = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp2.cached is False  # Re-queried AI


@pytest.mark.asyncio
async def test_cache_prompt_version_change():
    """Changing prompt version results in different cache key and cache miss."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = MockAIProvider(model_name="mock-model-v1")
    provider.queue_response(VALID_AI_JSON)
    provider.queue_response(VALID_AI_JSON)
    cache = CacheService()
    service = WrongAnswerDiagnosticService(provider=provider, cache=cache)

    async with AsyncSessionLocal() as session:
        resp1 = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp1.cached is False

        # Patch PROMPT_VERSION in service module
        with patch("app.modules.ai_engine.diagnostics.service.PROMPT_VERSION", "2.0.0"):
            resp2 = await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
            )
            assert resp2.cached is False  # Missed cache because version differed


@pytest.mark.asyncio
async def test_cache_answer_fingerprint_change():
    """When student answer version changes, cache key changes and triggers cache miss."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = MockAIProvider(model_name="mock-model-v1")
    provider.queue_response(VALID_AI_JSON)
    provider.queue_response(VALID_AI_JSON)
    cache = CacheService()
    service = WrongAnswerDiagnosticService(provider=provider, cache=cache)

    async with AsyncSessionLocal() as session:
        resp1 = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp1.cached is False

        # Update student answer version in DB
        ans_db = (await session.execute(select(StudentAnswer).where(StudentAnswer.id == ans.id))).scalar_one()
        ans_db.version = 2
        await session.commit()

        resp2 = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp2.cached is False  # Cache miss due to updated answer version


@pytest.mark.asyncio
async def test_cache_redis_unavailable_fallback():
    """When Redis is completely unavailable, in-memory cache provides seamless fallback."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = _make_mock_provider(VALID_AI_JSON)

    # Force cache service to have redis_client = None
    cache = CacheService()
    cache.redis_client = None

    service = WrongAnswerDiagnosticService(provider=provider, cache=cache)

    async with AsyncSessionLocal() as session:
        resp = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp is not None
        assert resp.cached is False


@pytest.mark.asyncio
async def test_cache_redis_restart():
    """When Redis restarts / flushes, service misses cache and re-queries cleanly."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = MockAIProvider(model_name="mock-model-v1")
    provider.queue_response(VALID_AI_JSON)
    provider.queue_response(VALID_AI_JSON)
    cache = CacheService()
    service = WrongAnswerDiagnosticService(provider=provider, cache=cache)

    async with AsyncSessionLocal() as session:
        resp1 = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp1.cached is False

        # Simulate Redis restart (flush in-memory and redis store)
        cache.in_memory._store.clear()
        if cache.redis_client:
            cache.redis_client.flushdb()

        resp2 = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp2.cached is False


@pytest.mark.asyncio
async def test_cache_concurrent_duplicate_requests():
    """
    Two concurrent requests for the exact same diagnostic:
    Exactly ONE AI call is executed; second request waits and receives the cached result.
    """
    s1, s2, exam, q, attempt, ans = await _create_test_entities()

    # Provider with slight delay to ensure concurrency overlap
    class DelayedProvider(MockAIProvider):
        def __init__(self):
            super().__init__(model_name="mock-model-v1", default_text=VALID_AI_JSON)

        async def generate(self, request):
            await asyncio.sleep(0.3)
            return await super().generate(request)

    provider = DelayedProvider()
    cache = CacheService()
    cache.in_memory._store.clear()
    if cache.redis_client:
        cache.redis_client.flushdb()

    service = WrongAnswerDiagnosticService(provider=provider, cache=cache)

    async def call_worker():
        async with AsyncSessionLocal() as session:
            return await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
            )

    # Launch both concurrently
    res1, res2 = await asyncio.gather(call_worker(), call_worker())

    # Exactly one worker called the AI provider
    assert provider.call_count == 1

    # Both got valid diagnostics
    assert res1.diagnostic is not None
    assert res2.diagnostic is not None

    # One was fresh (cached=False), the other was served from cache (cached=True)
    statuses = [res1.cached, res2.cached]
    assert False in statuses
    assert True in statuses


@pytest.mark.asyncio
async def test_cache_lock_expiration():
    """Expired lock allows acquisition by subsequent request."""
    service = WrongAnswerDiagnosticService()
    lock_key = f"lock:test_exp_{uuid.uuid4().hex}"
    token1 = "token1"
    token2 = "token2"

    # Acquire lock with 1s TTL
    acquired1 = await service._acquire_lock(lock_key, token1, ttl_seconds=1)
    assert acquired1 is True

    # Immediate second attempt fails
    acquired2 = await service._acquire_lock(lock_key, token2, ttl_seconds=1)
    assert acquired2 is False

    # Simulate expiration in in-memory locks
    if lock_key in service._in_memory_locks:
        service._in_memory_locks[lock_key] = (token1, 0.0)  # Expired in past

    # Second acquisition now succeeds
    acquired3 = await service._acquire_lock(lock_key, token2, ttl_seconds=1)
    assert acquired3 is True


@pytest.mark.asyncio
async def test_cache_lock_release_after_failure():
    """When AI call fails, the lock is released in finally block so next request is not blocked."""
    s1, s2, exam, q, attempt, ans = await _create_test_entities()
    provider = MockAIProvider(model_name="mock-model-v1")
    provider.set_simulated_error("server")
    cache = CacheService()
    service = WrongAnswerDiagnosticService(provider=provider, cache=cache)

    async with AsyncSessionLocal() as session:
        # First call fails due to server error
        with pytest.raises(AIProviderUnavailableException):
            await service.diagnose_wrong_answer(
                db=session,
                attempt_id=attempt.id,
                question_id=q.id,
                student=s1,
            )

    # Fix provider
    provider.clear_simulated_error()
    provider.queue_response(VALID_AI_JSON)

    # Second request succeeds immediately because lock was released
    async with AsyncSessionLocal() as session:
        resp = await service.diagnose_wrong_answer(
            db=session,
            attempt_id=attempt.id,
            question_id=q.id,
            student=s1,
        )
        assert resp is not None
        assert resp.diagnostic is not None


@pytest.mark.asyncio
async def test_cache_isolation_between_tenants_and_users():
    """Cache keys differ between different students and different tenants."""
    service = WrongAnswerDiagnosticService()
    student1 = User(id="user-1")
    student2 = User(id="user-2")
    attempt = ExamAttempt(id="att-1")
    ans = StudentAnswer(version=1)

    from app.modules.ai_engine.diagnostics.schemas import DiagnosticContext
    ctx = DiagnosticContext(
        question_content="Question",
        question_type="SINGLE_CHOICE",
        student_answer="Ans",
        correct_answer="Corr",
    )

    key_user1 = service._generate_cache_key(
        tenant_id="tenant-a",
        student_id=student1.id,
        attempt_id=attempt.id,
        question_id="q-1",
        student_answer=ans,
        context=ctx,
        model_name="model-v1",
    )
    key_user2 = service._generate_cache_key(
        tenant_id="tenant-a",
        student_id=student2.id,
        attempt_id=attempt.id,
        question_id="q-1",
        student_answer=ans,
        context=ctx,
        model_name="model-v1",
    )
    key_tenant_b = service._generate_cache_key(
        tenant_id="tenant-b",
        student_id=student1.id,
        attempt_id=attempt.id,
        question_id="q-1",
        student_answer=ans,
        context=ctx,
        model_name="model-v1",
    )

    # All 3 keys must be mutually distinct
    assert key_user1 != key_user2
    assert key_user1 != key_tenant_b
    assert key_user2 != key_tenant_b
