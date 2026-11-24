"""
Domain Schemas for Wrong Answer Diagnostic Engine — Phase 7.2.1

Pydantic v2 contracts for:
- WrongAnswerDiagnosticRequest   — API input (identifiers only, no client-supplied correctness)
- DiagnosticContext              — Internal server-side context assembled from DB
- DiagnosticDetail               — Structured AI diagnostic output
- WrongAnswerDiagnosticResponse  — Full API response envelope
- parse_llm_diagnostic_json()    — Strict LLM JSON parser (no auto-fix)

Security notes:
- Request only accepts UUIDs; no client-supplied answer correctness or free-form prompts.
- DiagnosticContext is populated server-side from the database; never from client input.
- parse_llm_diagnostic_json raises AIMalformedResponseError on any parsing failure;
  it does NOT auto-correct or silently coerce malformed structures.
- Prompt injection is mitigated structurally: untrusted data is placed in a separate
  user message (not merged into system_instruction). Prompt text is NOT a security boundary.
"""

import json
import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.ai_engine.exceptions import AIMalformedResponseError


# ---------------------------------------------------------------------------
# Error Category Enum
# ---------------------------------------------------------------------------

class ErrorCategory(str, Enum):
    """Diagnostic error categories that the AI engine can assign to a wrong answer."""

    CONCEPTUAL_MISCONCEPTION = "CONCEPTUAL_MISCONCEPTION"
    """Student misunderstands the core concept (not a calculation mistake)."""

    CALCULATION_ERROR = "CALCULATION_ERROR"
    """Student understood the approach but made an arithmetic or algebraic mistake."""

    QUESTION_MISREAD = "QUESTION_MISREAD"
    """Student misread or misinterpreted the question statement."""

    FORMULA_MISAPPLICATION = "FORMULA_MISAPPLICATION"
    """Student selected the right topic but applied the wrong formula or rule."""

    LOGICAL_GAP = "LOGICAL_GAP"
    """Student's reasoning chain had an identifiable logical step missing or inverted."""

    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    """AI cannot determine the error type with confidence from the available evidence."""


# ---------------------------------------------------------------------------
# UUID v4 validation pattern
# ---------------------------------------------------------------------------

_UUID_V4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _validate_uuid_v4(value: str, field_name: str) -> str:
    """Validate that a string is a valid UUID v4 and return it lowercased."""
    stripped = value.strip().lower()
    if not _UUID_V4_RE.match(stripped):
        raise ValueError(
            f"{field_name} must be a valid UUID v4 "
            f"(format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx). Got: {value!r}"
        )
    return stripped


# ---------------------------------------------------------------------------
# API Request Contract
# ---------------------------------------------------------------------------

class WrongAnswerDiagnosticRequest(BaseModel):
    """
    Client-facing request schema for the Wrong Answer Diagnostic endpoint.

    Security: Only accepts database identifiers.
    - No answer text, correctness flags, or prompt text accepted from client.
    - All content (question, answer, explanation) is loaded server-side from the database.
    - Disallows any extra client-provided fields (extra="forbid").
    """

    model_config = {"str_strip_whitespace": True, "extra": "forbid"}

    attempt_id: str = Field(
        ...,
        description="UUID v4 of the ExamAttempt record.",
    )
    question_id: str = Field(
        ...,
        description="UUID v4 of the Question record within the attempt.",
    )

    @field_validator("attempt_id")
    @classmethod
    def validate_attempt_id(cls, v: str) -> str:
        return _validate_uuid_v4(v, "attempt_id")

    @field_validator("question_id")
    @classmethod
    def validate_question_id(cls, v: str) -> str:
        return _validate_uuid_v4(v, "question_id")


# ---------------------------------------------------------------------------
# Internal Context Contract (server-side only, never from client)
# ---------------------------------------------------------------------------

class DiagnosticContext(BaseModel):
    """
    Internal context assembled server-side from database records.
    NEVER populated from client input.

    This model carries the question and answer content that will be passed
    structurally to the LLM prompt builder.
    """

    model_config = {"str_strip_whitespace": True}

    question_content: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="Full text of the question as stored in the database.",
    )
    question_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Question type identifier (e.g. 'multiple_choice', 'fill_in_blank').",
    )
    student_answer: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="The answer the student selected or entered. None if question was skipped.",
    )
    correct_answer: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The correct answer text as stored in the database.",
    )
    explanation: Optional[str] = Field(
        default=None,
        max_length=4000,
        description="Official explanation for why the correct answer is correct. Optional.",
    )

    @field_validator("question_content")
    @classmethod
    def validate_question_content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question_content cannot be blank.")
        return v.strip()

    @field_validator("correct_answer")
    @classmethod
    def validate_correct_answer_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("correct_answer cannot be blank.")
        return v.strip()

    @field_validator("student_answer")
    @classmethod
    def validate_student_answer(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None

    @field_validator("explanation")
    @classmethod
    def validate_explanation(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


# ---------------------------------------------------------------------------
# AI Output Contract
# ---------------------------------------------------------------------------

class DiagnosticDetail(BaseModel):
    """
    Structured diagnostic output parsed from LLM response JSON.

    All fields are required; no auto-fixing of partial or malformed responses.
    Use parse_llm_diagnostic_json() to construct this from raw LLM output.
    """

    model_config = {"str_strip_whitespace": True}

    error_category: ErrorCategory = Field(
        ...,
        description="Classified error type from the ErrorCategory enum.",
    )
    error_summary: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Short one-sentence summary of the diagnosed error.",
    )
    misconception_analysis: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Detailed analysis of the underlying misconception or mistake.",
    )
    step_by_step_guidance: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Step-by-step corrective guidance for the student.",
    )
    key_takeaway: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Single most important lesson the student should remember.",
    )
    suggested_review: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional topic or concept the student should review further.",
    )

    @field_validator("error_summary", "misconception_analysis", "step_by_step_guidance", "key_takeaway")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be blank or whitespace-only.")
        return v.strip()

    @field_validator("suggested_review")
    @classmethod
    def validate_suggested_review(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        stripped = v.strip()
        return stripped if stripped else None


# ---------------------------------------------------------------------------
# API Response Envelope
# ---------------------------------------------------------------------------

class WrongAnswerDiagnosticResponse(BaseModel):
    """
    Full API response envelope for the Wrong Answer Diagnostic endpoint.
    """

    diagnostic: Optional[DiagnosticDetail] = Field(
        default=None,
        description=(
            "Structured diagnostic detail. None when is_sufficient is False "
            "(AI did not have enough evidence to produce a reliable diagnosis)."
        ),
    )
    cached: bool = Field(
        default=False,
        description="True if this response was served from cache.",
    )
    latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total generation latency in milliseconds (0.0 if cached).",
    )
    prompt_version: str = Field(
        ...,
        description="SemVer string of the prompt template used (e.g. '1.0.0').",
    )
    is_sufficient: bool = Field(
        default=True,
        description=(
            "False when the AI reported INSUFFICIENT_INFORMATION — "
            "the system did not have enough context to produce a reliable diagnosis."
        ),
    )


# ---------------------------------------------------------------------------
# LLM Response Parser (strict, no auto-fix)
# ---------------------------------------------------------------------------

_CODE_FENCE_RE = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def parse_llm_diagnostic_json(raw_json_str: str) -> DiagnosticDetail:
    """
    Parse and validate a raw LLM response string into a DiagnosticDetail.

    Steps:
    1. Strip surrounding whitespace.
    2. Remove markdown code fences (```json ... ``` or ``` ... ```).
    3. Parse as JSON — raises AIMalformedResponseError if not valid JSON.
    4. Reject if parsed value is not a dict (e.g. JSON array) — raises AIMalformedResponseError.
    5. Validate via DiagnosticDetail.model_validate() — raises AIMalformedResponseError on failure.

    Does NOT auto-fix, coerce, or guess missing fields.

    Args:
        raw_json_str: Raw string output from LLM provider.

    Returns:
        Validated DiagnosticDetail instance.

    Raises:
        AIMalformedResponseError: On any parsing or validation failure.
    """
    if not isinstance(raw_json_str, str):
        raise AIMalformedResponseError(
            f"LLM response must be a string, got {type(raw_json_str).__name__}."
        )

    cleaned = raw_json_str.strip()

    # Strip markdown code fences
    fence_match = _CODE_FENCE_RE.match(cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    # Parse JSON
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIMalformedResponseError(
            f"LLM response is not valid JSON: {exc}. "
            f"Raw (first 200 chars): {cleaned[:200]!r}"
        ) from exc

    # Must be a dict (object), not an array or scalar
    if not isinstance(parsed, dict):
        raise AIMalformedResponseError(
            f"LLM response JSON must be an object (dict), got {type(parsed).__name__}. "
            f"Value: {str(parsed)[:200]!r}"
        )

    # Validate via Pydantic — strict, no auto-fix
    try:
        return DiagnosticDetail.model_validate(parsed)
    except Exception as exc:
        raise AIMalformedResponseError(
            f"LLM response failed DiagnosticDetail schema validation: {exc}. "
            f"Keys present: {list(parsed.keys())}"
        ) from exc
