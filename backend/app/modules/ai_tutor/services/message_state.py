"""
Message State Machine & Metadata Serialization - SMART LEARNING PRO
Enforces valid lifecycle transitions and versioned JSON metadata for AI Tutor messages.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.modules.ai_tutor.exceptions import InvalidMessageStateTransitionError
from app.modules.ai_tutor.schemas import MessageStatus, TutorMessageMetadata

logger = logging.getLogger(__name__)

# Allowed state transitions: from_status -> set of allowed to_statuses
ALLOWED_TRANSITIONS: Dict[MessageStatus, set[MessageStatus]] = {
    MessageStatus.PENDING: {
        MessageStatus.STREAMING,
        MessageStatus.FAILED,
        MessageStatus.INTERRUPTED,
    },
    MessageStatus.STREAMING: {
        MessageStatus.COMPLETED,
        MessageStatus.FAILED,
        MessageStatus.INTERRUPTED,
    },
    # Terminal states have no valid transitions
    MessageStatus.COMPLETED: set(),
    MessageStatus.FAILED: set(),
    MessageStatus.INTERRUPTED: set(),
}


def validate_message_state_transition(
    current_status: MessageStatus,
    target_status: MessageStatus,
) -> None:
    """
    Validate that transitioning from current_status to target_status is permitted.

    Raises:
        InvalidMessageStateTransitionError: If the transition is disallowed.
    """
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        logger.warning(
            "Rejected invalid message state transition: %s -> %s",
            current_status.value,
            target_status.value,
        )
        raise InvalidMessageStateTransitionError(
            current_status=current_status.value,
            target_status=target_status.value,
        )


def build_message_metadata_json(
    status: MessageStatus,
    version: int = 1,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    model_name: Optional[str] = None,
    latency_ms: Optional[float] = None,
    error_message: Optional[str] = None,
    existing_metadata_json: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    enforce_transition: bool = True,
) -> str:
    """
    Construct a versioned, sanitized JSON string to store in AIMessage.metadata_json.
    Preserves any non-colliding extra fields from existing metadata.
    When existing_metadata_json is provided and enforce_transition is True,
    strictly validates the state transition against ALLOWED_TRANSITIONS.
    """
    if enforce_transition and existing_metadata_json is not None:
        current_meta = parse_message_metadata(existing_metadata_json)
        validate_message_state_transition(current_meta.status, status)

    data: Dict[str, Any] = {
        "version": version,
        "status": status.value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Merge existing metadata non-destructive
    if existing_metadata_json:
        try:
            existing = json.loads(existing_metadata_json)
            if isinstance(existing, dict):
                for k, v in existing.items():
                    if k not in data:
                        data[k] = v
        except Exception as exc:
            logger.warning("Failed parsing existing metadata_json during merge: %s", exc)

    if input_tokens is not None:
        data["input_tokens"] = input_tokens
    if output_tokens is not None:
        data["output_tokens"] = output_tokens
    if model_name is not None:
        data["model_name"] = model_name
    if latency_ms is not None:
        data["latency_ms"] = round(latency_ms, 2)
    if error_message is not None:
        data["error_message"] = str(error_message)[:1000]

    if extra:
        for k, v in extra.items():
            if k not in ("version", "status", "updated_at"):
                data[k] = v

    return json.dumps(data, ensure_ascii=False)


def apply_message_state_transition(
    existing_metadata_json: Optional[str],
    target_status: MessageStatus,
    version: int = 1,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    model_name: Optional[str] = None,
    latency_ms: Optional[float] = None,
    error_message: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Explicitly parse current status, enforce ALLOWED_TRANSITIONS, and build updated metadata JSON.
    Raises InvalidMessageStateTransitionError if the transition is disallowed.
    """
    current_meta = parse_message_metadata(existing_metadata_json)
    validate_message_state_transition(current_meta.status, target_status)
    return build_message_metadata_json(
        status=target_status,
        version=version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_name=model_name,
        latency_ms=latency_ms,
        error_message=error_message,
        existing_metadata_json=existing_metadata_json,
        extra=extra,
        enforce_transition=False,  # Already validated directly above
    )


def parse_message_metadata(metadata_json: Optional[str]) -> TutorMessageMetadata:
    """
    Safely deserialize metadata_json into a strongly-typed TutorMessageMetadata instance.
    Defaults to COMPLETED if metadata is missing or unparseable.
    """
    if not metadata_json:
        return TutorMessageMetadata(status=MessageStatus.COMPLETED)

    try:
        raw = json.loads(metadata_json)
        if not isinstance(raw, dict):
            return TutorMessageMetadata(status=MessageStatus.COMPLETED)

        raw_status = raw.get("status")
        try:
            status = MessageStatus(raw_status) if raw_status else MessageStatus.COMPLETED
        except ValueError:
            status = MessageStatus.COMPLETED

        return TutorMessageMetadata(
            status=status,
            input_tokens=raw.get("input_tokens"),
            output_tokens=raw.get("output_tokens"),
            model_name=raw.get("model_name"),
            latency_ms=raw.get("latency_ms"),
        )
    except Exception as exc:
        logger.warning("Failed parsing metadata_json (%s). Falling back to default metadata.", exc)
        return TutorMessageMetadata(status=MessageStatus.COMPLETED)
