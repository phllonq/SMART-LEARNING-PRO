"""
AI Tutor Module - SMART LEARNING PRO
Provides Socratic conversational tutoring, prompt registries, domain contracts, and streaming session management.
"""

from app.modules.ai_tutor.schemas import (
    MessageStatus,
    MessageRole,
    ConversationCreateRequest,
    ConversationRenameRequest,
    ConversationResponse,
    ConversationListResponse,
    TutorMessageRequest,
    TutorMessageMetadata,
    TutorMessageResponse,
)
from app.modules.ai_tutor.prompts import (
    SOCRATIC_TUTOR_PROMPT_VERSION,
    get_socratic_prompt,
    get_prompt_metadata,
)

__all__ = [
    "MessageStatus",
    "MessageRole",
    "ConversationCreateRequest",
    "ConversationRenameRequest",
    "ConversationResponse",
    "ConversationListResponse",
    "TutorMessageRequest",
    "TutorMessageMetadata",
    "TutorMessageResponse",
    "SOCRATIC_TUTOR_PROMPT_VERSION",
    "get_socratic_prompt",
    "get_prompt_metadata",
]
