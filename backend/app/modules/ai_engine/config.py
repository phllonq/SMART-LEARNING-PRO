"""
Centralized AI Configuration - SMART LEARNING PRO
Loads AI provider settings from application configuration, validates invariants,
and enforces security protections against credential leakage.
"""

from typing import Optional
from pydantic import BaseModel, Field
from app.config import settings
from app.modules.ai_engine.exceptions import AIConfigurationError


class AIConfig(BaseModel):
    """Immutable runtime configuration container for the AI Engine."""

    provider: str = Field(
        default="mock",
        description="Active AI provider: 'mock' or 'google'."
    )
    api_key: str = Field(
        default="",
        description="API key for cloud provider."
    )
    model: str = Field(
        default="gemini-3.8-flash",
        description="Default chat model ID."
    )
    timeout_seconds: float = Field(
        default=15.0,
        gt=0.0,
        le=120.0,
        description="Request timeout in seconds."
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum retry attempts on transient failures."
    )
    retry_backoff_base: float = Field(
        default=0.5,
        gt=0.0,
        le=10.0,
        description="Base multiplier for exponential backoff."
    )

    def validate_provider_configuration(self) -> None:
        """Validate provider-specific prerequisites."""
        provider_norm = self.provider.strip().lower()
        if provider_norm not in ("mock", "google"):
            raise AIConfigurationError(
                f"Unsupported AI provider: '{self.provider}'. Allowed providers are 'mock' and 'google'."
            )
        if provider_norm == "google" and not self.api_key.strip():
            raise AIConfigurationError(
                "GEMINI_API_KEY must be configured when AI_PROVIDER is 'google'."
            )

    def __repr__(self) -> str:
        masked_key = "***" if self.api_key else "(empty)"
        return (
            f"AIConfig(provider='{self.provider}', model='{self.model}', "
            f"timeout={self.timeout_seconds}s, max_retries={self.max_retries}, api_key={masked_key})"
        )

    def __str__(self) -> str:
        return self.__repr__()


def get_ai_config(settings_override=None) -> AIConfig:
    """Load AI configuration from application settings."""
    cfg = settings_override or settings
    config = AIConfig(
        provider=getattr(cfg, "AI_PROVIDER", "mock"),
        api_key=getattr(cfg, "GEMINI_API_KEY", ""),
        model=getattr(cfg, "GEMINI_MODEL", "gemini-3.8-flash"),
        timeout_seconds=float(getattr(cfg, "AI_TIMEOUT_SECONDS", 15.0)),
        max_retries=int(getattr(cfg, "AI_MAX_RETRIES", 2)),
        retry_backoff_base=float(getattr(cfg, "AI_RETRY_BACKOFF_BASE", 0.5)),
    )
    return config
