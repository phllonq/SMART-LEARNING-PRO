"""
Normalized Provider Contracts - SMART LEARNING PRO
Pydantic v2 domain schemas defining vendor-neutral request and response structures.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict


class ChatMessage(BaseModel):
    """Normalized chat message structure."""

    role: Literal["system", "user", "assistant"] = Field(
        ...,
        description="Role of the message sender."
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=65536,
        description="Text content of the message."
    )

    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message content cannot be blank or whitespace-only.")
        return stripped


class NormalizedChatRequest(BaseModel):
    """Normalized request passed into any BaseLLMProvider implementation."""

    messages: List[ChatMessage] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Sequential list of conversation messages."
    )
    model: Optional[str] = Field(
        default=None,
        description="Optional model ID override. If None, uses provider default."
    )
    system_instruction: Optional[str] = Field(
        default=None,
        max_length=32768,
        description="System instruction guiding model persona and behavioral constraints."
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature between 0.0 and 2.0."
    )
    max_output_tokens: Optional[int] = Field(
        default=2048,
        ge=1,
        le=32768,
        description="Maximum tokens the model is allowed to generate in the completion."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary JSON-serializable request context metadata (e.g. user_id, feature)."
    )

    @field_validator("system_instruction")
    @classmethod
    def strip_system_instruction(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            return stripped if stripped else None
        return None


class NormalizedChatResponse(BaseModel):
    """Normalized response returned from any BaseLLMProvider implementation."""

    text: str = Field(
        default="",
        description="Generated text response from the LLM."
    )
    model: str = Field(
        ...,
        description="Exact model ID that produced this response."
    )
    provider: str = Field(
        ...,
        description="Identifier of the provider (e.g., 'mock', 'google')."
    )
    input_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of prompt/input tokens consumed, or None if unavailable from provider."
    )
    output_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        description="Number of completion/output tokens generated, or None if unavailable from provider."
    )
    total_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total tokens consumed, or None if unavailable from provider."
    )
    finish_reason: Optional[str] = Field(
        default=None,
        description="Reason the generation finished (e.g., 'STOP', 'MAX_TOKENS', 'SAFETY')."
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Unique identifier for the request if provided by upstream gateway."
    )
    latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total roundtrip generation latency in milliseconds."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary provider metadata (e.g., cached_tokens, thoughts_tokens)."
    )


class NormalizedStreamUsage(BaseModel):
    """Normalized token usage metrics reported upon stream conclusion."""

    model_config = ConfigDict(extra="allow")

    input_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        description="Prompt / input tokens consumed, or None if unavailable from provider.",
    )
    output_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        description="Generated / completion tokens produced, or None if unavailable from provider.",
    )
    total_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        description="Total tokens consumed, or None if unavailable from provider.",
    )
    cached_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        description="Prompt tokens served from context cache, or None if unavailable.",
    )
    thoughts_tokens: Optional[int] = Field(
        default=None,
        ge=0,
        description="Reasoning / thinking tokens included in completion tokens, or None if unavailable.",
    )

    def __init__(self, **data: Any):
        # Support legacy shorthand keys (e.g. usage={"input": 10, "output": 20})
        if "input" in data and "input_tokens" not in data:
            data["input_tokens"] = data["input"]
        if "output" in data and "output_tokens" not in data:
            data["output_tokens"] = data["output"]
        if "total" in data and "total_tokens" not in data:
            data["total_tokens"] = data["total"]
        super().__init__(**data)

    def __getitem__(self, item: str) -> Any:
        """Allow subscripting like a dict for backward compatibility with existing tests."""
        if item == "input":
            return self.input_tokens
        if item == "output":
            return self.output_tokens
        if item == "total":
            return self.total_tokens
        if hasattr(self, item):
            return getattr(self, item)
        extra = getattr(self, "__pydantic_extra__", {}) or {}
        if item in extra:
            return extra[item]
        raise KeyError(item)


class NormalizedStreamChunk(BaseModel):
    """
    Vendor-neutral streaming chunk emitted by BaseLLMProvider.generate_stream().
    Guarantees consistent text extraction, lifecycle flags, and usage attribution.
    """

    delta: str = Field(
        default="",
        description="Incremental text chunk generated in this step.",
    )
    delta_text: str = Field(
        default="",
        description="Backward-compatible alias for delta.",
    )
    is_final: bool = Field(
        default=False,
        description="True if this is the final closing chunk of the stream.",
    )
    finish_reason: Optional[str] = Field(
        default=None,
        description="Reason the generation concluded (e.g., 'STOP', 'MAX_TOKENS', 'SAFETY').",
    )
    usage: Optional[Union[NormalizedStreamUsage, Dict[str, Any]]] = Field(
        default=None,
        description="Final token metrics if reported by provider on stream conclusion.",
    )
    index: int = Field(
        default=0,
        ge=0,
        description="Zero-based sequence index of this chunk in the stream.",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model identifier used for generation.",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary provider-specific chunk metadata.",
    )

    def __init__(self, **data: Any):
        # Bi-directional synchronization between delta and delta_text for seamless backward compatibility
        if "delta" in data and "delta_text" not in data:
            data["delta_text"] = data["delta"]
        elif "delta_text" in data and "delta" not in data:
            data["delta"] = data["delta_text"]
        elif "delta" not in data and "delta_text" not in data:
            data["delta"] = ""
            data["delta_text"] = ""

        # Auto-convert dict usage to NormalizedStreamUsage if needed
        if "usage" in data and isinstance(data["usage"], dict):
            data["usage"] = NormalizedStreamUsage(**data["usage"])

        super().__init__(**data)


class AIUsageRecord(BaseModel):
    """Normalized usage and accounting record prior to persistence."""

    user_id: Optional[str] = Field(
        default=None,
        description="User UUID associated with this AI interaction."
    )
    feature: str = Field(
        default="AI_FOUNDATION",
        description="System feature tag (e.g. 'TUTOR_CHAT', 'WRONG_ANSWER_ANALYSIS')."
    )
    provider: str = Field(
        ...,
        description="Provider name (e.g. 'mock', 'google')."
    )
    model_name: str = Field(
        ...,
        description="Model name utilized."
    )
    input_tokens: Optional[int] = Field(
        default=None,
        description="Prompt tokens reported by provider."
    )
    output_tokens: Optional[int] = Field(
        default=None,
        description="Completion tokens reported by provider."
    )
    total_tokens: Optional[int] = Field(
        default=None,
        description="Total tokens reported by provider."
    )
    cached_tokens: Optional[int] = Field(
        default=None,
        description="Number of prompt tokens served from context cache."
    )
    thoughts_tokens: Optional[int] = Field(
        default=None,
        description="Number of reasoning/thinking tokens included inside output_tokens."
    )
    estimated_cost_usd: Optional[float] = Field(
        default=None,
        description="Calculated cost in USD if pricing metadata is available."
    )
    latency_ms: float = Field(
        default=0.0,
        description="Roundtrip latency in milliseconds."
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp of request execution in UTC."
    )
