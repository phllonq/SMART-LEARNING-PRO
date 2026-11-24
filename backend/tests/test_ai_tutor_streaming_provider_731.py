"""
Phase 7.3.1 Provider Streaming & Domain Contracts Test Suite - SMART LEARNING PRO
Comprehensive verification covering Groups A through F:
  Group A: Contract Tests (NormalizedStreamChunk, NormalizedStreamUsage)
  Group B: Mock Provider Streaming Tests (MockAIProvider)
  Group C: Google GenAI Provider Adapter Tests (Mocked Client & Error Mapping)
  Group D: Retry & Resilience Policy Tests (execute_stream_with_retry & ResilientLLMProvider)
  Group E: Backward Compatibility & Factory Integration
  Group F: AI Tutor Domain Schema & Socratic Prompt Registry Validation
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from google.genai import errors as genai_errors

from app.modules.ai_engine.contracts import (
    ChatMessage,
    NormalizedChatRequest,
    NormalizedChatResponse,
    NormalizedStreamChunk,
    NormalizedStreamUsage,
)
from app.modules.ai_engine.exceptions import (
    AIEngineException,
    AITimeoutError,
    AIRateLimitError,
    AIAuthenticationError,
    AIServerError,
    AIInvalidRequestError,
)
from app.modules.ai_engine.providers.base import BaseLLMProvider
from app.modules.ai_engine.providers.mock import MockAIProvider
from app.modules.ai_engine.providers.google_genai import GoogleGenAIProvider
from app.modules.ai_engine.retry import (
    ResilientLLMProvider,
    execute_stream_with_retry,
    execute_with_retry,
    is_retryable_error,
)
from app.modules.ai_engine.config import AIConfig
from app.modules.ai_engine.factory import get_llm_provider, ProviderFactory
from app.modules.ai_tutor.schemas import (
    MessageStatus,
    MessageRole,
    ConversationCreateRequest,
    ConversationRenameRequest,
    ConversationResponse,
    ConversationListResponse,
    TutorMessageRequest,
    TutorMessageMetadata,
    TutorMessageResponse,
)
from app.modules.ai_tutor.prompts import (
    SOCRATIC_TUTOR_PROMPT_VERSION,
    get_socratic_prompt,
    get_prompt_metadata,
)


# ==============================================================================
# GROUP A: CONTRACT TESTS (NormalizedStreamChunk, NormalizedStreamUsage)
# ==============================================================================

class TestGroupAContracts:
    """Verifies NormalizedStreamChunk and NormalizedStreamUsage contracts."""

    def test_chunk_basic_instantiation(self):
        chunk = NormalizedStreamChunk(
            delta="Xin chào",
            finish_reason=None,
            index=0,
            model="mock-model",
        )
        assert chunk.delta == "Xin chào"
        assert chunk.delta_text == "Xin chào"
        assert chunk.finish_reason is None
        assert chunk.index == 0
        assert chunk.model == "mock-model"
        assert chunk.usage is None

    def test_chunk_bidirectional_delta_sync(self):
        # Setting via delta
        c1 = NormalizedStreamChunk(delta="A")
        assert c1.delta == "A"
        assert c1.delta_text == "A"

        # Setting via delta_text
        c2 = NormalizedStreamChunk(delta_text="B")
        assert c2.delta == "B"
        assert c2.delta_text == "B"

    def test_usage_properties_and_serialization(self):
        usage = NormalizedStreamUsage(
            input_tokens=15,
            output_tokens=30,
            total_tokens=45,
            cached_tokens=5,
            thoughts_tokens=10,
        )
        assert usage.input_tokens == 15
        assert usage.output_tokens == 30
        assert usage.total_tokens == 45
        assert usage.cached_tokens == 5
        assert usage.thoughts_tokens == 10

        data = usage.model_dump()
        assert data["input_tokens"] == 15
        assert data["cached_tokens"] == 5

    def test_chunk_with_usage_and_finish_reason(self):
        usage = NormalizedStreamUsage(input_tokens=10, output_tokens=20, total_tokens=30)
        chunk = NormalizedStreamChunk(
            delta="",
            finish_reason="STOP",
            usage=usage,
            index=5,
            model="gemini-3.8-flash",
            metadata={"source": "test"},
        )
        assert chunk.finish_reason == "STOP"
        assert chunk.usage is not None
        assert chunk.usage.total_tokens == 30
        assert chunk.metadata.get("source") == "test"

        dumped = chunk.model_dump()
        assert dumped["finish_reason"] == "STOP"
        assert dumped["usage"]["total_tokens"] == 30


# ==============================================================================
# GROUP B: MOCK PROVIDER STREAMING TESTS
# ==============================================================================

class TestGroupBMockProvider:
    """Verifies deterministic streaming behavior in MockAIProvider."""

    @pytest.mark.asyncio
    async def test_mock_streaming_deterministic_words(self):
        provider = MockAIProvider(default_text="Học tập là một hành trình kỳ diệu.")
        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])

        chunks = []
        async for chunk in provider.generate_stream(request):
            chunks.append(chunk)

        assert len(chunks) > 1
        full_text = "".join(c.delta for c in chunks)
        assert full_text == "Học tập là một hành trình kỳ diệu."
        assert chunks[-1].finish_reason == "STOP"
        assert provider.stream_call_count == 1
        assert len(provider.recorded_stream_requests) == 1

    @pytest.mark.asyncio
    async def test_mock_streaming_explicit_chunk_list(self):
        provider = MockAIProvider(
            stream_chunks=["Chunk 1: ", "Chunk 2: ", "Chunk 3."],
            finish_reason="STOP",
        )
        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Ping")])

        received = []
        async for chunk in provider.generate_stream(request):
            received.append(chunk.delta)

        assert received == ["Chunk 1: ", "Chunk 2: ", "Chunk 3."]

    @pytest.mark.asyncio
    async def test_mock_streaming_with_simulated_usage(self):
        simulated_usage = NormalizedStreamUsage(input_tokens=12, output_tokens=24, total_tokens=36)
        provider = MockAIProvider(
            stream_chunks=["A", "B"],
            simulated_stream_usage=simulated_usage,
        )
        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Test")])

        chunks = [c async for c in provider.generate_stream(request)]
        assert len(chunks) == 2
        assert chunks[0].usage is None
        assert chunks[1].usage is not None
        assert chunks[1].usage.total_tokens == 36

    @pytest.mark.asyncio
    async def test_mock_streaming_empty_response(self):
        provider = MockAIProvider(empty_response=True)
        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Empty")])

        chunks = [c async for c in provider.generate_stream(request)]
        assert len(chunks) == 1
        assert chunks[0].delta == ""
        assert chunks[0].finish_reason == "STOP"

    @pytest.mark.asyncio
    async def test_mock_streaming_cancellation(self):
        provider = MockAIProvider(
            stream_chunks=["a", "b", "c", "d"],
            stream_chunk_delay=0.05,
        )
        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Cancel me")])

        async def consume():
            tokens = []
            async for chunk in provider.generate_stream(request):
                tokens.append(chunk.delta)
                if len(tokens) == 2:
                    break
            return tokens

        tokens = await consume()
        assert len(tokens) == 2


# ==============================================================================
# GROUP C: GOOGLE GENAI PROVIDER ADAPTER TESTS (MOCKED CLIENT)
# ==============================================================================

class TestGroupCGoogleGenAIAdapter:
    """Verifies GoogleGenAIProvider streaming normalization, finish reasons, token handling, and error mapping."""

    @pytest.mark.asyncio
    async def test_google_stream_success_and_chunk_mapping(self):
        provider = GoogleGenAIProvider(api_key="fake-test-key", default_model="gemini-3.8-flash")

        # Create mock chunks returned by client.aio.models.generate_content_stream
        chunk1 = MagicMock()
        chunk1.text = "Gợi ý: "
        chunk1.candidates = [MagicMock(finish_reason=None)]
        chunk1.usage_metadata = None

        chunk2 = MagicMock()
        chunk2.text = "Hãy tìm nghiệm $x$."
        chunk2.candidates = [MagicMock(finish_reason="STOP")]
        usage_meta = MagicMock()
        usage_meta.prompt_token_count = 25
        usage_meta.candidates_token_count = 15
        usage_meta.total_token_count = 40
        usage_meta.cached_content_token_count = 0
        usage_meta.thoughts_token_count = 5
        chunk2.usage_metadata = usage_meta

        async def mock_async_gen():
            yield chunk1
            yield chunk2

        # Mock the client's generate_content_stream coroutine
        provider._client.aio.models.generate_content_stream = AsyncMock(return_value=mock_async_gen())

        request = NormalizedChatRequest(
            messages=[ChatMessage(role="user", content="Giải phương trình")],
            system_instruction="Bạn là gia sư",
        )

        streamed_chunks = []
        async for chunk in provider.generate_stream(request):
            streamed_chunks.append(chunk)

        assert len(streamed_chunks) == 2
        assert streamed_chunks[0].delta == "Gợi ý: "
        assert streamed_chunks[0].index == 0
        assert streamed_chunks[0].finish_reason is None
        assert streamed_chunks[0].usage is None

        assert streamed_chunks[1].delta == "Hãy tìm nghiệm $x$."
        assert streamed_chunks[1].index == 1
        assert streamed_chunks[1].finish_reason == "STOP"
        assert streamed_chunks[1].usage is not None
        assert streamed_chunks[1].usage.input_tokens == 25
        assert streamed_chunks[1].usage.output_tokens == 15
        assert streamed_chunks[1].usage.total_tokens == 40
        assert streamed_chunks[1].usage.thoughts_tokens == 5

    @pytest.mark.asyncio
    async def test_google_stream_error_mapping_429(self):
        provider = GoogleGenAIProvider(api_key="fake-test-key")
        err_429 = genai_errors.APIError(429, {"error": {"message": "Resource exhausted quota"}})
        provider._client.aio.models.generate_content_stream = AsyncMock(side_effect=err_429)

        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="test")])

        with pytest.raises(AIRateLimitError) as exc_info:
            async for _ in provider.generate_stream(request):
                pass
        assert exc_info.value.provider == "google"

    @pytest.mark.asyncio
    async def test_google_stream_error_mapping_401_auth(self):
        provider = GoogleGenAIProvider(api_key="fake-test-key")
        err_401 = genai_errors.APIError(401, {"error": {"message": "API key invalid fake-test-key"}})
        provider._client.aio.models.generate_content_stream = AsyncMock(side_effect=err_401)

        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="test")])

        with pytest.raises(AIAuthenticationError) as exc_info:
            async for _ in provider.generate_stream(request):
                pass
        assert "fake-test-key" not in str(exc_info.value)  # Key must be sanitized

    @pytest.mark.asyncio
    async def test_google_stream_timeout_mapping(self):
        provider = GoogleGenAIProvider(api_key="fake-test-key", timeout_seconds=0.05)
        provider._client.aio.models.generate_content_stream = AsyncMock(side_effect=asyncio.TimeoutError())

        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="test")])

        with pytest.raises(AITimeoutError):
            async for _ in provider.generate_stream(request):
                pass


# ==============================================================================
# GROUP D: RETRY & RESILIENCE POLICY TESTS
# ==============================================================================

class TestGroupDRetryAndResilience:
    """Verifies strict streaming retry policy: retry connection error BEFORE first token; NEVER retry after."""

    @pytest.mark.asyncio
    async def test_retry_succeeds_when_error_before_first_token(self):
        """Failure occurs before any chunk is emitted -> retry is allowed and succeeds."""
        mock_provider = MockAIProvider(stream_chunks=["Token1", "Token2"])
        call_count = 0

        async def faulty_stream(req):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First attempt raises server error immediately before yielding anything
                raise AIServerError("Connection drop before first token", provider="mock")
            yield NormalizedStreamChunk(delta="RetriedToken1", index=0)
            yield NormalizedStreamChunk(delta="RetriedToken2", index=1)

        mock_provider.generate_stream = faulty_stream

        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])

        received = []
        async for chunk in execute_stream_with_retry(
            provider=mock_provider,
            request=request,
            max_retries=1,
            backoff_base=0.01,
            total_timeout=5.0,
        ):
            received.append(chunk.delta)

        assert call_count == 2
        assert received == ["RetriedToken1", "RetriedToken2"]

    @pytest.mark.asyncio
    async def test_strictly_no_retry_after_token_emitted(self):
        """CRITICAL: Error occurs after chunks were yielded -> MUST NOT retry to prevent duplicate tokens."""
        mock_provider = MockAIProvider()
        attempts = 0

        async def midflight_failure_stream(req):
            nonlocal attempts
            attempts += 1
            yield NormalizedStreamChunk(delta="PartialChunk1", index=0)
            yield NormalizedStreamChunk(delta="PartialChunk2", index=1)
            # Mid-flight network partition
            raise AIServerError("Connection lost mid-flight!", provider="mock")

        mock_provider.generate_stream = midflight_failure_stream

        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])

        emitted_chunks = []
        with pytest.raises(AIServerError) as exc_info:
            async for chunk in execute_stream_with_retry(
                provider=mock_provider,
                request=request,
                max_retries=2,
                backoff_base=0.01,
                total_timeout=5.0,
            ):
                emitted_chunks.append(chunk.delta)

        # Verified: Only 1 attempt made! Retry was strictly forbidden after tokens were yielded.
        assert attempts == 1
        assert emitted_chunks == ["PartialChunk1", "PartialChunk2"]
        assert "Connection lost mid-flight!" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_non_retryable_error_aborts_immediately_without_retries(self):
        """Permanent auth or invalid request errors fail on attempt 1 without retry."""
        mock_provider = MockAIProvider(
            stream_error_after_chunks=0,
            stream_error_to_raise=AIAuthenticationError("Invalid API key", provider="mock"),
        )
        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])

        with pytest.raises(AIAuthenticationError):
            async for _ in execute_stream_with_retry(
                provider=mock_provider,
                request=request,
                max_retries=2,
                backoff_base=0.01,
            ):
                pass

        assert mock_provider.stream_call_count == 1

    @pytest.mark.asyncio
    async def test_resilient_provider_decorator_streaming(self):
        """ResilientLLMProvider.generate_stream properly forwards to execute_stream_with_retry."""
        base_provider = MockAIProvider(stream_chunks=["Hello", " World"])
        resilient = ResilientLLMProvider(
            underlying_provider=base_provider,
            max_retries=1,
            backoff_base=0.01,
            total_timeout=5.0,
        )
        request = NormalizedChatRequest(messages=[ChatMessage(role="user", content="Hi")])

        chunks = [c.delta async for c in resilient.generate_stream(request)]
        assert chunks == ["Hello", " World"]


# ==============================================================================
# GROUP E: BACKWARD COMPATIBILITY & FACTORY INTEGRATION
# ==============================================================================

class TestGroupEBackwardCompatibility:
    """Verifies that existing batch generate() and legacy provider subclasses remain fully compatible."""

    class LegacyProviderWithoutStream(BaseLLMProvider):
        """Legacy provider that only implements generate() and does not define generate_stream."""
        @property
        def provider_name(self) -> str:
            return "legacy"

        @property
        def default_model(self) -> str:
            return "legacy-v1"

        async def generate(self, request: NormalizedChatRequest) -> NormalizedChatResponse:
            return NormalizedChatResponse(
                text="legacy response",
                model="legacy-v1",
                provider="legacy",
                request_id="req-legacy",
                latency_ms=10.0,
            )

        async def validate_connection(self) -> bool:
            return True

        async def close(self) -> None:
            pass

    @pytest.mark.asyncio
    async def test_legacy_subclass_instantiates_and_batch_works(self):
        legacy = self.LegacyProviderWithoutStream()
        assert legacy.provider_name == "legacy"

        req = NormalizedChatRequest(messages=[ChatMessage(role="user", content="test")])
        resp = await legacy.generate(req)
        assert resp.text == "legacy response"

    @pytest.mark.asyncio
    async def test_legacy_subclass_streaming_raises_not_implemented(self):
        legacy = self.LegacyProviderWithoutStream()
        req = NormalizedChatRequest(messages=[ChatMessage(role="user", content="test")])

        with pytest.raises(NotImplementedError) as exc_info:
            async for _ in legacy.generate_stream(req):
                pass
        assert "does not implement streaming" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_factory_provides_streaming_capable_provider(self):
        provider = get_llm_provider(AIConfig(provider="mock"))
        assert hasattr(provider, "generate_stream")

        req = NormalizedChatRequest(messages=[ChatMessage(role="user", content="ping")])
        chunks = [c.delta async for c in provider.generate_stream(req)]
        assert len(chunks) > 0


# ==============================================================================
# GROUP F: AI TUTOR DOMAIN SCHEMA & PROMPT REGISTRY VALIDATION
# ==============================================================================

class TestGroupFSchemasAndPrompts:
    """Verifies Pydantic v2 schemas and Socratic prompt registry."""

    def test_conversation_create_request_validation(self):
        # Valid create
        req = ConversationCreateRequest(title="  Ôn tập Hình học 9  ", topic_id="topic-123")
        assert req.title == "Ôn tập Hình học 9"
        assert req.topic_id == "topic-123"

        # Disallow client user_id injection
        with pytest.raises(ValueError):
            ConversationCreateRequest(title="Test", user_id="injected-uuid")

    def test_conversation_rename_request_validation(self):
        # Valid rename
        req = ConversationRenameRequest(title="  Tiêu đề mới  ")
        assert req.title == "Tiêu đề mới"

        # Disallow empty or whitespace-only title
        with pytest.raises(ValueError):
            ConversationRenameRequest(title="   ")

    def test_tutor_message_request_validation(self):
        # Valid message
        req = TutorMessageRequest(content="  Thầy ơi giúp em câu này với!  ")
        assert req.content == "Thầy ơi giúp em câu này với!"

        # Disallow empty content
        with pytest.raises(ValueError):
            TutorMessageRequest(content="   ")

        # Disallow client role injection
        with pytest.raises(ValueError):
            TutorMessageRequest(content="Học sinh hỏi", role="assistant")

    def test_message_status_enum_values(self):
        assert MessageStatus.STREAMING == "STREAMING"
        assert MessageStatus.COMPLETED == "COMPLETED"
        assert MessageStatus.INTERRUPTED == "INTERRUPTED"
        assert MessageStatus.FAILED == "FAILED"

    def test_socratic_prompt_registry_content(self):
        prompt = get_socratic_prompt(topic="Phương trình bậc hai", grade_level="9")
        assert "Gia sư AI" in prompt
        assert "PHƯƠNG PHÁP SƯ PHẠM SOCRATIC" in prompt
        assert "KHÔNG LÀM HỘ" in prompt
        assert "KaTeX" in prompt
        assert "PROMPT INJECTION" in prompt
        assert "Lớp 9" in prompt
        assert "Phương trình bậc hai" in prompt

        meta = get_prompt_metadata()
        assert meta["version"] == SOCRATIC_TUTOR_PROMPT_VERSION
        assert meta["version"] == "1.0.0"
