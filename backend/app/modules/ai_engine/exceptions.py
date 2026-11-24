"""
Exceptions for AI Engine - SMART LEARNING PRO
All exceptions inherit from AIEngineException and indicate whether they are retryable.
"""

from typing import Optional


class AIEngineException(Exception):
    """Base exception for all AI Engine operations."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        retryable: bool = False,
        status_code: Optional[int] = None,
    ):
        self.message = message
        self.provider = provider
        self.retryable = retryable
        self.status_code = status_code
        super().__init__(message)


class AIConfigurationError(AIEngineException):
    """Raised when provider configuration or required credentials are missing or invalid. Non-retryable."""

    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider=provider, retryable=False, status_code=500)


class AIAuthenticationError(AIEngineException):
    """Raised when provider authentication fails (e.g. invalid API key). Non-retryable."""

    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider=provider, retryable=False, status_code=401)


class AIRateLimitError(AIEngineException):
    """Raised when provider returns HTTP 429 / RESOURCE_EXHAUSTED. Retryable."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        retry_after_seconds: Optional[float] = None,
    ):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(message, provider=provider, retryable=True, status_code=429)


class AITimeoutError(AIEngineException):
    """Raised when provider call exceeds the configured timeout or deadline. Retryable."""

    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider=provider, retryable=True, status_code=504)


class AIServerError(AIEngineException):
    """Raised when provider returns a 5xx / UNAVAILABLE / INTERNAL error. Retryable."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        status_code: int = 500,
    ):
        super().__init__(message, provider=provider, retryable=True, status_code=status_code)


class AIInvalidRequestError(AIEngineException):
    """Raised when input parameters, model ID, or prompt schema are invalid. Non-retryable."""

    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider=provider, retryable=False, status_code=400)


class AIMalformedResponseError(AIEngineException):
    """Raised when provider returns an unparseable or corrupted response. Non-retryable."""

    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, provider=provider, retryable=False, status_code=502)
