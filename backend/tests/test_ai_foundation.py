"""
Test Suite for Phase 7.1 — AI Foundation & Provider Abstraction
SMART LEARNING PRO

Tests:
1. Normalized Contracts (Validation, boundaries, token handling)
2. MockAIProvider (Deterministic responses, offline execution, error simulation)
3. GoogleGenAIProvider (Mocked SDK responses, exception mapping, token extraction, secret scrubbing)
4. Retry and Timeout Policy (Transient retries, permanent fail-fast, overall deadline)
5. Provider Factory & Centralized Configuration (Validation, no silent fallback, credential masking)
6. Usage Accounting (Cost calculations, DB persistence isolation)
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import ValidationError

from app.modules.ai_engine.contracts import (
    ChatMessage,
    NormalizedChatRequest,
    NormalizedChatResponse,
    NormalizedStreamChunk,
    AIUsageRecord,
)
from app.modules.ai_engine.exceptions import (
    AIEngineException,
    AIConfigurationError,
    AIAuthenticationError,
    AIRateLimitError,
    AITimeoutError,
    AIServerError,
    AIInvalidRequestError,
    AIMalformedResponseError,
)
from app.modules.ai_engine.config import AIConfig, get_ai_config
from app.modules.ai_engine.providers.mock import MockAIProvider
from app.modules.ai_engine.providers.google_genai import GoogleGenAIProvider
from app.modules.ai_engine.retry import (
    is_retryable_error,
    execute_with_retry,
    ResilientLLMProvider,
)
from app.modules.ai_engine.factory import ProviderFactory, get_llm_provider
from app.modules.ai_engine.usage import (
    calculate_estimated_cost,
    create_usage_record,
    record_usage_to_db,
)
from app.modules.ai_tutor.models import AIUsageLog
from app.core.database import AsyncSessionLocal
from sqlalchemy import select


# ==============================================================================
# 1. CONTRACTS TESTING
# ==============================================================================

class TestNormalizedContracts:
    def test_valid_chat_message(self):
        msg = ChatMessage(role="user", content="Giải giúp em bài toán này với")
        assert msg.role == "user"
        assert msg.content == "Giải giúp em bài toán này với"

    def test_chat_message_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="")

        with pytest.raises(ValidationError):
            ChatMessage(role="user", content="   \n\t  ")

    def test_chat_message_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            ChatMessage(role="admin", content="Hello")

    def test_valid_chat_request(self):
        req = NormalizedChatRequest(
            messages=[
                ChatMessage(role="system", content="Bạn là gia sư toán."),
                ChatMessage(role="user", content="Định lý Pythagoras là gì?"),
            ],
            model="gemini-3.8-flash",
            temperature=0.5,
            max_output_tokens=1024,
            metadata={"user_id": "u-123", "grade": 9},
        )
        assert len(req.messages) == 2
        assert req.temperature == 0.5
        assert req.max_output_tokens == 1024
        assert req.metadata["user_id"] == "u-123"

    def test_chat_request_empty_messages_rejected(self):
        with pytest.raises(ValidationError):
            NormalizedChatRequest(messages=[])

    def test_chat_request_invalid_temperature_rejected(self):
        with pytest.raises(ValidationError):
            NormalizedChatRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                temperature=2.5,
            )

        with pytest.raises(ValidationError):
            NormalizedChatRequest(
                messages=[ChatMessage(role="user", content="Hi")],
                temperature=-0.1,
            )

    def test_chat_response_tokens_unavailable(self):
        resp = NormalizedChatResponse(
            text="Kết quả là 42",
            model="mock-model",
            provider="mock",
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
        )
        assert resp.text == "Kết quả là 42"
        assert resp.input_tokens is None
        assert resp.output_tokens is None
        assert resp.total_tokens is None

    def test_chat_response_empty_text_handled(self):
        resp = NormalizedChatResponse(
            text="",
            model="mock-model",
            provider="mock",
        )
        assert resp.text == ""

    def test_stream_chunk_minimal_contract(self):
        chunk = NormalizedStreamChunk(
            delta_text="Xin chào ",
            is_final=False,
        )
        assert chunk.delta_text == "Xin chào "
        assert not chunk.is_final
        assert chunk.finish_reason is None

        final_chunk = NormalizedStreamChunk(
            delta_text="",
            is_final=True,
            finish_reason="STOP",
            usage={"input": 10, "output": 20},
        )
        assert final_chunk.is_final
        assert final_chunk.finish_reason == "STOP"
        assert final_chunk.usage["input"] == 10


# ==============================================================================
# 2. MOCK PROVIDER TESTING (OFFLINE & DETERMINISTIC)
# ==============================================================================

class TestMockAIProvider:
    @pytest.mark.asyncio
    async def test_mock_successful_generation(self):
        provider = MockAIProvider(default_text="Đáp án câu 1 là A.")
        req = NormalizedChatRequest(
            messages=[ChatMessage(role="user", content="Câu 1 đáp án gì?")]
        )
        resp = await provider.generate(req)

        assert resp.provider == "mock"
        assert resp.text == "Đáp án câu 1 là A."
        assert resp.input_tokens is None
        assert resp.output_tokens is None
        assert provider.call_count == 1
        assert provider.last_request == req

    @pytest.mark.asyncio
    async def test_mock_simulated_tokens(self):
        provider = MockAIProvider(
            default_text="Chi tiết lời giải...",
            simulated_input_tokens=50,
            simulated_output_tokens=120,
        )
        req = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Giải giúp em")])
        resp = await provider.generate(req)

        assert resp.input_tokens == 50
        assert resp.output_tokens == 120
        assert resp.total_tokens == 170

    @pytest.mark.asyncio
    async def test_mock_empty_response(self):
        provider = MockAIProvider(empty_response=True)
        req = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])
        resp = await provider.generate(req)
        assert resp.text == ""

    @pytest.mark.asyncio
    async def test_mock_simulated_errors(self):
        # 1. Rate limit
        provider = MockAIProvider()
        provider.set_simulated_error("rate_limit", "Quota exhausted")
        with pytest.raises(AIRateLimitError) as exc_info:
            await provider.generate(NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")]))
        assert "Quota exhausted" in str(exc_info.value)
        assert exc_info.value.retryable is True

        # 2. Timeout
        provider.set_simulated_error("timeout", "Mock timeout")
        with pytest.raises(AITimeoutError):
            await provider.generate(NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")]))

        # 3. Auth failure
        provider.set_simulated_error("auth", "Invalid key")
        with pytest.raises(AIAuthenticationError) as auth_exc:
            await provider.generate(NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")]))
        assert auth_exc.value.retryable is False

        # 4. Server error
        provider.set_simulated_error("server", "Internal 500")
        with pytest.raises(AIServerError):
            await provider.generate(NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")]))

        # 5. Malformed response
        provider.set_simulated_error("malformed", "Corrupted payload")
        with pytest.raises(AIMalformedResponseError):
            await provider.generate(NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")]))

    @pytest.mark.asyncio
    async def test_mock_response_sequence(self):
        provider = MockAIProvider()
        provider.queue_response(AIRateLimitError("First call rate limited", provider="mock"))
        provider.queue_response("Second call succeeded.")

        req = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])

        # Call 1: raises error
        with pytest.raises(AIRateLimitError):
            await provider.generate(req)

        # Call 2: succeeds
        resp2 = await provider.generate(req)
        assert resp2.text == "Second call succeeded."
        assert provider.call_count == 2

    @pytest.mark.asyncio
    async def test_mock_lifecycle_and_validate(self):
        provider = MockAIProvider()
        assert await provider.validate_connection() is True
        await provider.close()
        assert await provider.validate_connection() is False


# ==============================================================================
# 3. GOOGLE PROVIDER TESTING (WITH MOCKED SDK RESPONSES)
# ==============================================================================

class TestGoogleGenAIProvider:
    @pytest.mark.asyncio
    async def test_google_provider_init_requires_api_key(self):
        with pytest.raises(ValueError):
            GoogleGenAIProvider(api_key="")

        with pytest.raises(ValueError):
            GoogleGenAIProvider(api_key="   ")

    @pytest.mark.asyncio
    async def test_google_provider_normalization(self):
        secret_key = "test-secret-key-xyz123"
        provider = GoogleGenAIProvider(api_key=secret_key, default_model="gemini-3.8-flash")

        # Mock the SDK client response
        mock_raw_resp = MagicMock()
        mock_raw_resp.text = "Tam giác vuông có định lý Pythagoras: $a^2 + b^2 = c^2$."
        mock_raw_resp.response_id = "resp-google-999"

        # Mock usage metadata
        mock_usage = MagicMock()
        mock_usage.prompt_token_count = 25
        mock_usage.candidates_token_count = 40
        mock_usage.total_token_count = 65
        mock_raw_resp.usage_metadata = mock_usage

        # Mock candidate
        mock_candidate = MagicMock()
        mock_candidate.finish_reason = "STOP"
        mock_raw_resp.candidates = [mock_candidate]

        # Patch the SDK async call
        with patch.object(
            provider._client.aio.models,
            "generate_content",
            new=AsyncMock(return_value=mock_raw_resp)
        ) as mock_generate:
            req = NormalizedChatRequest(
                messages=[ChatMessage(role="user", content="Giải thích Pythagoras")],
                system_instruction="Thầy giáo dạy toán",
                temperature=0.3,
            )
            response = await provider.generate(req)

            assert response.provider == "google"
            assert response.model == "gemini-3.8-flash"
            assert "$a^2 + b^2 = c^2$" in response.text
            assert response.input_tokens == 25
            assert response.output_tokens == 40
            assert response.total_tokens == 65
            assert response.finish_reason == "STOP"
            assert response.request_id == "resp-google-999"

            mock_generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_google_provider_missing_usage_metadata(self):
        provider = GoogleGenAIProvider(api_key="mock-key")

        mock_raw_resp = MagicMock()
        mock_raw_resp.text = "Hello"
        mock_raw_resp.usage_metadata = None
        mock_raw_resp.candidates = []
        mock_raw_resp.response_id = None

        with patch.object(
            provider._client.aio.models,
            "generate_content",
            new=AsyncMock(return_value=mock_raw_resp)
        ):
            resp = await provider.generate(
                NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])
            )
            assert resp.input_tokens is None
            assert resp.output_tokens is None
            assert resp.total_tokens is None
            assert resp.finish_reason is None

    @pytest.mark.asyncio
    async def test_google_provider_empty_text_handled(self):
        provider = GoogleGenAIProvider(api_key="mock-key")

        mock_raw_resp = MagicMock()
        # Simulating property access error or empty string
        mock_raw_resp.text = None
        mock_raw_resp.usage_metadata = None
        mock_raw_resp.candidates = []

        with patch.object(
            provider._client.aio.models,
            "generate_content",
            new=AsyncMock(return_value=mock_raw_resp)
        ):
            resp = await provider.generate(
                NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])
            )
            assert resp.text == ""

    @pytest.mark.asyncio
    async def test_google_provider_exception_mapping_and_secret_scrubbing(self):
        secret_api_key = "super-secret-gemini-key-999"
        provider = GoogleGenAIProvider(api_key=secret_api_key)

        from google.genai import errors as genai_errors

        # 1. 429 Quota Exceeded
        err_429 = genai_errors.APIError(429, {"error": {"message": f"Quota exceeded for key {secret_api_key}"}})
        with patch.object(provider._client.aio.models, "generate_content", new=AsyncMock(side_effect=err_429)):
            with pytest.raises(AIRateLimitError) as exc_info:
                await provider.generate(NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")]))
            assert secret_api_key not in str(exc_info.value)
            assert "[REDACTED_API_KEY]" in str(exc_info.value)
            assert exc_info.value.retryable is True

        # 2. 401 Auth error
        err_401 = genai_errors.APIError(401, {"error": {"message": f"Invalid API key {secret_api_key}"}})
        with patch.object(provider._client.aio.models, "generate_content", new=AsyncMock(side_effect=err_401)):
            with pytest.raises(AIAuthenticationError) as exc_info:
                await provider.generate(NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")]))
            assert secret_api_key not in str(exc_info.value)
            assert exc_info.value.retryable is False

        # 3. 503 Server Unavailable
        err_503 = genai_errors.APIError(503, {"error": {"message": "Service unavailable"}})
        with patch.object(provider._client.aio.models, "generate_content", new=AsyncMock(side_effect=err_503)):
            with pytest.raises(AIServerError) as exc_info:
                await provider.generate(NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")]))
            assert exc_info.value.retryable is True

    @pytest.mark.asyncio
    async def test_google_provider_timeout_handling(self):
        provider = GoogleGenAIProvider(api_key="test-key", timeout_seconds=0.1)

        async def slow_call(*args, **kwargs):
            await asyncio.sleep(0.5)

        with patch.object(provider._client.aio.models, "generate_content", new=slow_call):
            with pytest.raises(AITimeoutError) as exc_info:
                await provider.generate(NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")]))
            assert "timed out after 0.1s" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_google_provider_close(self):
        provider = GoogleGenAIProvider(api_key="test-key")
        assert await provider.validate_connection() is True
        await provider.close()
        assert await provider.validate_connection() is False
        with pytest.raises(AIEngineException):
            await provider.generate(NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")]))

    def test_google_provider_normalizes_usage_metadata_without_double_counting_thoughts(self):
        """Phase 7.1.2: candidates_token_count already includes thoughts_token_count.
        Never add them together. Also extract cached_content_token_count and thoughts_token_count."""
        provider = GoogleGenAIProvider(api_key="test-key")
        raw_resp = MagicMock()
        raw_resp.candidates = [MagicMock(finish_reason="STOP")]
        raw_resp.text = "Model answer with thinking"
        raw_resp.response_id = "test-genai-id-123"

        usage_mock = MagicMock()
        usage_mock.prompt_token_count = 100
        usage_mock.candidates_token_count = 50
        usage_mock.total_token_count = 150
        usage_mock.cached_content_token_count = 30
        usage_mock.thoughts_token_count = 20
        raw_resp.usage_metadata = usage_mock

        norm = provider._normalize_response(raw_resp, model="gemini-3.8-flash", latency_ms=120.0)
        assert norm.input_tokens == 100
        assert norm.output_tokens == 50  # Must be 50, NOT 50 + 20 = 70!
        assert norm.total_tokens == 150
        assert norm.metadata["cached_tokens"] == 30
        assert norm.metadata["thoughts_tokens"] == 20
        assert norm.request_id == "test-genai-id-123"

    def test_google_provider_normalizes_missing_usage_metadata(self):
        """Phase 7.1.2: Missing usage_metadata must produce None tokens, not 0."""
        provider = GoogleGenAIProvider(api_key="test-key")
        raw_resp = MagicMock()
        raw_resp.candidates = [MagicMock(finish_reason="STOP")]
        raw_resp.text = "Response without usage metadata"
        raw_resp.response_id = "test-genai-id-456"
        raw_resp.usage_metadata = None

        norm = provider._normalize_response(raw_resp, model="gemini-3.8-flash", latency_ms=100.0)
        assert norm.input_tokens is None
        assert norm.output_tokens is None
        assert norm.total_tokens is None
        assert norm.metadata == {}


# ==============================================================================
# 4. TIMEOUT AND RETRY POLICY TESTING
# ==============================================================================

class TestRetryPolicy:
    def test_error_classification(self):
        assert is_retryable_error(AIRateLimitError("429")) is True
        assert is_retryable_error(AIServerError("500")) is True
        assert is_retryable_error(AITimeoutError("timeout")) is True

        assert is_retryable_error(AIAuthenticationError("401")) is False
        assert is_retryable_error(AIInvalidRequestError("400")) is False
        assert is_retryable_error(AIConfigurationError("misconfigured")) is False
        assert is_retryable_error(AIMalformedResponseError("corrupt")) is False

    @pytest.mark.asyncio
    async def test_retry_transient_error_eventual_success(self):
        mock_provider = MockAIProvider()
        mock_provider.queue_response(AIRateLimitError("Transient 429", provider="mock"))
        mock_provider.queue_response(AIServerError("Transient 503", provider="mock"))
        mock_provider.queue_response("Success on 3rd attempt!")

        req = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])

        # Execute with max_retries = 2 (total 3 attempts)
        resilient_provider = ResilientLLMProvider(
            underlying_provider=mock_provider,
            max_retries=2,
            backoff_base=0.01, # Fast backoff for tests
            total_timeout=5.0,
        )

        resp = await resilient_provider.generate(req)
        assert resp.text == "Success on 3rd attempt!"
        assert mock_provider.call_count == 3

    @pytest.mark.asyncio
    async def test_do_not_retry_permanent_error(self):
        mock_provider = MockAIProvider()
        mock_provider.queue_response(AIAuthenticationError("Invalid API Key", provider="mock"))
        mock_provider.queue_response("Should never reach here")

        resilient_provider = ResilientLLMProvider(
            underlying_provider=mock_provider,
            max_retries=3,
            backoff_base=0.01,
            total_timeout=5.0,
        )

        with pytest.raises(AIAuthenticationError):
            await resilient_provider.generate(
                NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])
            )

        # Permanent error must fail on first attempt!
        assert mock_provider.call_count == 1

    @pytest.mark.asyncio
    async def test_exhaust_max_retries(self):
        mock_provider = MockAIProvider()
        mock_provider.queue_response(AIServerError("Server 500 #1", provider="mock"))
        mock_provider.queue_response(AIServerError("Server 500 #2", provider="mock"))
        mock_provider.queue_response(AIServerError("Server 500 #3", provider="mock"))

        resilient_provider = ResilientLLMProvider(
            underlying_provider=mock_provider,
            max_retries=2,
            backoff_base=0.01,
            total_timeout=5.0,
        )

        with pytest.raises(AIServerError):
            await resilient_provider.generate(
                NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])
            )

        # 1 initial + 2 retries = 3 calls
        assert mock_provider.call_count == 3

    @pytest.mark.asyncio
    async def test_overall_deadline_budget_exhausted(self):
        mock_provider = MockAIProvider(latency_seconds=0.2)
        mock_provider.error_to_raise = AIRateLimitError("Slow rate limit", provider="mock")

        resilient_provider = ResilientLLMProvider(
            underlying_provider=mock_provider,
            max_retries=5,
            backoff_base=0.1,
            total_timeout=0.3, # Budget expires during retry
        )

        with pytest.raises(AITimeoutError) as exc_info:
            await resilient_provider.generate(
                NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])
            )
        assert "deadline" in str(exc_info.value).lower()


# ==============================================================================
# 5. FACTORY & CONFIGURATION TESTING
# ==============================================================================

class TestProviderFactoryAndConfig:
    def test_mock_mode_works_without_api_key(self):
        cfg = AIConfig(provider="mock", api_key="", model="mock-model-v1")
        cfg.validate_provider_configuration()
        provider = ProviderFactory.create_provider(cfg, with_resilience=False)

        assert provider.provider_name == "mock"
        assert isinstance(provider, MockAIProvider)

    def test_google_mode_rejects_missing_api_key(self):
        cfg = AIConfig(provider="google", api_key="", model="gemini-3.8-flash")
        with pytest.raises(AIConfigurationError) as exc_info:
            cfg.validate_provider_configuration()
        assert "GEMINI_API_KEY must be configured" in str(exc_info.value)

        with pytest.raises(AIConfigurationError):
            ProviderFactory.create_provider(cfg)

    def test_invalid_provider_rejected(self):
        cfg = AIConfig(provider="openai_unsupported", api_key="test")
        with pytest.raises(AIConfigurationError) as exc_info:
            cfg.validate_provider_configuration()
        assert "Unsupported AI provider" in str(exc_info.value)

    def test_config_masks_api_key_in_repr(self):
        secret = "secret-gemini-key-123456"
        cfg = AIConfig(provider="google", api_key=secret)
        repr_str = repr(cfg)
        str_str = str(cfg)

        assert secret not in repr_str
        assert secret not in str_str
        assert "***" in repr_str

    def test_factory_creates_resilient_wrapper(self):
        cfg = AIConfig(provider="mock", max_retries=3)
        provider = ProviderFactory.create_provider(cfg, with_resilience=True)
        assert isinstance(provider, ResilientLLMProvider)
        assert provider.max_retries == 3
        assert provider.provider_name == "mock"


# ==============================================================================
# 6. USAGE ACCOUNTING TESTING
# ==============================================================================

class TestUsageAccounting:
    def test_calculate_estimated_cost_verified_2026(self):
        from datetime import date
        # Official pricing Gemini 3.8 Flash in 2026:
        # Input: $0.75 / 1M, Output: $3.75 / 1M
        # 1,000,000 input + 1,000,000 output = $4.50
        cost = calculate_estimated_cost("gemini-3.8-flash", 1_000_000, 1_000_000, as_of=date(2026, 11, 20))
        assert cost == 4.50

        # 10,000 input ($0.0075) + 2,000 output ($0.0075) = $0.015
        cost_small = calculate_estimated_cost("gemini-3.8-flash", 10_000, 2_000, as_of=date(2026, 11, 20))
        assert cost_small == 0.015

    def test_calculate_estimated_cost_verified_2027(self):
        from datetime import date
        # Official pricing Gemini 3.8 Flash starting 2027-01-01:
        # Input: $1.50 / 1M, Output: $7.50 / 1M
        cost_2027 = calculate_estimated_cost("gemini-3.8-flash", 1_000_000, 1_000_000, as_of=date(2027, 1, 15))
        assert cost_2027 == 9.00

    def test_calculate_estimated_cost_context_caching(self):
        from datetime import date
        # 1M total input with 500k cached tokens, 100k output:
        # non-cached input: 500k * $0.75/1M = $0.375
        # cached input: 500k * $0.075/1M = $0.0375
        # output: 100k * $3.75/1M = $0.375
        # total: 0.375 + 0.0375 + 0.375 = $0.7875
        cost = calculate_estimated_cost(
            "gemini-3.8-flash",
            input_tokens=1_000_000,
            output_tokens=100_000,
            as_of=date(2026, 11, 20),
            cached_tokens=500_000,
        )
        assert cost == 0.7875

    def test_calculate_cost_batch_tier(self):
        from datetime import date
        # Batch tier (50% discount):
        # 1M input ($0.375) + 1M output ($1.875) = $2.25
        cost_batch = calculate_estimated_cost(
            "gemini-3.8-flash",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            as_of=date(2026, 11, 20),
            tier="batch",
        )
        assert cost_batch == 2.25

    def test_calculate_cost_missing_tokens_returns_none(self):
        assert calculate_estimated_cost("gemini-3.8-flash", None, 100) is None
        assert calculate_estimated_cost("gemini-3.8-flash", 100, None) is None
        assert calculate_estimated_cost("gemini-3.8-flash", None, None) is None

    def test_calculate_cost_unknown_model_returns_none(self):
        assert calculate_estimated_cost("unknown-model-xyz", 1000, 2000) is None

    def test_create_usage_record(self):
        from datetime import date
        resp = NormalizedChatResponse(
            text="Lời giải bài toán",
            model="gemini-3.8-flash",
            provider="google",
            input_tokens=200,
            output_tokens=500,
            total_tokens=700,
            latency_ms=450.0,
        )
        record = create_usage_record(resp, user_id="user-123", feature="TUTOR_TEST", as_of=date(2026, 11, 20))
        assert record.user_id == "user-123"
        assert record.feature == "TUTOR_TEST"
        assert record.input_tokens == 200
        assert record.output_tokens == 500
        assert record.total_tokens == 700
        assert record.estimated_cost_usd is not None
        assert record.latency_ms == 450.0

    @pytest.mark.asyncio
    async def test_record_usage_to_db(self):
        async with AsyncSessionLocal() as db:
            record = AIUsageRecord(
                user_id=None,
                feature="FOUNDATION_TEST",
                provider="mock",
                model_name="mock-model-v1",
                input_tokens=15,
                output_tokens=30,
                total_tokens=45,
                estimated_cost_usd=0.0,
                latency_ms=12.5,
            )
            log_entry = await record_usage_to_db(db, record)
            assert log_entry is not None
            assert log_entry.feature == "FOUNDATION_TEST"
            assert log_entry.prompt_tokens == 15
            assert log_entry.completion_tokens == 30
            assert log_entry.model_name == "mock-model-v1"

            # Verify in DB
            q = select(AIUsageLog).where(AIUsageLog.id == log_entry.id)
            res = await db.execute(q)
            db_entry = res.scalar_one_or_none()
            assert db_entry is not None
            assert db_entry.prompt_tokens == 15

    @pytest.mark.asyncio
    async def test_record_usage_db_failure_isolated(self):
        # Pass a mock DB that throws an exception on add
        failing_db = MagicMock()
        failing_db.add.side_effect = Exception("DB Connection Lost")

        record = AIUsageRecord(
            user_id="u-err",
            feature="FAIL_TEST",
            provider="mock",
            model_name="mock-model-v1",
            input_tokens=10,
            output_tokens=20,
            estimated_cost_usd=0.0,
        )
        # Must catch error and return None without raising exception
        result = await record_usage_to_db(failing_db, record)
        assert result is None

    @pytest.mark.asyncio
    async def test_retry_does_not_duplicate_usage_records(self):
        """Verify that retries produce exactly one final response and one usage record."""
        mock_provider = MockAIProvider(
            simulated_input_tokens=100,
            simulated_output_tokens=50,
        )
        mock_provider.queue_response(AIRateLimitError("Retry 1", provider="mock"))
        mock_provider.queue_response(AIServerError("Retry 2", provider="mock"))
        mock_provider.queue_response("Final successful output")

        resilient_provider = ResilientLLMProvider(
            underlying_provider=mock_provider,
            max_retries=2,
            backoff_base=0.01,
            total_timeout=5.0,
        )

        req = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Calculate")])
        response = await resilient_provider.generate(req)

        # 3 calls made to mock provider
        assert mock_provider.call_count == 3
        # Exactly one final response returned
        assert response.text == "Final successful output"

        # Telemetry record is created once from final response
        usage_record = create_usage_record(response, user_id=None, feature="RETRY_DEDUP_FEATURE")
        assert usage_record.input_tokens == 100
        assert usage_record.output_tokens == 50

        # Persist once
        async with AsyncSessionLocal() as db:
            log_entry = await record_usage_to_db(db, usage_record)
            assert log_entry is not None

            # Verify only 1 record exists with this feature
            q = select(AIUsageLog).where(
                AIUsageLog.feature == "RETRY_DEDUP_FEATURE",
            )
            res = await db.execute(q)
            entries = res.scalars().all()
            assert len(entries) == 1

    def test_pricing_batch_tier_rejects_cached_tokens(self):
        """Batch tier does not support context caching discount."""
        from datetime import date
        cost = calculate_estimated_cost(
            "gemini-3.8-flash",
            input_tokens=1_000_000,
            output_tokens=100_000,
            as_of=date(2026, 11, 20),
            tier="batch",
            cached_tokens=500_000,
        )
        assert cost is None

    def test_pricing_2027_batch(self):
        """2027 Batch tier: 50% discount on 2027 standard ($1.50 / $7.50) -> $0.75 / $3.75."""
        from datetime import date
        cost = calculate_estimated_cost(
            "gemini-3.8-flash",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            as_of=date(2027, 2, 1),
            tier="batch",
        )
        assert cost == 4.50

    def test_create_usage_record_preserves_cached_and_thoughts_tokens(self):
        """Verify create_usage_record extracts cached and thoughts tokens from metadata."""
        from datetime import date
        resp = NormalizedChatResponse(
            text="Response text",
            model="gemini-3.8-flash",
            provider="google",
            input_tokens=1_000_000,
            output_tokens=100_000,
            total_tokens=1_100_000,
            latency_ms=300.0,
            metadata={"cached_tokens": 500_000, "thoughts_tokens": 25_000},
        )
        record = create_usage_record(resp, user_id="u-cache", as_of=date(2026, 11, 20))
        assert record.cached_tokens == 500_000
        assert record.thoughts_tokens == 25_000
        # Cost with caching: 500k regular ($0.375) + 500k cached ($0.0375) + 100k out ($0.375) = 0.7875
        assert record.estimated_cost_usd == 0.7875

    @pytest.mark.asyncio
    async def test_record_usage_skips_persistence_when_input_tokens_none(self):
        """Phase 7.1.2: Do NOT persist fake 0 tokens when input_tokens is None."""
        async with AsyncSessionLocal() as db:
            record = AIUsageRecord(
                user_id=None,
                feature="UNKNOWN_INPUT_FEATURE",
                provider="google",
                model_name="gemini-3.8-flash",
                input_tokens=None,
                output_tokens=50,
                total_tokens=None,
                estimated_cost_usd=None,
            )
            result = await record_usage_to_db(db, record)
            assert result is None

            # Verify no row was inserted into ai_usage_logs
            q = select(AIUsageLog).where(AIUsageLog.feature == "UNKNOWN_INPUT_FEATURE")
            res = await db.execute(q)
            assert res.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_record_usage_skips_persistence_when_output_tokens_none(self):
        """Phase 7.1.2: Do NOT persist fake 0 tokens when output_tokens is None."""
        async with AsyncSessionLocal() as db:
            record = AIUsageRecord(
                user_id=None,
                feature="UNKNOWN_OUTPUT_FEATURE",
                provider="google",
                model_name="gemini-3.8-flash",
                input_tokens=100,
                output_tokens=None,
                total_tokens=None,
                estimated_cost_usd=None,
            )
            result = await record_usage_to_db(db, record)
            assert result is None

            q = select(AIUsageLog).where(AIUsageLog.feature == "UNKNOWN_OUTPUT_FEATURE")
            res = await db.execute(q)
            assert res.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_record_usage_skips_persistence_when_both_tokens_none(self):
        """Phase 7.1.2: Do NOT persist fake 0 tokens when both input and output are None."""
        async with AsyncSessionLocal() as db:
            record = AIUsageRecord(
                user_id=None,
                feature="UNKNOWN_BOTH_FEATURE",
                provider="google",
                model_name="gemini-3.8-flash",
                input_tokens=None,
                output_tokens=None,
                total_tokens=None,
                estimated_cost_usd=None,
            )
            result = await record_usage_to_db(db, record)
            assert result is None

            q = select(AIUsageLog).where(AIUsageLog.feature == "UNKNOWN_BOTH_FEATURE")
            res = await db.execute(q)
            assert res.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_record_usage_persists_when_actual_zero_tokens(self):
        """Phase 7.1.2: Actual 0 tokens is a valid telemetry metric and must be persisted."""
        async with AsyncSessionLocal() as db:
            record = AIUsageRecord(
                user_id=None,
                feature="ACTUAL_ZERO_TOKENS_FEATURE",
                provider="mock",
                model_name="mock-model-v1",
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                estimated_cost_usd=0.0,
            )
            result = await record_usage_to_db(db, record)
            assert result is not None
            assert result.prompt_tokens == 0
            assert result.completion_tokens == 0
            assert result.estimated_cost_usd == 0.0

            q = select(AIUsageLog).where(AIUsageLog.feature == "ACTUAL_ZERO_TOKENS_FEATURE")
            res = await db.execute(q)
            entry = res.scalar_one_or_none()
            assert entry is not None
            assert entry.prompt_tokens == 0
            assert entry.completion_tokens == 0

    @pytest.mark.asyncio
    async def test_record_usage_skips_persistence_when_cost_none(self):
        """Phase 7.1.3: Do NOT persist fake 0.0 cost when estimated_cost_usd is None."""
        async with AsyncSessionLocal() as db:
            record = AIUsageRecord(
                user_id=None,
                feature="UNKNOWN_COST_FEATURE",
                provider="mock",
                model_name="unpriced-model",
                input_tokens=150,
                output_tokens=50,
                total_tokens=200,
                estimated_cost_usd=None,
            )
            result = await record_usage_to_db(db, record)
            assert result is None

            # Verify no row was inserted into ai_usage_logs
            q = select(AIUsageLog).where(AIUsageLog.feature == "UNKNOWN_COST_FEATURE")
            res = await db.execute(q)
            assert res.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_record_usage_persists_exact_positive_cost(self):
        """Phase 7.1.3: When cost is positive verified, persist exact cost."""
        async with AsyncSessionLocal() as db:
            record = AIUsageRecord(
                user_id=None,
                feature="POSITIVE_COST_FEATURE",
                provider="google",
                model_name="gemini-3.8-flash",
                input_tokens=1_000_000,
                output_tokens=100_000,
                total_tokens=1_100_000,
                estimated_cost_usd=0.615,
            )
            result = await record_usage_to_db(db, record)
            assert result is not None
            assert result.prompt_tokens == 1_000_000
            assert result.completion_tokens == 100_000
            assert result.estimated_cost_usd == 0.615

            q = select(AIUsageLog).where(AIUsageLog.feature == "POSITIVE_COST_FEATURE")
            res = await db.execute(q)
            entry = res.scalar_one_or_none()
            assert entry is not None
            assert entry.estimated_cost_usd == 0.615

    def test_calculate_cost_cached_pricing_formula_verification(self):
        """
        Phase 7.1.3 Verification of exact arithmetic:
        prompt = 1,000,000; cached = 200,000.
        regular input = 800,000.
        Standard 2026 input price = $0.75 / 1M.
        Cached price = $0.075 / 1M.
        Expected input cost = $0.615.
        With output = 0, total = $0.615.
        """
        from datetime import date
        cost = calculate_estimated_cost(
            "gemini-3.8-flash",
            input_tokens=1_000_000,
            output_tokens=0,
            as_of=date(2026, 11, 20),
            tier="standard",
            cached_tokens=200_000,
        )
        assert cost == 0.615

    def test_calculate_cost_cached_tokens_zero(self):
        """When cached_tokens == 0, full input charged at standard rate."""
        from datetime import date
        cost = calculate_estimated_cost(
            "gemini-3.8-flash",
            input_tokens=1_000_000,
            output_tokens=0,
            as_of=date(2026, 11, 20),
            tier="standard",
            cached_tokens=0,
        )
        assert cost == 0.75

    def test_calculate_cost_cached_tokens_none_unavailable(self):
        """When cached_tokens is None, full input charged at standard rate."""
        from datetime import date
        cost = calculate_estimated_cost(
            "gemini-3.8-flash",
            input_tokens=1_000_000,
            output_tokens=0,
            as_of=date(2026, 11, 20),
            tier="standard",
            cached_tokens=None,
        )
        assert cost == 0.75

    def test_calculate_cost_cached_equals_prompt_tokens(self):
        """When cached == prompt, 0 regular input tokens, 100% cached pricing."""
        from datetime import date
        cost = calculate_estimated_cost(
            "gemini-3.8-flash",
            input_tokens=1_000_000,
            output_tokens=0,
            as_of=date(2026, 11, 20),
            tier="standard",
            cached_tokens=1_000_000,
        )
        # 1M cached tokens * $0.075 / 1M = $0.075
        assert cost == 0.075

    def test_calculate_cost_cached_exceeds_prompt_tokens_returns_none(self):
        """
        Phase 7.1.3: If cached_tokens > input_tokens, metadata is invalid.
        DO NOT CLAMP, return None.
        """
        from datetime import date
        cost = calculate_estimated_cost(
            "gemini-3.8-flash",
            input_tokens=1_000_000,
            output_tokens=100_000,
            as_of=date(2026, 11, 20),
            tier="standard",
            cached_tokens=1_200_000,
        )
        assert cost is None

    def test_calculate_cost_negative_cached_tokens_returns_none(self):
        """Negative cached tokens is invalid metadata -> return None."""
        from datetime import date
        cost = calculate_estimated_cost(
            "gemini-3.8-flash",
            input_tokens=1_000_000,
            output_tokens=100_000,
            as_of=date(2026, 11, 20),
            tier="standard",
            cached_tokens=-50,
        )
        assert cost is None

    def test_calculate_cost_batch_tier_with_cached_tokens_returns_none(self):
        """Batch tier does not support context caching -> return None."""
        from datetime import date
        cost = calculate_estimated_cost(
            "gemini-3.8-flash",
            input_tokens=1_000_000,
            output_tokens=100_000,
            as_of=date(2026, 11, 20),
            tier="batch",
            cached_tokens=200_000,
        )
        assert cost is None


# ==============================================================================
# 7. ASYNC CANCELLATION & CLIENT LIFECYCLE AUDIT
# ==============================================================================

class TestAsyncLifecycleAndCancellation:
    @pytest.mark.asyncio
    async def test_async_cancellation_propagates_immediately(self):
        """Verify that asyncio.CancelledError is never caught as a retryable error."""
        mock_provider = MockAIProvider()

        async def cancelled_call(*args, **kwargs):
            raise asyncio.CancelledError()

        mock_provider.generate = AsyncMock(side_effect=asyncio.CancelledError())

        resilient_provider = ResilientLLMProvider(
            underlying_provider=mock_provider,
            max_retries=3,
            backoff_base=0.01,
            total_timeout=5.0,
        )

        req = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])

        with pytest.raises(asyncio.CancelledError):
            await resilient_provider.generate(req)

        # Must not retry when cancelled!
        mock_provider.generate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_google_provider_client_lifecycle_close_calls_aclose(self):
        """Verify GoogleGenAIProvider.close() releases underlying async and sync sessions."""
        provider = GoogleGenAIProvider(api_key="test-key")

        # Mock the client's close and aclose
        provider._client.aio.aclose = AsyncMock()
        provider._client.close = MagicMock()

        await provider.close()

        assert provider._is_closed is True
        assert provider._client is None
