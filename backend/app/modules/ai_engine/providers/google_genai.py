"""
Google GenAI Provider - SMART LEARNING PRO
Integrates with the official, actively maintained `google-genai` Python SDK.
Normalizes Google responses into vendor-neutral contracts and enforces timeout/security boundaries.
"""

import asyncio
import logging
import time
import uuid
from typing import Optional, List, Dict, Any, AsyncIterator

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

from app.modules.ai_engine.contracts import (
    NormalizedChatRequest,
    NormalizedChatResponse,
    NormalizedStreamChunk,
    NormalizedStreamUsage,
)
from app.modules.ai_engine.exceptions import (
    AIEngineException,
    AIAuthenticationError,
    AIRateLimitError,
    AITimeoutError,
    AIServerError,
    AIInvalidRequestError,
    AIMalformedResponseError,
)
from app.modules.ai_engine.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class GoogleGenAIProvider(BaseLLMProvider):
    """Production provider connecting to Google Gemini using official google-genai SDK."""

    def __init__(
        self,
        api_key: str,
        default_model: str = "gemini-3.8-flash",
        timeout_seconds: float = 15.0,
    ):
        if not api_key or not api_key.strip():
            raise ValueError("api_key must be non-empty for GoogleGenAIProvider.")

        self._api_key = api_key.strip()
        self._default_model = default_model.strip()
        self.timeout_seconds = timeout_seconds

        # Persistent reusable GenAI client instance
        self._client: Optional[genai.Client] = genai.Client(api_key=self._api_key)
        self._is_closed: bool = False

    @property
    def provider_name(self) -> str:
        return "google"

    @property
    def default_model(self) -> str:
        return self._default_model

    def _sanitize_error_message(self, message: str) -> str:
        """Strip API key or sensitive token strings from exception messages."""
        if not message:
            return "Unknown Google GenAI error."
        if self._api_key and self._api_key in message:
            message = message.replace(self._api_key, "[REDACTED_API_KEY]")
        return message

    def _convert_messages_to_contents(
        self, request: NormalizedChatRequest
    ) -> tuple[List[types.Content], Optional[str]]:
        """Convert normalized ChatMessage objects to Google GenAI Content objects."""
        contents: List[types.Content] = []
        system_instructions: List[str] = []

        if request.system_instruction:
            system_instructions.append(request.system_instruction)

        for msg in request.messages:
            if msg.role == "system":
                system_instructions.append(msg.content)
            elif msg.role == "user":
                part = types.Part.from_text(text=msg.content)
                contents.append(types.Content(role="user", parts=[part]))
            elif msg.role == "assistant":
                # Google GenAI uses 'model' role for assistant messages
                part = types.Part.from_text(text=msg.content)
                contents.append(types.Content(role="model", parts=[part]))

        combined_sys_instruction = "\n\n".join(system_instructions) if system_instructions else None
        return contents, combined_sys_instruction

    async def generate(
        self,
        request: NormalizedChatRequest,
    ) -> NormalizedChatResponse:
        if self._is_closed or self._client is None:
            raise AIEngineException("GoogleGenAIProvider instance is closed.", provider="google")

        target_model = request.model or self._default_model
        contents, system_instruction = self._convert_messages_to_contents(request)

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
        )

        t_start = time.perf_counter()

        try:
            call_coro = self._client.aio.models.generate_content(
                model=target_model,
                contents=contents,
                config=config,
            )
            raw_response = await asyncio.wait_for(call_coro, timeout=self.timeout_seconds)
        except asyncio.CancelledError:
            logger.info("Google GenAI request cancelled by caller.")
            raise
        except asyncio.TimeoutError:
            raise AITimeoutError(
                f"Google GenAI request timed out after {self.timeout_seconds:.1f}s.",
                provider="google",
            )
        except genai_errors.APIError as exc:
            msg = self._sanitize_error_message(getattr(exc, "message", str(exc)))
            code = getattr(exc, "code", 500)
            logger.warning("Google GenAI API error [%s]: %s", code, msg)

            if code == 429:
                raise AIRateLimitError(msg, provider="google")
            elif code in (401, 403):
                raise AIAuthenticationError(msg, provider="google")
            elif code == 400:
                raise AIInvalidRequestError(msg, provider="google")
            elif code in (500, 502, 503, 504):
                raise AIServerError(msg, provider="google", status_code=code)
            else:
                raise AIEngineException(msg, provider="google", status_code=code)
        except Exception as exc:
            msg = self._sanitize_error_message(str(exc))
            logger.error("Unexpected error in GoogleGenAIProvider: %s", msg)
            raise AIEngineException(f"Google GenAI generation failed: {msg}", provider="google")

        t_end = time.perf_counter()
        latency_ms = round((t_end - t_start) * 1000.0, 2)

        return self._normalize_response(raw_response, target_model, latency_ms)

    def _map_api_error(self, exc: Exception) -> Exception:
        """Map SDK errors and generic exceptions to AIEngineException hierarchy."""
        if isinstance(exc, (AIEngineException, asyncio.CancelledError)):
            return exc
        if isinstance(exc, asyncio.TimeoutError):
            return AITimeoutError(
                f"Google GenAI request timed out after {self.timeout_seconds:.1f}s.",
                provider="google",
            )
        if isinstance(exc, genai_errors.APIError):
            msg = self._sanitize_error_message(getattr(exc, "message", str(exc)))
            code = getattr(exc, "code", 500)
            logger.warning("Google GenAI API error [%s]: %s", code, msg)

            if code == 429:
                return AIRateLimitError(msg, provider="google")
            elif code in (401, 403):
                return AIAuthenticationError(msg, provider="google")
            elif code == 400:
                return AIInvalidRequestError(msg, provider="google")
            elif code in (500, 502, 503, 504):
                return AIServerError(msg, provider="google", status_code=code)
            else:
                return AIEngineException(msg, provider="google", status_code=code)

        msg = self._sanitize_error_message(str(exc))
        logger.error("Unexpected error in GoogleGenAIProvider: %s", msg)
        return AIEngineException(f"Google GenAI operation failed: {msg}", provider="google")

    async def generate_stream(
        self,
        request: NormalizedChatRequest,
    ) -> AsyncIterator[NormalizedStreamChunk]:
        """
        Execute an asynchronous streaming completion request against Google GenAI.
        Yields NormalizedStreamChunk objects incrementally as tokens arrive.
        """
        if self._is_closed or self._client is None:
            raise AIEngineException("GoogleGenAIProvider instance is closed.", provider="google")

        target_model = request.model or self._default_model
        contents, system_instruction = self._convert_messages_to_contents(request)

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
        )

        t_start = time.perf_counter()
        deadline = t_start + self.timeout_seconds

        try:
            call_coro = self._client.aio.models.generate_content_stream(
                model=target_model,
                contents=contents,
                config=config,
            )
            stream_response = await asyncio.wait_for(call_coro, timeout=self.timeout_seconds)
        except Exception as exc:
            raise self._map_api_error(exc)

        chunk_idx = 0
        stream_iter = stream_response.__aiter__()
        while True:
            now = time.perf_counter()
            if now >= deadline:
                raise AITimeoutError(
                    f"Google GenAI stream timed out after {self.timeout_seconds:.1f}s.",
                    provider="google",
                )
            remaining = max(0.1, deadline - now)
            try:
                raw_chunk = await asyncio.wait_for(stream_iter.__anext__(), timeout=remaining)
            except StopAsyncIteration:
                break
            except Exception as exc:
                raise self._map_api_error(exc)

            # Extract delta text safely
            chunk_text = ""
            try:
                raw_text = getattr(raw_chunk, "text", "")
                chunk_text = str(raw_text) if isinstance(raw_text, str) else ""
            except Exception:
                chunk_text = ""

            # Extract finish_reason safely
            finish_reason: Optional[str] = None
            if getattr(raw_chunk, "candidates", None):
                first_cand = raw_chunk.candidates[0]
                raw_finish = getattr(first_cand, "finish_reason", None)
                if raw_finish is not None and isinstance(raw_finish, (str, int)):
                    finish_reason = str(raw_finish)

            # Extract usage_metadata if provided on this chunk
            stream_usage: Optional[NormalizedStreamUsage] = None
            usage = getattr(raw_chunk, "usage_metadata", None)
            if usage is not None:
                raw_in = getattr(usage, "prompt_token_count", None)
                raw_out = getattr(usage, "candidates_token_count", None)
                raw_tot = getattr(usage, "total_token_count", None)
                raw_cached = getattr(usage, "cached_content_token_count", None)
                raw_thoughts = getattr(usage, "thoughts_token_count", None)

                stream_usage = NormalizedStreamUsage(
                    input_tokens=int(raw_in) if isinstance(raw_in, (int, float)) else None,
                    output_tokens=int(raw_out) if isinstance(raw_out, (int, float)) else None,
                    total_tokens=int(raw_tot) if isinstance(raw_tot, (int, float)) else None,
                    cached_tokens=int(raw_cached) if isinstance(raw_cached, (int, float)) else None,
                    thoughts_tokens=int(raw_thoughts) if isinstance(raw_thoughts, (int, float)) else None,
                )

            yield NormalizedStreamChunk(
                delta=chunk_text,
                finish_reason=finish_reason,
                usage=stream_usage,
                index=chunk_idx,
                model=target_model,
            )
            chunk_idx += 1

    def _normalize_response(
        self,
        raw_response: types.GenerateContentResponse,
        model: str,
        latency_ms: float,
    ) -> NormalizedChatResponse:
        """Map raw GenerateContentResponse into NormalizedChatResponse without inventing values."""
        # Extract text safely
        text_content = ""
        finish_reason: Optional[str] = None

        if raw_response.candidates:
            first_candidate = raw_response.candidates[0]
            raw_finish = getattr(first_candidate, "finish_reason", None)
            if raw_finish is not None and isinstance(raw_finish, (str, int)):
                finish_reason = str(raw_finish)

        try:
            raw_text = getattr(raw_response, "text", "")
            text_content = str(raw_text) if isinstance(raw_text, str) else ""
        except Exception:
            # When response has no text parts (e.g. safety blocks or empty candidates)
            text_content = ""

        # Extract tokens strictly from actual usage metadata
        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None
        total_tokens: Optional[int] = None
        cached_tokens: Optional[int] = None
        thoughts_tokens: Optional[int] = None

        usage = getattr(raw_response, "usage_metadata", None)
        if usage is not None:
            raw_in = getattr(usage, "prompt_token_count", None)
            input_tokens = int(raw_in) if isinstance(raw_in, (int, float)) else None

            # IMPORTANT: In google-genai SDK, candidates_token_count ALREADY includes thoughts_token_count!
            # Do NOT add thoughts_token_count to candidates_token_count to avoid double-counting.
            raw_out = getattr(usage, "candidates_token_count", None)
            output_tokens = int(raw_out) if isinstance(raw_out, (int, float)) else None

            raw_tot = getattr(usage, "total_token_count", None)
            total_tokens = int(raw_tot) if isinstance(raw_tot, (int, float)) else None

            raw_cached = getattr(usage, "cached_content_token_count", None)
            cached_tokens = int(raw_cached) if isinstance(raw_cached, (int, float)) else None

            raw_thoughts = getattr(usage, "thoughts_token_count", None)
            thoughts_tokens = int(raw_thoughts) if isinstance(raw_thoughts, (int, float)) else None

        raw_req_id = getattr(raw_response, "response_id", None)
        if isinstance(raw_req_id, str) and raw_req_id.strip():
            request_id = raw_req_id.strip()
        else:
            request_id = f"genai-{uuid.uuid4()}"

        resp_metadata: Dict[str, Any] = {}
        if cached_tokens is not None:
            resp_metadata["cached_tokens"] = cached_tokens
        if thoughts_tokens is not None:
            resp_metadata["thoughts_tokens"] = thoughts_tokens

        return NormalizedChatResponse(
            text=text_content,
            model=model,
            provider="google",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            finish_reason=finish_reason,
            request_id=request_id,
            latency_ms=latency_ms,
            metadata=resp_metadata,
        )

    async def validate_connection(self) -> bool:
        """Lightweight sanity check on client readiness."""
        if self._is_closed or not self._client:
            return False
        return True

    async def close(self) -> None:
        """Release underlying HTTP sessions and client resources."""
        self._is_closed = True
        if self._client is not None:
            try:
                if hasattr(self._client, "aio") and hasattr(self._client.aio, "aclose"):
                    await self._client.aio.aclose()
            except Exception as exc:
                logger.warning("Error closing Google GenAI async client: %s", exc)
            try:
                if hasattr(self._client, "close"):
                    self._client.close()
            except Exception as exc:
                logger.warning("Error closing Google GenAI sync client: %s", exc)
            finally:
                self._client = None
