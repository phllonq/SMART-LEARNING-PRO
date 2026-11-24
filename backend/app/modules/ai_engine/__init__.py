"""
AI Engine Module - SMART LEARNING PRO
Provides provider abstraction, normalized contracts, mock/Google GenAI integrations,
and usage accounting for AI-assisted educational workflows.
"""

from app.modules.ai_engine.contracts import (
    ChatMessage,
    NormalizedChatRequest,
    NormalizedChatResponse,
    NormalizedStreamChunk,
    NormalizedStreamUsage,
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
from app.modules.ai_engine.providers.base import BaseLLMProvider
from app.modules.ai_engine.providers.mock import MockAIProvider
from app.modules.ai_engine.providers.google_genai import GoogleGenAIProvider
from app.modules.ai_engine.retry import ResilientLLMProvider, execute_with_retry, execute_stream_with_retry
from app.modules.ai_engine.factory import get_llm_provider, ProviderFactory
from app.modules.ai_engine.usage import record_usage_to_db, calculate_estimated_cost, create_usage_record

__all__ = [
    "ChatMessage",
    "NormalizedChatRequest",
    "NormalizedChatResponse",
    "NormalizedStreamChunk",
    "NormalizedStreamUsage",
    "AIUsageRecord",
    "AIEngineException",
    "AIConfigurationError",
    "AIAuthenticationError",
    "AIRateLimitError",
    "AITimeoutError",
    "AIServerError",
    "AIInvalidRequestError",
    "AIMalformedResponseError",
    "BaseLLMProvider",
    "MockAIProvider",
    "GoogleGenAIProvider",
    "ResilientLLMProvider",
    "execute_with_retry",
    "execute_stream_with_retry",
    "get_llm_provider",
    "ProviderFactory",
    "record_usage_to_db",
    "calculate_estimated_cost",
    "create_usage_record",
]
