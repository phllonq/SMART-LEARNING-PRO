"""
Provider Factory - SMART LEARNING PRO
Constructs and configures LLM providers based on application settings.
Prevents silent fallbacks and enforces strict credential verification.
"""

import logging
from typing import Optional

from app.modules.ai_engine.config import AIConfig, get_ai_config
from app.modules.ai_engine.exceptions import AIConfigurationError
from app.modules.ai_engine.providers.base import BaseLLMProvider
from app.modules.ai_engine.providers.mock import MockAIProvider
from app.modules.ai_engine.providers.google_genai import GoogleGenAIProvider
from app.modules.ai_engine.retry import ResilientLLMProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory responsible for instantiating verified BaseLLMProvider instances."""

    @classmethod
    def create_raw_provider(
        cls,
        config: AIConfig,
    ) -> BaseLLMProvider:
        """Create the raw underlying provider without retry/resilience wrappers."""
        provider_name = config.provider.strip().lower()

        if provider_name == "mock":
            return MockAIProvider(
                model_name=config.model,
            )

        if provider_name == "google":
            if not config.api_key or not config.api_key.strip():
                raise AIConfigurationError(
                    "GEMINI_API_KEY must be configured when AI_PROVIDER is 'google'. "
                    "Silent fallback to mock is strictly disallowed.",
                    provider="google",
                )
            return GoogleGenAIProvider(
                api_key=config.api_key,
                default_model=config.model,
                timeout_seconds=config.timeout_seconds,
            )

        raise AIConfigurationError(
            f"Unsupported AI provider '{config.provider}'. Allowed providers: 'mock', 'google'."
        )

    @classmethod
    def create_provider(
        cls,
        config: Optional[AIConfig] = None,
        with_resilience: bool = True,
    ) -> BaseLLMProvider:
        """
        Create a fully configured provider, optionally decorated with the ResilientLLMProvider
        to enforce retry backoff and overall timeout budget.
        """
        cfg = config or get_ai_config()
        cfg.validate_provider_configuration()

        raw_provider = cls.create_raw_provider(cfg)

        if not with_resilience:
            return raw_provider

        # Wrap with resilience policy
        return ResilientLLMProvider(
            underlying_provider=raw_provider,
            max_retries=cfg.max_retries,
            backoff_base=cfg.retry_backoff_base,
            total_timeout=cfg.timeout_seconds,
        )


def get_llm_provider(
    config: Optional[AIConfig] = None,
    with_resilience: bool = True,
) -> BaseLLMProvider:
    """Convenience helper to obtain the configured provider singleton or instance."""
    return ProviderFactory.create_provider(config=config, with_resilience=with_resilience)
