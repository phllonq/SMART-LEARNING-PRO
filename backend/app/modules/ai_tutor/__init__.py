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
from app.modules.ai_tutor.exceptions import (
    AITutorException,
    ConversationNotFoundException,
    ConversationAccessDeniedException,
    ConversationBusyException,
    InvalidMessageContentException,
    InvalidMessageStateTransitionError,
    LockAcquisitionException,
    StaleWorkerException,
    TutorProviderUnavailableException,
    TutorTimeoutException,
)
from app.modules.ai_tutor.services import (
    ConversationLockManager,
    conversation_lock_manager,
    ConversationService,
    conversation_service,
    SocraticTutorService,
    socratic_tutor_service,
    validate_message_state_transition,
    apply_message_state_transition,
    build_message_metadata_json,
    parse_message_metadata,
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
    "AITutorException",
    "ConversationNotFoundException",
    "ConversationAccessDeniedException",
    "ConversationBusyException",
    "InvalidMessageContentException",
    "InvalidMessageStateTransitionError",
    "LockAcquisitionException",
    "StaleWorkerException",
    "TutorProviderUnavailableException",
    "TutorTimeoutException",
    "ConversationLockManager",
    "conversation_lock_manager",
    "ConversationService",
    "conversation_service",
    "SocraticTutorService",
    "socratic_tutor_service",
    "validate_message_state_transition",
    "apply_message_state_transition",
    "build_message_metadata_json",
    "parse_message_metadata",
]
