"""
Base Provider Abstraction - SMART LEARNING PRO
Defines the abstract contract for all LLM providers.
"""

from abc import ABC, abstractmethod
from typing import Optional, AsyncIterator

from app.modules.ai_engine.contracts import (
    NormalizedChatRequest,
    NormalizedChatResponse,
    NormalizedStreamChunk,
)


class BaseLLMProvider(ABC):
    """Abstract asynchronous base class for all LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique canonical name of this provider (e.g. 'mock', 'google')."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model ID associated with this provider instance."""
        ...

    @abstractmethod
    async def generate(
        self,
        request: NormalizedChatRequest,
    ) -> NormalizedChatResponse:
        """
        Execute an asynchronous chat completion request and return a NormalizedChatResponse.

        Raises:
            AIEngineException or its subclasses on error.
        """
        ...

    async def generate_stream(
        self,
        request: NormalizedChatRequest,
    ) -> AsyncIterator[NormalizedStreamChunk]:
        """
        Execute an asynchronous streaming chat completion request and yield NormalizedStreamChunk instances.

        Raises:
            AIEngineException or its subclasses on error.
            NotImplementedError if the provider does not support streaming.
        """
        raise NotImplementedError(f"Provider '{self.provider_name}' does not implement streaming.")
        yield  # pragma: no cover

    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        Validate provider readiness and authentication credentials.
        Returns True if operational, False or raises AIConfigurationError / AIAuthenticationError.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release underlying HTTP sessions, network sockets, or client resources."""
        ...

