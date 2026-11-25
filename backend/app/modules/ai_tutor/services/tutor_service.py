"""
Socratic Tutor Orchestration Service - SMART LEARNING PRO
Orchestrates Socratic conversational tutoring turns with streaming, distributed locking,
strict state machine enforcement, CAS persistence, stale worker protection,
cancellation recovery, lock-aware batched crash recovery, and usage accounting.
"""

import asyncio
from dataclasses import dataclass
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import AsyncIterator, Dict, Any, List, Optional, Tuple

from sqlalchemy import select, and_, or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.modules.ai_engine.contracts import (
    ChatMessage,
    NormalizedChatRequest,
    NormalizedStreamChunk,
    NormalizedStreamUsage,
)
from app.modules.ai_engine.exceptions import AITimeoutError
from app.modules.ai_engine.factory import get_llm_provider
from app.modules.ai_engine.providers.base import BaseLLMProvider
from app.modules.ai_engine.usage import calculate_estimated_cost
from app.modules.ai_tutor.exceptions import (
    ConversationBusyException,
    InvalidMessageStateTransitionError,
    StaleWorkerException,
    TutorProviderUnavailableException,
    TutorTimeoutException,
)
from app.modules.ai_tutor.models import AIConversation, AIMessage, AIUsageLog
from app.modules.ai_tutor.prompts import get_socratic_prompt
from app.modules.ai_tutor.schemas import (
    MessageStatus,
    TutorMessageRequest,
)
from app.modules.ai_tutor.services.conversation_lock import (
    ConversationLockManager,
    conversation_lock_manager,
    DEFAULT_LOCK_TTL_SECONDS,
)
from app.modules.ai_tutor.services.conversation_service import (
    ConversationService,
    conversation_service,
)
from app.modules.ai_tutor.services.message_state import (
    apply_message_state_transition,
    build_message_metadata_json,
    parse_message_metadata,
)
from app.modules.auth.models import User

logger = logging.getLogger(__name__)

MAX_RECOVERY_BATCH_SIZE: int = 100


@dataclass
class RecoveryBatchResult:
    """Result of a single keyset-paginated stale message recovery batch."""

    scanned_count: int
    recovered_count: int
    skipped_locked_count: int
    last_created_at: Optional[datetime]
    last_id: Optional[str]
    has_more: bool


class SocraticTutorService:
    """Orchestrates interactive Socratic tutoring sessions with real-time streaming."""

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        lock_manager: Optional[ConversationLockManager] = None,
        conv_service: Optional[ConversationService] = None,
    ):
        self._provider = provider or get_llm_provider()
        self._lock_manager = lock_manager or conversation_lock_manager
        self._conv_service = conv_service or conversation_service

    async def send_message_stream(
        self,
        db: AsyncSession,
        conversation_id: str,
        user: User,
        request: TutorMessageRequest,
        context_limit: int = 10,
    ) -> AsyncIterator[NormalizedStreamChunk]:
        """
        Execute an end-to-end Socratic tutoring turn:
        1. Authorize user ownership.
        2. Acquire distributed conversation lock.
        3. Persist user message and assistant placeholder (PENDING), then transition PENDING -> STREAMING.
        4. Build Socratic prompt and conversation context window.
        5. Stream LLM tokens to caller.
        6. On finish: verify lock ownership & atomically transition STREAMING -> COMPLETED.
        7. On cancellation: verify lock ownership & transition to INTERRUPTED.
        8. On failure: verify lock ownership & transition to FAILED.
        """
        # 1. Authorize ownership before doing any work
        conversation = await self._conv_service.verify_conversation_ownership(
            db=db,
            conversation_id=conversation_id,
            user_id=user.id,
        )

        # 2. Acquire exclusive conversation lock to prevent concurrent turn collisions
        lock_token = str(uuid.uuid4())
        acquired = await self._lock_manager.acquire_lock(
            conversation_id=conversation_id,
            lock_token=lock_token,
            ttl_seconds=DEFAULT_LOCK_TTL_SECONDS,
        )
        if not acquired:
            logger.warning(
                "Conversation %s is busy. Rejected concurrent request from user %s",
                conversation_id,
                user.id,
            )
            raise ConversationBusyException()

        # Start heartbeat renewal to keep lock alive while streaming
        heartbeat_task = self._lock_manager.spawn_heartbeat_worker(
            conversation_id=conversation_id,
            lock_token=lock_token,
            ttl_seconds=DEFAULT_LOCK_TTL_SECONDS,
            interval_seconds=max(5.0, DEFAULT_LOCK_TTL_SECONDS / 3.0),
        )

        user_msg_id = str(uuid.uuid4())
        assistant_msg_id = str(uuid.uuid4())
        accumulated_text: List[str] = []
        last_usage: Optional[NormalizedStreamUsage] = None
        finish_reason: Optional[str] = None
        t_start = time.perf_counter()

        try:
            # 3. Persist User Message & Assistant Placeholder (PENDING)
            user_message = AIMessage(
                id=user_msg_id,
                conversation_id=conversation_id,
                role="user",
                content=request.content.strip(),
                metadata_json=build_message_metadata_json(status=MessageStatus.COMPLETED),
                created_at=datetime.now(timezone.utc),
            )
            db.add(user_message)

            assistant_message = AIMessage(
                id=assistant_msg_id,
                conversation_id=conversation_id,
                role="assistant",
                content="",
                metadata_json=build_message_metadata_json(
                    status=MessageStatus.PENDING,
                    model_name=self._provider.default_model,
                ),
                created_at=datetime.now(timezone.utc),
            )
            db.add(assistant_message)
            await db.commit()

            # Verify lock ownership and transition PENDING -> STREAMING
            if not await self._lock_manager.is_lock_owned(conversation_id, lock_token):
                raise StaleWorkerException()

            started = await self._atomic_transition_message(
                db=db,
                message_id=assistant_msg_id,
                target_status=MessageStatus.STREAMING,
                model_name=self._provider.default_model,
            )
            if not started:
                raise StaleWorkerException("Could not transition assistant message from PENDING to STREAMING.")

            # 4. Build Socratic Prompt & Context Window
            safe_context_limit = max(2, min(50, context_limit))
            hist_stmt = (
                select(AIMessage)
                .where(
                    and_(
                        AIMessage.conversation_id == conversation_id,
                        AIMessage.id != user_msg_id,
                        AIMessage.id != assistant_msg_id,
                    )
                )
                .order_by(AIMessage.created_at.desc())
                .limit(safe_context_limit)
            )
            hist_rows = (await db.execute(hist_stmt)).scalars().all()
            chronological_history = list(reversed(hist_rows))

            topic_name = conversation.topic.title if (hasattr(conversation, "topic") and conversation.topic) else None
            grade_str = str(user.grade_level) if getattr(user, "grade_level", None) else None
            system_instruction = get_socratic_prompt(topic=topic_name, grade_level=grade_str)

            chat_messages: List[ChatMessage] = []
            for m in chronological_history:
                meta = parse_message_metadata(m.metadata_json)
                if meta.status == MessageStatus.FAILED or (meta.status == MessageStatus.INTERRUPTED and not m.content):
                    continue
                if m.role in ("user", "assistant"):
                    chat_messages.append(ChatMessage(role=m.role, content=m.content))

            chat_messages.append(ChatMessage(role="user", content=user_message.content))

            # 5. Stream tokens from Provider (no DB transaction held open)
            normalized_req = NormalizedChatRequest(
                messages=chat_messages,
                system_instruction=system_instruction,
                model=self._provider.default_model,
            )

            async for chunk in self._provider.generate_stream(normalized_req):
                if chunk.delta:
                    accumulated_text.append(chunk.delta)
                if chunk.usage:
                    last_usage = chunk.usage
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
                yield chunk

            # 6. Finalization on successful stream completion
            t_end = time.perf_counter()
            latency_ms = round((t_end - t_start) * 1000.0, 2)
            final_content = "".join(accumulated_text)

            # Stale worker protection: verify caller still owns lock token BEFORE any state mutation
            is_owned = await self._lock_manager.is_lock_owned(conversation_id, lock_token)
            if not is_owned:
                logger.error(
                    "Stale worker detected for conversation %s: lock lost during streaming. Aborting final write.",
                    conversation_id,
                )
                # Preserve actual incurred provider telemetry in isolated session without mutating conversation state
                await self._record_usage_telemetry_isolated(
                    user_id=user.id,
                    model_name=self._provider.default_model,
                    usage=last_usage,
                )
                raise StaleWorkerException()

            # Atomic CAS transition STREAMING -> COMPLETED (enforces state machine + prevents race)
            transitioned = await self._atomic_transition_message(
                db=db,
                message_id=assistant_msg_id,
                target_status=MessageStatus.COMPLETED,
                content=final_content,
                input_tokens=last_usage.input_tokens if last_usage else None,
                output_tokens=last_usage.output_tokens if last_usage else None,
                model_name=self._provider.default_model,
                latency_ms=latency_ms,
                extra={"finish_reason": finish_reason or "STOP"},
            )
            if not transitioned:
                logger.error(
                    "CAS conflict detected finalizing message %s for conversation %s. Aborting conversation update.",
                    assistant_msg_id,
                    conversation_id,
                )
                await self._record_usage_telemetry_isolated(
                    user_id=user.id,
                    model_name=self._provider.default_model,
                    usage=last_usage,
                )
                raise StaleWorkerException("Message state changed concurrently before completion commit.")

            # Update conversation timestamp only when message CAS succeeded under valid lock
            conv_stmt = (
                update(AIConversation)
                .where(AIConversation.id == conversation_id)
                .values(updated_at=datetime.now(timezone.utc))
            )
            await db.execute(conv_stmt)
            await db.commit()
            db.expire_all()

            # Record usage telemetry (error-isolated)
            await self._record_usage_telemetry(
                db=db,
                user_id=user.id,
                model_name=self._provider.default_model,
                usage=last_usage,
            )

        except (asyncio.CancelledError, GeneratorExit):
            # 7. Cancellation Handling (Client disconnect / aclose / task cancelled)
            logger.info("Streaming interrupted by client for conversation %s", conversation_id)
            partial_content = "".join(accumulated_text)
            await self._update_message_on_failure(
                db=db,
                conversation_id=conversation_id,
                lock_token=lock_token,
                message_id=assistant_msg_id,
                status=MessageStatus.INTERRUPTED,
                content=partial_content,
                model_name=self._provider.default_model,
                error_message="Streaming cancelled by client or consumer.",
            )
            raise

        except (AITimeoutError, asyncio.TimeoutError) as exc:
            # 8. Timeout Handling
            logger.warning("Streaming timeout for conversation %s: %s", conversation_id, exc)
            await self._update_message_on_failure(
                db=db,
                conversation_id=conversation_id,
                lock_token=lock_token,
                message_id=assistant_msg_id,
                status=MessageStatus.FAILED,
                content="".join(accumulated_text),
                model_name=self._provider.default_model,
                error_message=f"Timeout: {exc}",
            )
            raise TutorTimeoutException() from exc

        except StaleWorkerException:
            raise

        except InvalidMessageStateTransitionError:
            raise

        except Exception as exc:
            # 9. General Provider / System Failure
            logger.error("Streaming failure for conversation %s: %s", conversation_id, exc)
            await self._update_message_on_failure(
                db=db,
                conversation_id=conversation_id,
                lock_token=lock_token,
                message_id=assistant_msg_id,
                status=MessageStatus.FAILED,
                content="".join(accumulated_text),
                model_name=self._provider.default_model,
                error_message=str(exc),
            )
            raise TutorProviderUnavailableException(f"Lỗi AI Tutor: {exc}") from exc

        finally:
            # 10. Teardown: Stop heartbeat & release lock atomically
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

            await self._lock_manager.release_lock(conversation_id, lock_token)

    async def _atomic_transition_message(
        self,
        db: AsyncSession,
        message_id: str,
        target_status: MessageStatus,
        content: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        model_name: Optional[str] = None,
        latency_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Read fresh authoritative state, enforce state transition rules via apply_message_state_transition,
        and persist using Compare-And-Swap (CAS) on metadata_json.

        Returns True if exactly 1 row transitioned and committed; False if row missing or concurrent conflict.
        Raises InvalidMessageStateTransitionError if current state cannot transition to target_status.
        """
        stmt = (
            select(AIMessage)
            .where(AIMessage.id == message_id)
            .execution_options(populate_existing=True)
        )
        # Use row lock when supported by backend (PostgreSQL)
        try:
            bind = db.get_bind()
            if bind is not None and bind.dialect.name == "postgresql":
                stmt = stmt.with_for_update()
        except Exception:
            pass

        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            return False

        expected_old_meta = row.metadata_json

        # Enforce state machine strictly against authoritative DB status
        new_meta_json = apply_message_state_transition(
            existing_metadata_json=expected_old_meta,
            target_status=target_status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=model_name,
            latency_ms=latency_ms,
            error_message=error_message,
            extra=extra,
        )

        update_values: Dict[str, Any] = {"metadata_json": new_meta_json}
        if content is not None:
            update_values["content"] = content

        if expected_old_meta is None:
            cond = and_(AIMessage.id == message_id, AIMessage.metadata_json.is_(None))
        else:
            cond = and_(AIMessage.id == message_id, AIMessage.metadata_json == expected_old_meta)

        cas_stmt = update(AIMessage).where(cond).values(**update_values)
        res = await db.execute(cas_stmt)
        if res.rowcount != 1:
            await db.rollback()
            return False

        await db.commit()
        db.expire(row)
        return True

    async def _update_message_on_failure(
        self,
        db: AsyncSession,
        conversation_id: str,
        lock_token: str,
        message_id: str,
        status: MessageStatus,
        content: str,
        model_name: str,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Verify lock ownership before updating message status on failure or cancellation.
        A stale worker that has lost its lock MUST NOT mark FAILED/INTERRUPTED or write partial content.
        """
        is_owned = await self._lock_manager.is_lock_owned(conversation_id, lock_token)
        if not is_owned:
            logger.warning(
                "Stale worker detected during %s update for conversation %s (message %s). "
                "Refusing to write status or partial content.",
                status.value,
                conversation_id,
                message_id,
            )
            return

        try:
            updated = await self._atomic_transition_message(
                db=db,
                message_id=message_id,
                target_status=status,
                content=content,
                model_name=model_name,
                error_message=error_message,
            )
            if not updated:
                logger.warning("CAS update skipped for message %s (missing or concurrent state change).", message_id)
        except InvalidMessageStateTransitionError as exc:
            logger.warning("Blocked invalid transition in failure handler for %s: %s", message_id, exc)
        except Exception as exc:
            logger.warning("Failed to update message in current session (%s). Retrying in isolated session.", exc)
            try:
                await db.rollback()
            except Exception:
                pass
            # Re-verify lock ownership before isolated retry
            if await self._lock_manager.is_lock_owned(conversation_id, lock_token):
                await self._safe_update_message_status(
                    message_id=message_id,
                    status=status,
                    content=content,
                    model_name=model_name,
                    error_message=error_message,
                )

    async def _safe_update_message_status(
        self,
        message_id: str,
        status: MessageStatus,
        content: str,
        model_name: str,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Safely update message status and content in an isolated transaction using atomic CAS
        and state transition enforcement.
        """
        try:
            async with AsyncSessionLocal() as session:
                await self._atomic_transition_message(
                    db=session,
                    message_id=message_id,
                    target_status=status,
                    content=content,
                    model_name=model_name,
                    error_message=error_message,
                )
        except InvalidMessageStateTransitionError as exc:
            logger.warning("Blocked invalid transition in isolated update for %s: %s", message_id, exc)
        except Exception as exc:
            logger.error("Failed to safely update message status for %s: %s", message_id, exc)

    async def _record_usage_telemetry(
        self,
        db: AsyncSession,
        user_id: str,
        model_name: str,
        usage: Optional[NormalizedStreamUsage],
    ) -> None:
        """
        Persist verified provider-reported token consumption and estimated USD cost to ai_usage_logs.
        Error-isolated: database write failure never raises to caller.
        """
        if not usage or usage.input_tokens is None or usage.output_tokens is None:
            return

        try:
            in_tok = usage.input_tokens
            out_tok = usage.output_tokens
            cached_tok = usage.cached_tokens

            cost = calculate_estimated_cost(
                model_name=model_name,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cached_tokens=cached_tok,
            )
            estimated_usd = cost if cost is not None else 0.0

            log_entry = AIUsageLog(
                id=str(uuid.uuid4()),
                user_id=user_id,
                feature="TUTOR_CHAT",
                model_name=model_name,
                prompt_tokens=in_tok,
                completion_tokens=out_tok,
                estimated_cost_usd=estimated_usd,
                created_at=datetime.now(timezone.utc),
            )
            db.add(log_entry)
            await db.commit()
        except Exception as exc:
            logger.warning("Failed to record usage log for user %s: %s", user_id, exc)
            try:
                await db.rollback()
            except Exception:
                pass

    async def _record_usage_telemetry_isolated(
        self,
        user_id: str,
        model_name: str,
        usage: Optional[NormalizedStreamUsage],
    ) -> None:
        """
        Record actual incurred provider-reported usage in a completely isolated transaction,
        separate from conversation/message state persistence.
        """
        if not usage or usage.input_tokens is None or usage.output_tokens is None:
            return
        try:
            async with AsyncSessionLocal() as session:
                await self._record_usage_telemetry(
                    db=session,
                    user_id=user_id,
                    model_name=model_name,
                    usage=usage,
                )
        except Exception as exc:
            logger.warning("Isolated usage telemetry recording failed for user %s: %s", user_id, exc)

    async def recover_stale_streaming_messages_batch(
        self,
        db: AsyncSession,
        max_stale_seconds: int = 300,
        batch_size: int = MAX_RECOVERY_BATCH_SIZE,
        after_created_at: Optional[datetime] = None,
        after_id: Optional[str] = None,
    ) -> RecoveryBatchResult:
        """
        Lock-aware, race-free, batched stale message recovery with keyset pagination.

        Design guarantees (SEC-732-L1 & SEC-732-L2):
        - Scans at most `min(100, batch_size)` candidate rows per batch using deterministic keyset ordering.
        - Filters terminal records out at SQL level where possible, and skips terminal states in Python.
        - Checks whether the conversation currently holds an active lock (`is_locked`).
        - Acquires a short-lived exclusive recovery lock on `conversation_id` BEFORE transitioning.
        - Re-reads authoritative DB row and transitions using atomic CAS `UPDATE` (`metadata_json == old_meta`),
          guaranteeing zero conflict with concurrent recovery workers or new turn workers.
        - Only counts a message as recovered when the DB CAS transaction succeeds.
        """
        safe_batch_size = max(1, min(MAX_RECOVERY_BATCH_SIZE, batch_size))
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_stale_seconds)

        filters = [
            AIMessage.role == "assistant",
            AIMessage.created_at < cutoff,
            or_(
                AIMessage.metadata_json.contains('"status": "STREAMING"'),
                AIMessage.metadata_json.contains('"status":"STREAMING"'),
                AIMessage.metadata_json.contains('"status": "PENDING"'),
                AIMessage.metadata_json.contains('"status":"PENDING"'),
            ),
        ]

        if after_created_at is not None and after_id is not None:
            filters.append(
                or_(
                    AIMessage.created_at > after_created_at,
                    and_(AIMessage.created_at == after_created_at, AIMessage.id > after_id),
                )
            )

        stmt = (
            select(
                AIMessage.id,
                AIMessage.conversation_id,
                AIMessage.metadata_json,
                AIMessage.created_at,
            )
            .where(and_(*filters))
            .order_by(AIMessage.created_at.asc(), AIMessage.id.asc())
            .limit(safe_batch_size)
        )

        candidates = (await db.execute(stmt)).all()
        scanned_count = len(candidates)
        recovered_count = 0
        skipped_locked_count = 0
        last_created_at: Optional[datetime] = None
        last_id: Optional[str] = None

        for msg_id, conv_id, msg_meta_json, raw_created_at in candidates:
            last_created_at = raw_created_at
            last_id = msg_id

            # Timezone-safe cutoff check
            msg_created = raw_created_at
            if msg_created.tzinfo is None:
                msg_created = msg_created.replace(tzinfo=timezone.utc)
            if msg_created >= cutoff:
                continue

            # Never touch terminal states
            meta = parse_message_metadata(msg_meta_json)
            if meta.status not in (MessageStatus.STREAMING, MessageStatus.PENDING):
                continue

            # Check whether conversation currently holds an active worker lock (Scenario A & C)
            if await self._lock_manager.is_locked(conv_id):
                skipped_locked_count += 1
                continue

            # Acquire exclusive short-lived recovery lock to prevent race with new workers / other reapers
            recovery_token = f"recovery-{uuid.uuid4()}"
            acquired = await self._lock_manager.acquire_lock(
                conversation_id=conv_id,
                lock_token=recovery_token,
                ttl_seconds=15,
            )
            if not acquired:
                skipped_locked_count += 1
                continue

            try:
                # Re-verify lock ownership
                if not await self._lock_manager.is_lock_owned(conv_id, recovery_token):
                    skipped_locked_count += 1
                    continue

                # Execute atomic CAS transition so each message update is strictly serialized
                try:
                    transitioned = await self._atomic_transition_message(
                        db=db,
                        message_id=msg_id,
                        target_status=MessageStatus.INTERRUPTED,
                        model_name=meta.model_name,
                        error_message="Recovered from stale orphaned state.",
                        extra={"recovered_stale": True},
                    )
                    if transitioned:
                        recovered_count += 1
                except InvalidMessageStateTransitionError:
                    # Message transitioned to terminal state concurrently -> safe to ignore
                    pass
                except Exception as exc:
                    logger.warning("Failed recovering stale message %s: %s", msg_id, exc)
                    try:
                        await db.rollback()
                    except Exception:
                        pass
            finally:
                await self._lock_manager.release_lock(conv_id, recovery_token)

        if recovered_count > 0:
            logger.info("Recovered %d stale streaming messages (scanned=%d, skipped_locked=%d).",
                        recovered_count, scanned_count, skipped_locked_count)

        has_more = (scanned_count == safe_batch_size)
        return RecoveryBatchResult(
            scanned_count=scanned_count,
            recovered_count=recovered_count,
            skipped_locked_count=skipped_locked_count,
            last_created_at=last_created_at,
            last_id=last_id,
            has_more=has_more,
        )

    async def recover_stale_streaming_messages(
        self,
        db: AsyncSession,
        max_stale_seconds: int = 300,
        batch_size: int = MAX_RECOVERY_BATCH_SIZE,
        drain_backlog: bool = False,
    ) -> int:
        """
        Backward-compatible wrapper for stale message recovery.
        When drain_backlog=False (default), executes a single bounded batch (max 100 candidates).
        When drain_backlog=True, iterates through batches via keyset pagination until backlog is drained.
        """
        total_recovered = 0
        after_created_at: Optional[datetime] = None
        after_id: Optional[str] = None

        while True:
            batch_res = await self.recover_stale_streaming_messages_batch(
                db=db,
                max_stale_seconds=max_stale_seconds,
                batch_size=batch_size,
                after_created_at=after_created_at,
                after_id=after_id,
            )
            total_recovered += batch_res.recovered_count

            if not drain_backlog or not batch_res.has_more:
                break

            if batch_res.last_created_at is None or batch_res.last_id is None:
                break
            after_created_at = batch_res.last_created_at
            after_id = batch_res.last_id

        return total_recovered


# Global singleton instance for application use
socratic_tutor_service = SocraticTutorService()
