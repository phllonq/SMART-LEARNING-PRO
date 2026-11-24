"""
Mock LLM Provider - SMART LEARNING PRO
Offline, fully deterministic provider for local testing and CI/CD pipelines.
Requires no external network connections or API credentials.
"""

import asyncio
import time
import uuid
from typing import Optional, List, Union, Dict, Any, AsyncIterator

from app.modules.ai_engine.contracts import (
    NormalizedChatRequest,
    NormalizedChatResponse,
    NormalizedStreamChunk,
    NormalizedStreamUsage,
)
from app.modules.ai_engine.exceptions import (
    AITimeoutError,
    AIRateLimitError,
    AIAuthenticationError,
    AIServerError,
    AIMalformedResponseError,
    AIInvalidRequestError,
)
from app.modules.ai_engine.providers.base import BaseLLMProvider


class MockAIProvider(BaseLLMProvider):
    """Deterministic mock provider supporting error simulation, sequence queues, and offline verification."""

    def __init__(
        self,
        default_text: str = "Simulated response from MockAIProvider.",
        model_name: str = "mock-model-v1",
        latency_seconds: float = 0.0,
        error_to_raise: Optional[Exception] = None,
        response_sequence: Optional[List[Union[str, Exception]]] = None,
        simulated_input_tokens: Optional[int] = None,
        simulated_output_tokens: Optional[int] = None,
        finish_reason: str = "STOP",
        empty_response: bool = False,
        stream_chunks: Optional[List[str]] = None,
        stream_chunk_delay: float = 0.0,
        stream_error_after_chunks: Optional[int] = None,
        stream_error_to_raise: Optional[Exception] = None,
        simulated_stream_usage: Optional[NormalizedStreamUsage] = None,
    ):
        self._default_text = default_text
        self._model_name = model_name
        self.latency_seconds = latency_seconds
        self.error_to_raise = error_to_raise
        self.response_sequence: List[Union[str, Exception]] = list(response_sequence) if response_sequence else []
        self.simulated_input_tokens = simulated_input_tokens
        self.simulated_output_tokens = simulated_output_tokens
        self.finish_reason = finish_reason
        self.empty_response = empty_response

        # Streaming simulation configuration
        self.stream_chunks = list(stream_chunks) if stream_chunks is not None else None
        self.stream_chunk_delay = stream_chunk_delay
        self.stream_error_after_chunks = stream_error_after_chunks
        self.stream_error_to_raise = stream_error_to_raise
        self.simulated_stream_usage = simulated_stream_usage

        # Telemetry & Call inspection
        self.call_count: int = 0
        self.stream_call_count: int = 0
        self.last_request: Optional[NormalizedChatRequest] = None
        self.recorded_requests: List[NormalizedChatRequest] = []
        self.recorded_stream_requests: List[NormalizedChatRequest] = []
        self.is_closed: bool = False

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return self._model_name

    def queue_response(self, item: Union[str, Exception]) -> None:
        """Enqueue a response or error for subsequent generate calls."""
        self.response_sequence.append(item)

    def set_simulated_error(self, error_type: str, message: str = "Simulated error") -> None:
        """Helper to quickly configure specific error types for test scenarios."""
        err_map = {
            "timeout": AITimeoutError(message, provider="mock"),
            "rate_limit": AIRateLimitError(message, provider="mock", retry_after_seconds=1.0),
            "auth": AIAuthenticationError(message, provider="mock"),
            "server": AIServerError(message, provider="mock", status_code=500),
            "malformed": AIMalformedResponseError(message, provider="mock"),
            "invalid_request": AIInvalidRequestError(message, provider="mock"),
        }
        if error_type not in err_map:
            raise ValueError(f"Unknown mock error type '{error_type}'. Allowed: {list(err_map.keys())}")
        self.error_to_raise = err_map[error_type]

    def clear_simulated_error(self) -> None:
        """Clear currently configured error."""
        self.error_to_raise = None

    async def generate(
        self,
        request: NormalizedChatRequest,
    ) -> NormalizedChatResponse:
        self.call_count += 1
        self.last_request = request
        self.recorded_requests.append(request)

        t_start = time.perf_counter()

        if self.latency_seconds > 0:
            await asyncio.sleep(self.latency_seconds)

        # 1. Check sequence queue first
        if self.response_sequence:
            next_item = self.response_sequence.pop(0)
            if isinstance(next_item, Exception):
                raise next_item
            text_content = next_item
        # 2. Check static configured error
        elif self.error_to_raise is not None:
            raise self.error_to_raise
        # 3. Check empty response mode
        elif self.empty_response:
            text_content = ""
        # 4. Fallback to default text
        else:
            text_content = self._default_text

        t_end = time.perf_counter()
        latency_ms = round((t_end - t_start) * 1000.0, 2)

        # Total tokens computed only if both input and output are present
        total_tokens: Optional[int] = None
        if self.simulated_input_tokens is not None and self.simulated_output_tokens is not None:
            total_tokens = self.simulated_input_tokens + self.simulated_output_tokens

        return NormalizedChatResponse(
            text=text_content,
            model=request.model or self._model_name,
            provider="mock",
            input_tokens=self.simulated_input_tokens,
            output_tokens=self.simulated_output_tokens,
            total_tokens=total_tokens,
            finish_reason=self.finish_reason,
            request_id=f"mock-{uuid.uuid4()}",
            latency_ms=latency_ms,
        )

    async def generate_stream(
        self,
        request: NormalizedChatRequest,
    ) -> AsyncIterator[NormalizedStreamChunk]:
        self.stream_call_count += 1
        self.last_request = request
        self.recorded_stream_requests.append(request)

        # 1. Fail immediately before first token if configured
        if self.stream_error_after_chunks == 0:
            err = self.stream_error_to_raise or self.error_to_raise or AIServerError("Mock stream error before first chunk", provider="mock")
            raise err

        # Determine chunks to stream
        if self.stream_chunks is not None:
            chunks = list(self.stream_chunks)
        elif self.empty_response:
            chunks = []
        else:
            words = self._default_text.split(" ")
            if len(words) <= 1:
                chunks = [self._default_text]
            else:
                chunks = [w + " " for w in words[:-1]] + [words[-1]]

        total_chunks = len(chunks)
        target_model = request.model or self._model_name

        for idx, chunk_text in enumerate(chunks):
            # Check mid-flight error simulation
            if self.stream_error_after_chunks is not None and idx == self.stream_error_after_chunks:
                err = self.stream_error_to_raise or self.error_to_raise or AIServerError(f"Mock stream error after {idx} chunks", provider="mock")
                raise err

            if self.stream_chunk_delay > 0:
                await asyncio.sleep(self.stream_chunk_delay)

            is_last = (idx == total_chunks - 1)
            finish_reason = self.finish_reason if is_last else None
            usage = self.simulated_stream_usage if is_last else None

            yield NormalizedStreamChunk(
                delta=chunk_text,
                finish_reason=finish_reason,
                usage=usage,
                index=idx,
                model=target_model,
            )

        # If chunks was empty (e.g. empty_response), yield a single empty chunk with finish_reason and usage
        if total_chunks == 0:
            yield NormalizedStreamChunk(
                delta="",
                finish_reason=self.finish_reason,
                usage=self.simulated_stream_usage,
                index=0,
                model=target_model,
            )

    async def validate_connection(self) -> bool:
        if self.is_closed:
            return False
        return True

    async def close(self) -> None:
        self.is_closed = True
