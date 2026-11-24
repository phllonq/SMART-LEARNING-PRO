"""
Wrong Answer Diagnostic Engine — SMART LEARNING PRO Phase 7.2

Provides:
- Domain schemas (Pydantic v2 contracts)
- Declarative prompt registry & versioning
- WrongAnswerDiagnosticService (authoritative loading, authorization, caching, AI orchestration)
- Service-level domain exceptions
"""

from app.modules.ai_engine.diagnostics.schemas import (
    ErrorCategory,
    WrongAnswerDiagnosticRequest,
    DiagnosticContext,
    DiagnosticDetail,
    WrongAnswerDiagnosticResponse,
    parse_llm_diagnostic_json,
)
from app.modules.ai_engine.diagnostics.prompts import (
    PROMPT_VERSION,
    PROMPT_KEY,
    REGISTRY_KEY,
    PROMPT_REGISTRY,
    build_diagnostic_prompt,
    get_prompt_version,
)
from app.modules.ai_engine.diagnostics.exceptions import (
    DiagnosticError,
    AttemptNotFoundException,
    DiagnosticUnauthorizedException,
    AttemptNotSubmittedException,
    QuestionNotInAttemptException,
    QuestionAlreadyCorrectException,
    GradingUnavailableException,
    InsufficientEvidenceException,
    AIProviderUnavailableException,
    AITimeoutException,
    AIMalformedOutputException,
    CacheCoordinationException,
)
from app.modules.ai_engine.diagnostics.service import (
    WrongAnswerDiagnosticService,
    ALLOWED_TERMINAL_STATUSES,
)
from app.modules.ai_engine.diagnostics.dependencies import (
    get_diagnostic_service,
    get_current_student,
)
from app.modules.ai_engine.diagnostics.router import router

__all__ = [
    # Enums
    "ErrorCategory",
    # Request / context schemas
    "WrongAnswerDiagnosticRequest",
    "DiagnosticContext",
    # Response schemas
    "DiagnosticDetail",
    "WrongAnswerDiagnosticResponse",
    # JSON parsing helper
    "parse_llm_diagnostic_json",
    # Prompt registry
    "PROMPT_VERSION",
    "PROMPT_KEY",
    "REGISTRY_KEY",
    "PROMPT_REGISTRY",
    "build_diagnostic_prompt",
    "get_prompt_version",
    # Exceptions
    "DiagnosticError",
    "AttemptNotFoundException",
    "DiagnosticUnauthorizedException",
    "AttemptNotSubmittedException",
    "QuestionNotInAttemptException",
    "QuestionAlreadyCorrectException",
    "GradingUnavailableException",
    "InsufficientEvidenceException",
    "AIProviderUnavailableException",
    "AITimeoutException",
    "AIMalformedOutputException",
    "CacheCoordinationException",
    # Service
    "WrongAnswerDiagnosticService",
    "ALLOWED_TERMINAL_STATUSES",
    # Dependencies & Router
    "get_diagnostic_service",
    "get_current_student",
    "router",
]
