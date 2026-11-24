"""
Timeout and Retry Policy - SMART LEARNING PRO
Enforces exponential backoff with jitter, total request deadline, and strict error classification.
Ensures permanent errors fail fast without retry storms.
"""

import asyncio
import logging
import random
import time
from typing import Optional, Callable, Awaitable, AsyncIterator

from app.modules.ai_engine.contracts import (
    NormalizedChatRequest,
    NormalizedChatResponse,
    NormalizedStreamChunk,
)
from app.modules.ai_engine.exceptions import (
    AIEngineException,
    AITimeoutError,
    AIRateLimitError,
    AIServerError,
    AIAuthenticationError,
    AIInvalidRequestError,
    AIConfigurationError,
    AIMalformedResponseError,
)
from app.modules.ai_engine.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


def is_retryable_error(exc: Exception) -> bool:
    """Classify whether an exception should be retried."""
    if isinstance(exc, asyncio.CancelledError):
        return False
    if isinstance(exc, (AIRateLimitError, AIServerError, AITimeoutError)):
        return True
    if isinstance(exc, AIEngineException) and exc.retryable:
        return True
    # Permanent errors must never be retried
    if isinstance(exc, (AIAuthenticationError, AIInvalidRequestError, AIConfigurationError, AIMalformedResponseError)):
        return False
    # Standard asyncio timeout
    if isinstance(exc, asyncio.TimeoutError):
        return True
    return False


async def execute_with_retry(
    provider: BaseLLMProvider,
    request: NormalizedChatRequest,
    max_retries: int = 2,
    backoff_base: float = 0.5,
    total_timeout: float = 15.0,
) -> NormalizedChatResponse:
    """
    Execute generation with exponential backoff and total request deadline enforcement.

    Args:
        provider: Provider instance to execute against.
        request: Normalized chat request.
        max_retries: Maximum number of retry attempts (0 means only 1 initial attempt).
        backoff_base: Base multiplier in seconds for exponential backoff.
        total_timeout: Absolute total elapsed time budget for all attempts combined.

    Returns:
        NormalizedChatResponse on success.

    Raises:
        The last encountered exception if attempts or deadline are exhausted.
    """
    start_time = time.perf_counter()
    deadline = start_time + total_timeout
    total_attempts = max_retries + 1

    last_exception: Optional[Exception] = None

    for attempt in range(total_attempts):
        now = time.perf_counter()
        if now >= deadline:
            logger.warning(
                "AI request deadline exceeded before attempt %d/%d (elapsed: %.2fs, budget: %.2fs)",
                attempt + 1,
                total_attempts,
                now - start_time,
                total_timeout,
            )
            raise AITimeoutError(
                f"Overall AI request deadline of {total_timeout:.1f}s exceeded.",
                provider=provider.provider_name,
            )

        try:
            # Per-attempt remaining budget
            remaining_time = max(0.1, deadline - now)
            # If the provider supports per-call timeout, we could pass it, but standard timeout is provider-level
            response = await provider.generate(request)
            return response
        except asyncio.CancelledError:
            logger.info("Generation cancelled during execution loop; aborting retries.")
            raise
        except Exception as exc:
            last_exception = exc
            if not is_retryable_error(exc):
                logger.debug(
                    "Non-retryable error on attempt %d/%d for provider '%s': %s",
                    attempt + 1,
                    total_attempts,
                    provider.provider_name,
                    exc,
                )
                raise exc

            # If this was our last attempt, stop
            if attempt == max_retries:
                logger.warning(
                    "Exhausted all %d attempts for provider '%s'. Last error: %s",
                    total_attempts,
                    provider.provider_name,
                    exc,
                )
                raise exc

            # Calculate backoff with jitter
            # e.g., attempt 0: 0.5 * 2^0 = 0.5s + jitter
            #       attempt 1: 0.5 * 2^1 = 1.0s + jitter
            jitter = random.uniform(0.0, 0.1 * backoff_base)
            delay = (backoff_base * (2 ** attempt)) + jitter

            # Check if sleeping would blow past the deadline
            if time.perf_counter() + delay >= deadline:
                logger.warning(
                    "Cannot retry attempt %d/%d: backoff delay (%.2fs) exceeds remaining deadline (%.2fs)",
                    attempt + 2,
                    total_attempts,
                    delay,
                    deadline - time.perf_counter(),
                )
                raise AITimeoutError(
                    f"Overall AI request deadline of {total_timeout:.1f}s reached during retry backoff.",
                    provider=provider.provider_name,
                )

            logger.warning(
                "Provider '%s' failed attempt %d/%d [%s: %s]. Retrying in %.2fs...",
                provider.provider_name,
                attempt + 1,
                total_attempts,
                type(exc).__name__,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
    raise AIEngineException("Execution loop terminated without result or exception.", provider=provider.provider_name)


async def execute_stream_with_retry(
    provider: BaseLLMProvider,
    request: NormalizedChatRequest,
    max_retries: int = 2,
    backoff_base: float = 0.5,
    total_timeout: float = 15.0,
) -> AsyncIterator[NormalizedStreamChunk]:
    """
    Execute streaming generation with strict retry policy.

    STRICT POLICY:
    - Retries connection errors ONLY before the first token has been yielded.
    - NEVER retries after the first token has been yielded to caller (to avoid duplicate text).
    - Enforces total deadline across all retry attempts.
    - Re-raises non-retryable errors immediately.
    """
    start_time = time.perf_counter()
    deadline = start_time + total_timeout
    total_attempts = max_retries + 1

    last_exception: Optional[Exception] = None
    has_emitted_chunks = False

    for attempt in range(total_attempts):
        now = time.perf_counter()
        if now >= deadline:
            logger.warning(
                "AI stream deadline exceeded before attempt %d/%d (elapsed: %.2fs, budget: %.2fs)",
                attempt + 1,
                total_attempts,
                now - start_time,
                total_timeout,
            )
            raise AITimeoutError(
                f"Overall AI stream deadline of {total_timeout:.1f}s exceeded.",
                provider=provider.provider_name,
            )

        try:
            stream = provider.generate_stream(request)
            async for chunk in stream:
                has_emitted_chunks = True
                yield chunk
            # Stream completed successfully
            return
        except asyncio.CancelledError:
            logger.info("Generation cancelled during stream execution; aborting.")
            raise
        except Exception as exc:
            last_exception = exc

            # CRITICAL: If any chunk was already delivered, we CANNOT retry.
            if has_emitted_chunks:
                logger.warning(
                    "Error occurred after chunks were already emitted for provider '%s': %s. Aborting without retry.",
                    provider.provider_name,
                    exc,
                )
                raise exc

            # Non-retryable errors must fail immediately
            if not is_retryable_error(exc):
                logger.debug(
                    "Non-retryable error on streaming attempt %d/%d for provider '%s': %s",
                    attempt + 1,
                    total_attempts,
                    provider.provider_name,
                    exc,
                )
                raise exc

            # If last attempt reached
            if attempt == max_retries:
                logger.warning(
                    "Exhausted all %d streaming attempts for provider '%s'. Last error: %s",
                    total_attempts,
                    provider.provider_name,
                    exc,
                )
                raise exc

            jitter = random.uniform(0.0, 0.1 * backoff_base)
            delay = (backoff_base * (2 ** attempt)) + jitter

            if time.perf_counter() + delay >= deadline:
                logger.warning(
                    "Cannot retry stream attempt %d/%d: delay (%.2fs) exceeds deadline (%.2fs)",
                    attempt + 2,
                    total_attempts,
                    delay,
                    deadline - time.perf_counter(),
                )
                raise AITimeoutError(
                    f"Overall AI stream deadline of {total_timeout:.1f}s reached during retry backoff.",
                    provider=provider.provider_name,
                )

            logger.warning(
                "Provider '%s' failed stream attempt %d/%d [%s: %s]. Retrying in %.2fs...",
                provider.provider_name,
                attempt + 1,
                total_attempts,
                type(exc).__name__,
                exc,
                delay,
            )
            await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
    raise AIEngineException("Stream loop terminated without result or exception.", provider=provider.provider_name)


class ResilientLLMProvider(BaseLLMProvider):
    """Decorator wrapper that applies the retry and timeout policy around any BaseLLMProvider."""

    def __init__(
        self,
        underlying_provider: BaseLLMProvider,
        max_retries: int = 2,
        backoff_base: float = 0.5,
        total_timeout: float = 15.0,
    ):
        self._provider = underlying_provider
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.total_timeout = total_timeout

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    @property
    def default_model(self) -> str:
        return self._provider.default_model

    @property
    def underlying_provider(self) -> BaseLLMProvider:
        return self._provider

    async def generate(
        self,
        request: NormalizedChatRequest,
    ) -> NormalizedChatResponse:
        return await execute_with_retry(
            provider=self._provider,
            request=request,
            max_retries=self.max_retries,
            backoff_base=self.backoff_base,
            total_timeout=self.total_timeout,
        )

    async def generate_stream(
        self,
        request: NormalizedChatRequest,
    ) -> AsyncIterator[NormalizedStreamChunk]:
        async for chunk in execute_stream_with_retry(
            provider=self._provider,
            request=request,
            max_retries=self.max_retries,
            backoff_base=self.backoff_base,
            total_timeout=self.total_timeout,
        ):
            yield chunk

    async def validate_connection(self) -> bool:
        return await self._provider.validate_connection()

    async def close(self) -> None:
        await self._provider.close()
