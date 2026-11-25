"""
AI Tutor Services - SMART LEARNING PRO
Exports conversation lifecycle management, Socratic streaming orchestration,
distributed locking, and message state transitions.
"""

from app.modules.ai_tutor.services.conversation_lock import (
    ConversationLockManager,
    conversation_lock_manager,
)
from app.modules.ai_tutor.services.conversation_service import (
    ConversationService,
    conversation_service,
)
from app.modules.ai_tutor.services.message_state import (
    ALLOWED_TRANSITIONS,
    validate_message_state_transition,
    apply_message_state_transition,
    build_message_metadata_json,
    parse_message_metadata,
)
from app.modules.ai_tutor.services.tutor_service import (
    SocraticTutorService,
    socratic_tutor_service,
)

__all__ = [
    "ConversationLockManager",
    "conversation_lock_manager",
    "ConversationService",
    "conversation_service",
    "ALLOWED_TRANSITIONS",
    "validate_message_state_transition",
    "apply_message_state_transition",
    "build_message_metadata_json",
    "parse_message_metadata",
    "SocraticTutorService",
    "socratic_tutor_service",
]
