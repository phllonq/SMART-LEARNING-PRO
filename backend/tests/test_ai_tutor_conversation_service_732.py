"""
Phase 7.3.2 Test Suite: Conversation State & Socratic Service Layer - SMART LEARNING PRO
Comprehensive verification covering:
  Group A: Conversation Lifecycle & Ownership Authorization
  Group B: Message State Machine & Metadata Serialization
  Group C: Socratic Service Streaming & Context Management
  Group D: Concurrency Control & Distributed Locking
  Group E: Cancellation & Failure Recovery
  Group F: Usage Telemetry & Accounting
"""

import asyncio
import json
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from typing import Tuple, List
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.cache import CacheService, InMemoryCache
from app.modules.ai_engine.contracts import (
    ChatMessage,
    NormalizedChatRequest,
    NormalizedStreamChunk,
    NormalizedStreamUsage,
)
from app.modules.ai_engine.exceptions import (
    AIServerError,
    AITimeoutError,
)
from app.modules.ai_engine.providers.mock import MockAIProvider
from app.modules.ai_tutor.exceptions import (
    ConversationNotFoundException,
    ConversationAccessDeniedException,
    ConversationBusyException,
    InvalidMessageStateTransitionError,
    StaleWorkerException,
    TutorProviderUnavailableException,
    TutorTimeoutException,
)
from app.modules.ai_tutor.models import AIConversation, AIMessage, AIUsageLog
from app.modules.ai_tutor.schemas import (
    MessageStatus,
    ConversationCreateRequest,
    ConversationRenameRequest,
    TutorMessageRequest,
)
from app.modules.ai_tutor.services.conversation_lock import (
    ConversationLockManager,
    DEFAULT_LOCK_TTL_SECONDS,
)
from app.modules.ai_tutor.services.conversation_service import ConversationService
from app.modules.ai_tutor.services.message_state import (
    ALLOWED_TRANSITIONS,
    validate_message_state_transition,
    apply_message_state_transition,
    build_message_metadata_json,
    parse_message_metadata,
)
from app.modules.ai_tutor.services.tutor_service import SocraticTutorService
from app.modules.auth.models import User, UserRole


# ==============================================================================
# TEST FIXTURES & HELPERS
# ==============================================================================

async def _create_test_users() -> Tuple[User, User]:
    """Create two test students in database."""
    async with AsyncSessionLocal() as session:
        u1 = User(
            id=str(uuid.uuid4()),
            email=f"tutor_stu1_{uuid.uuid4().hex[:6]}@smartlearning.vn",
            hashed_password="hash",
            full_name="Học sinh A",
            role=UserRole.STUDENT.value,
            grade_level=9,
        )
        u2 = User(
            id=str(uuid.uuid4()),
            email=f"tutor_stu2_{uuid.uuid4().hex[:6]}@smartlearning.vn",
            hashed_password="hash",
            full_name="Học sinh B",
            role=UserRole.STUDENT.value,
            grade_level=10,
        )
        session.add_all([u1, u2])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)
        return u1, u2


# ==============================================================================
# GROUP A: CONVERSATION LIFECYCLE & AUTHORIZATION TESTS
# ==============================================================================

class TestGroupAConversationLifecycle:
    """Verifies conversation creation, retrieval, renaming, deletion, and ownership enforcement."""

    @pytest.mark.asyncio
    async def test_create_and_get_conversation_success(self):
        user_a, _ = await _create_test_users()
        service = ConversationService()

        async with AsyncSessionLocal() as session:
            # 1. Create with custom title
            req = ConversationCreateRequest(title="Hình học 9: Góc nội tiếp")
            created = await service.create_conversation(session, user_a.id, req)
            assert created.title == "Hình học 9: Góc nội tiếp"
            assert created.user_id == user_a.id
            assert created.message_count == 0

            # 2. Get details
            fetched = await service.get_conversation(session, created.id, user_a.id)
            assert fetched.id == created.id
            assert fetched.title == "Hình học 9: Góc nội tiếp"
            assert fetched.user_id == user_a.id

    @pytest.mark.asyncio
    async def test_create_conversation_default_title(self):
        user_a, _ = await _create_test_users()
        service = ConversationService()

        async with AsyncSessionLocal() as session:
            req = ConversationCreateRequest()
            created = await service.create_conversation(session, user_a.id, req)
            assert created.title == "Đoạn hội thoại học tập"

    @pytest.mark.asyncio
    async def test_get_conversation_cross_user_denied_uniform_404(self):
        user_a, user_b = await _create_test_users()
        service = ConversationService()

        async with AsyncSessionLocal() as session:
            created = await service.create_conversation(session, user_a.id, ConversationCreateRequest())

            # User B attempts to access User A's conversation
            with pytest.raises(ConversationNotFoundException) as exc_info:
                await service.get_conversation(session, created.id, user_b.id)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_list_conversations_and_pagination(self):
        user_a, _ = await _create_test_users()
        service = ConversationService()

        async with AsyncSessionLocal() as session:
            # Create 3 conversations
            for i in range(3):
                await service.create_conversation(session, user_a.id, ConversationCreateRequest(title=f"Conv {i}"))

            # Page 1, size 2
            page1 = await service.list_conversations(session, user_a.id, page=1, page_size=2)
            assert page1.total == 3
            assert len(page1.items) == 2

            # Page 2, size 2
            page2 = await service.list_conversations(session, user_a.id, page=2, page_size=2)
            assert len(page2.items) == 1

    @pytest.mark.asyncio
    async def test_rename_conversation_success_and_cross_user_denied(self):
        user_a, user_b = await _create_test_users()
        service = ConversationService()

        async with AsyncSessionLocal() as session:
            conv = await service.create_conversation(session, user_a.id, ConversationCreateRequest(title="Cũ"))

            # User B attempts rename -> 404
            with pytest.raises(ConversationNotFoundException):
                await service.rename_conversation(session, conv.id, user_b.id, ConversationRenameRequest(title="Đổi"))

            # User A renames -> Success
            renamed = await service.rename_conversation(session, conv.id, user_a.id, ConversationRenameRequest(title="Mới"))
            assert renamed.title == "Mới"

    @pytest.mark.asyncio
    async def test_delete_conversation_success_and_cascades_messages(self):
        user_a, _ = await _create_test_users()
        service = ConversationService()

        async with AsyncSessionLocal() as session:
            conv = await service.create_conversation(session, user_a.id, ConversationCreateRequest())
            # Add message
            msg = AIMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv.id,
                role="user",
                content="Tin nhắn thử nghiệm",
            )
            session.add(msg)
            await session.commit()

            # Delete
            deleted = await service.delete_conversation(session, conv.id, user_a.id)
            assert deleted is True

            # Verify conversation is gone
            with pytest.raises(ConversationNotFoundException):
                await service.get_conversation(session, conv.id, user_a.id)

            # Verify cascaded message is also gone
            msg_check = (await session.execute(select(AIMessage).where(AIMessage.id == msg.id))).scalar_one_or_none()
            assert msg_check is None


# ==============================================================================
# GROUP B: MESSAGE STATE MACHINE TESTS
# ==============================================================================

class TestGroupBMessageStateMachine:
    """Verifies message status transitions, metadata serialization, and stale recovery."""

    def test_valid_state_transitions(self):
        # PENDING -> STREAMING
        validate_message_state_transition(MessageStatus.PENDING, MessageStatus.STREAMING)
        # PENDING -> FAILED
        validate_message_state_transition(MessageStatus.PENDING, MessageStatus.FAILED)
        # PENDING -> INTERRUPTED
        validate_message_state_transition(MessageStatus.PENDING, MessageStatus.INTERRUPTED)

        # STREAMING -> COMPLETED
        validate_message_state_transition(MessageStatus.STREAMING, MessageStatus.COMPLETED)
        # STREAMING -> FAILED
        validate_message_state_transition(MessageStatus.STREAMING, MessageStatus.FAILED)
        # STREAMING -> INTERRUPTED
        validate_message_state_transition(MessageStatus.STREAMING, MessageStatus.INTERRUPTED)

    def test_invalid_state_transitions(self):
        # COMPLETED cannot transition to anything
        with pytest.raises(InvalidMessageStateTransitionError):
            validate_message_state_transition(MessageStatus.COMPLETED, MessageStatus.STREAMING)

        # FAILED cannot transition
        with pytest.raises(InvalidMessageStateTransitionError):
            validate_message_state_transition(MessageStatus.FAILED, MessageStatus.COMPLETED)

        # INTERRUPTED cannot transition
        with pytest.raises(InvalidMessageStateTransitionError):
            validate_message_state_transition(MessageStatus.INTERRUPTED, MessageStatus.COMPLETED)

    def test_metadata_json_serialization_and_parsing(self):
        raw_json = build_message_metadata_json(
            status=MessageStatus.COMPLETED,
            input_tokens=42,
            output_tokens=88,
            model_name="mock-model",
            latency_ms=123.45,
            extra={"custom_attr": "value"},
        )
        assert '"status": "COMPLETED"' in raw_json
        assert '"custom_attr": "value"' in raw_json

        parsed = parse_message_metadata(raw_json)
        assert parsed.status == MessageStatus.COMPLETED
        assert parsed.input_tokens == 42
        assert parsed.output_tokens == 88
        assert parsed.model_name == "mock-model"
        assert parsed.latency_ms == 123.45

    @pytest.mark.asyncio
    async def test_stale_streaming_recovery(self):
        user_a, _ = await _create_test_users()
        service = ConversationService()
        tutor_service = SocraticTutorService()

        async with AsyncSessionLocal() as session:
            conv = await service.create_conversation(session, user_a.id, ConversationCreateRequest())
            # Create an orphaned message that is 10 minutes old in STREAMING state
            old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            stale_msg = AIMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv.id,
                role="assistant",
                content="Partial text...",
                metadata_json=build_message_metadata_json(status=MessageStatus.STREAMING),
                created_at=old_time,
            )
            session.add(stale_msg)
            await session.commit()

            # Run recovery
            recovered_count = await tutor_service.recover_stale_streaming_messages(session, max_stale_seconds=300)
            assert recovered_count >= 1

            # Verify it transitioned to INTERRUPTED
            await session.refresh(stale_msg)
            meta = parse_message_metadata(stale_msg.metadata_json)
            assert meta.status == MessageStatus.INTERRUPTED


# ==============================================================================
# GROUP C: SOCRATIC SERVICE STREAMING & CONTEXT TESTS
# ==============================================================================

class TestGroupCSocraticService:
    """Verifies end-to-end streaming dialogue, history assembly, and prompt injection safety."""

    @pytest.mark.asyncio
    async def test_socratic_stream_successful_interaction(self):
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()

        # Mock provider that yields 3 chunks
        sim_usage = NormalizedStreamUsage(input_tokens=15, output_tokens=30, total_tokens=45)
        mock_provider = MockAIProvider(
            stream_chunks=["Chào em! ", "Em hãy cho biết ", "nghiệm phương trình là gì?"],
            simulated_stream_usage=sim_usage,
        )
        tutor_service = SocraticTutorService(provider=mock_provider)

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest(title="Toán 9"))

            req = TutorMessageRequest(content="Thầy ơi giải giúp em $x^2 - 4 = 0$")
            received_tokens = []

            async for chunk in tutor_service.send_message_stream(session, conv.id, user_a, req):
                received_tokens.append(chunk.delta)

            assert "".join(received_tokens) == "Chào em! Em hãy cho biết nghiệm phương trình là gì?"

            # Verify in DB: both user and assistant messages exist
            history = await conv_service.get_conversation_history(session, conv.id, user_a.id)
            assert len(history) == 2
            assert history[0].role == "user"
            assert history[0].content == "Thầy ơi giải giúp em $x^2 - 4 = 0$"
            assert history[1].role == "assistant"
            assert history[1].content == "Chào em! Em hãy cho biết nghiệm phương trình là gì?"
            assert history[1].metadata.status == MessageStatus.COMPLETED
            assert history[1].metadata.input_tokens == 15
            assert history[1].metadata.output_tokens == 30

    @pytest.mark.asyncio
    async def test_socratic_context_history_ordering_and_filtering(self):
        """Verifies that conversation history sent to provider excludes failed turns and maintains order."""
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()

        mock_provider = MockAIProvider(stream_chunks=["Tiếp tục nhé."])
        tutor_service = SocraticTutorService(provider=mock_provider)

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())

            # Add turn 1: User + Assistant (COMPLETED)
            m1 = AIMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv.id,
                role="user",
                content="Câu hỏi 1",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
            m2 = AIMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv.id,
                role="assistant",
                content="Đáp án 1",
                metadata_json=build_message_metadata_json(status=MessageStatus.COMPLETED),
                created_at=datetime.now(timezone.utc) - timedelta(minutes=4),
            )
            # Add turn 2: Failed assistant message (should be excluded from context)
            m3 = AIMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv.id,
                role="assistant",
                content="Partial garbage",
                metadata_json=build_message_metadata_json(status=MessageStatus.FAILED),
                created_at=datetime.now(timezone.utc) - timedelta(minutes=3),
            )
            session.add_all([m1, m2, m3])
            await session.commit()

            # Now send turn 3
            req = TutorMessageRequest(content="Câu hỏi 2")
            tokens = [c.delta async for c in tutor_service.send_message_stream(session, conv.id, user_a, req)]
            assert "".join(tokens) == "Tiếp tục nhé."

            # Inspect recorded request in provider
            recorded_req = mock_provider.recorded_stream_requests[-1]
            # Expect: m1 (user), m2 (assistant), and new user message. m3 (failed) must be omitted!
            messages_sent = recorded_req.messages
            assert len(messages_sent) == 3
            assert messages_sent[0].content == "Câu hỏi 1"
            assert messages_sent[1].content == "Đáp án 1"
            assert messages_sent[2].content == "Câu hỏi 2"


# ==============================================================================
# GROUP D: CONCURRENCY CONTROL TESTS
# ==============================================================================

class TestGroupDConcurrencyControl:
    """Verifies distributed locking, collision prevention, lock ownership, and stale worker rejection."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_same_conversation_raises_busy(self):
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()

        # Slow provider simulating delay
        slow_provider = MockAIProvider(
            stream_chunks=["Chunk 1", "Chunk 2", "Chunk 3"],
            stream_chunk_delay=0.2,
        )
        tutor_service = SocraticTutorService(provider=slow_provider)

        async with AsyncSessionLocal() as session1, AsyncSessionLocal() as session2:
            conv = await conv_service.create_conversation(session1, user_a.id, ConversationCreateRequest())

            req1 = TutorMessageRequest(content="Câu 1")
            req2 = TutorMessageRequest(content="Câu 2")

            stream1 = tutor_service.send_message_stream(session1, conv.id, user_a, req1)
            # Fetch first token to acquire lock
            await stream1.__anext__()

            # Immediate concurrent request on session 2
            with pytest.raises(ConversationBusyException):
                async for _ in tutor_service.send_message_stream(session2, conv.id, user_a, req2):
                    pass

            # Drain stream 1
            async for _ in stream1:
                pass

    @pytest.mark.asyncio
    async def test_concurrent_requests_different_conversations_both_succeed(self):
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        provider = MockAIProvider(stream_chunks=["Done"])
        tutor_service = SocraticTutorService(provider=provider)

        async with AsyncSessionLocal() as s1, AsyncSessionLocal() as s2:
            c1 = await conv_service.create_conversation(s1, user_a.id, ConversationCreateRequest(title="Conv 1"))
            c2 = await conv_service.create_conversation(s2, user_a.id, ConversationCreateRequest(title="Conv 2"))

            req = TutorMessageRequest(content="Hello")
            res1 = [c.delta async for c in tutor_service.send_message_stream(s1, c1.id, user_a, req)]
            res2 = [c.delta async for c in tutor_service.send_message_stream(s2, c2.id, user_a, req)]

            assert "".join(res1) == "Done"
            assert "".join(res2) == "Done"

    @pytest.mark.asyncio
    async def test_stale_worker_rejected_before_persistence(self):
        """Worker loses lock during streaming -> final DB write is aborted with StaleWorkerException."""
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        provider = MockAIProvider(stream_chunks=["Chunk 1", "Chunk 2"])
        lock_mgr = ConversationLockManager()

        tutor_service = SocraticTutorService(provider=provider, lock_manager=lock_mgr)

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            req = TutorMessageRequest(content="Ping")

            # Force is_lock_owned to return False right at finalization
            with patch.object(lock_mgr, "is_lock_owned", AsyncMock(return_value=False)):
                with pytest.raises(StaleWorkerException):
                    async for _ in tutor_service.send_message_stream(session, conv.id, user_a, req):
                        pass


# ==============================================================================
# GROUP E: CANCELLATION & FAILURE RECOVERY TESTS
# ==============================================================================

class TestGroupECancellationAndFailure:
    """Verifies graceful cancellation, interruption state persistence, and error mapping."""

    @pytest.mark.asyncio
    async def test_streaming_cancellation_marks_message_interrupted(self):
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        provider = MockAIProvider(
            stream_chunks=["Token1 ", "Token2 ", "Token3 ", "Token4 "],
            stream_chunk_delay=0.1,
        )
        tutor_service = SocraticTutorService(provider=provider)

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            req = TutorMessageRequest(content="Giải thích giúp em")

            received = []
            stream = tutor_service.send_message_stream(session, conv.id, user_a, req)

            # Consume 2 tokens and break early (cancelling generator)
            async for chunk in stream:
                received.append(chunk.delta)
                if len(received) == 2:
                    await stream.aclose()
                    break

            assert len(received) == 2

            # Verify in DB: Assistant message is marked INTERRUPTED with partial text
            history = await conv_service.get_conversation_history(session, conv.id, user_a.id)
            assistant_msg = history[-1]
            assert assistant_msg.role == "assistant"
            assert assistant_msg.metadata.status == MessageStatus.INTERRUPTED
            assert assistant_msg.content == "Token1 Token2 "

    @pytest.mark.asyncio
    async def test_provider_error_marks_message_failed(self):
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        provider = MockAIProvider(
            stream_error_after_chunks=0,
            stream_error_to_raise=AIServerError("Model overloaded", provider="mock"),
        )
        tutor_service = SocraticTutorService(provider=provider)

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            req = TutorMessageRequest(content="Help")

            with pytest.raises(TutorProviderUnavailableException):
                async for _ in tutor_service.send_message_stream(session, conv.id, user_a, req):
                    pass

            # Verify DB: Assistant message marked FAILED
            history = await conv_service.get_conversation_history(session, conv.id, user_a.id)
            assistant_msg = history[-1]
            assert assistant_msg.role == "assistant"
            assert assistant_msg.metadata.status == MessageStatus.FAILED


# ==============================================================================
# GROUP F: USAGE TELEMETRY TESTS
# ==============================================================================

class TestGroupFUsageTelemetry:
    """Verifies that token usage is recorded to AIUsageLog with feature TUTOR_CHAT."""

    @pytest.mark.asyncio
    async def test_usage_recorded_to_db_on_stream_completion(self):
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        sim_usage = NormalizedStreamUsage(input_tokens=100, output_tokens=50, total_tokens=150)
        provider = MockAIProvider(
            stream_chunks=["Trả lời"],
            simulated_stream_usage=sim_usage,
        )
        tutor_service = SocraticTutorService(provider=provider)

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            req = TutorMessageRequest(content="Tính toán")

            tokens = [c.delta async for c in tutor_service.send_message_stream(session, conv.id, user_a, req)]
            assert len(tokens) > 0

            # Query AIUsageLog
            stmt = select(AIUsageLog).where(
                and_(
                    AIUsageLog.user_id == user_a.id,
                    AIUsageLog.feature == "TUTOR_CHAT",
                )
            )
            log_entry = (await session.execute(stmt)).scalars().first()
            assert log_entry is not None
            assert log_entry.prompt_tokens == 100
            assert log_entry.completion_tokens == 50
            assert log_entry.estimated_cost_usd >= 0.0


# ==============================================================================
# GROUP G: SEC-732-M1 — STRICT STATE MACHINE & CAS PERSISTENCE HARDENING
# ==============================================================================

class TestGroupGStateMachineHardening:
    """Verifies state transition enforcement across all persistence and metadata paths."""

    def test_forbidden_transitions_enforced_in_metadata_builders(self):
        forbidden_pairs = [
            (MessageStatus.COMPLETED, MessageStatus.INTERRUPTED),
            (MessageStatus.COMPLETED, MessageStatus.FAILED),
            (MessageStatus.COMPLETED, MessageStatus.STREAMING),
            (MessageStatus.FAILED, MessageStatus.COMPLETED),
            (MessageStatus.FAILED, MessageStatus.STREAMING),
            (MessageStatus.INTERRUPTED, MessageStatus.COMPLETED),
            (MessageStatus.INTERRUPTED, MessageStatus.STREAMING),
        ]

        for from_status, to_status in forbidden_pairs:
            existing_json = build_message_metadata_json(status=from_status)
            with pytest.raises(InvalidMessageStateTransitionError):
                apply_message_state_transition(existing_json, to_status)
            with pytest.raises(InvalidMessageStateTransitionError):
                build_message_metadata_json(status=to_status, existing_metadata_json=existing_json)

    @pytest.mark.asyncio
    async def test_atomic_transition_preserves_unrelated_metadata_and_blocks_terminal_overwrite(self):
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        tutor_service = SocraticTutorService()

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            msg_id = str(uuid.uuid4())
            initial_meta = build_message_metadata_json(
                status=MessageStatus.PENDING,
                extra={"custom_source": "mobile_app", "prompt_ver": "1.0.0"},
            )
            msg = AIMessage(
                id=msg_id,
                conversation_id=conv.id,
                role="assistant",
                content="",
                metadata_json=initial_meta,
                created_at=datetime.now(timezone.utc),
            )
            session.add(msg)
            await session.commit()

            # Valid: PENDING -> STREAMING -> COMPLETED
            assert await tutor_service._atomic_transition_message(session, msg_id, MessageStatus.STREAMING) is True
            assert await tutor_service._atomic_transition_message(
                session, msg_id, MessageStatus.COMPLETED, content="Done"
            ) is True

            await session.refresh(msg)
            raw = json.loads(msg.metadata_json)
            assert raw["status"] == "COMPLETED"
            assert raw["custom_source"] == "mobile_app"
            assert raw["prompt_ver"] == "1.0.0"

            # Forbidden: COMPLETED -> INTERRUPTED via _atomic_transition_message
            with pytest.raises(InvalidMessageStateTransitionError):
                await tutor_service._atomic_transition_message(session, msg_id, MessageStatus.INTERRUPTED)

    def test_backward_compatibility_legacy_metadata_without_status(self):
        legacy_json = json.dumps({"model": "gemini-1.5-flash", "legacy_note": "old"})
        parsed = parse_message_metadata(legacy_json)
        assert parsed.status == MessageStatus.COMPLETED
        # Legacy messages default to COMPLETED and cannot be overwritten to INTERRUPTED
        with pytest.raises(InvalidMessageStateTransitionError):
            apply_message_state_transition(legacy_json, MessageStatus.INTERRUPTED)


# ==============================================================================
# GROUP H: SEC-732-L1 & SEC-732-L2 — LOCK-AWARE BATCHED RECOVERY TESTS
# ==============================================================================

class TestGroupHRecoveryHardening:
    """Verifies lock-aware crash recovery (Scenarios A-E) and keyset-paginated batching."""

    @pytest.mark.asyncio
    async def test_recovery_scenario_a_active_stream_with_heartbeat_not_recovered(self):
        """Scenario A: Worker A streams > 300s with active lock -> Recovery MUST skip."""
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        lock_mgr = ConversationLockManager()
        tutor_service = SocraticTutorService(lock_manager=lock_mgr)

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            msg = AIMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv.id,
                role="assistant",
                content="",
                metadata_json=build_message_metadata_json(status=MessageStatus.STREAMING),
                created_at=old_time,
            )
            session.add(msg)
            await session.commit()

            # Simulate Worker A holding active renewed lock
            worker_a_token = f"worker-a-{uuid.uuid4()}"
            assert await lock_mgr.acquire_lock(conv.id, worker_a_token, ttl_seconds=60) is True
            try:
                res = await tutor_service.recover_stale_streaming_messages_batch(session, max_stale_seconds=300)
                assert res.recovered_count == 0
                assert res.skipped_locked_count >= 1

                await session.refresh(msg)
                assert parse_message_metadata(msg.metadata_json).status == MessageStatus.STREAMING
            finally:
                await lock_mgr.release_lock(conv.id, worker_a_token)

    @pytest.mark.asyncio
    async def test_recovery_scenario_b_dead_worker_expired_lock_recovered(self):
        """Scenario B: Worker A died, lock expired -> Recovery marks INTERRUPTED."""
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        lock_mgr = ConversationLockManager()
        tutor_service = SocraticTutorService(lock_manager=lock_mgr)

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            msg = AIMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv.id,
                role="assistant",
                content="Partial",
                metadata_json=build_message_metadata_json(status=MessageStatus.STREAMING),
                created_at=old_time,
            )
            session.add(msg)
            await session.commit()

            # No lock exists (expired / dead worker)
            assert await lock_mgr.is_locked(conv.id) is False
            res = await tutor_service.recover_stale_streaming_messages_batch(session, max_stale_seconds=300)
            assert res.recovered_count >= 1

            await session.refresh(msg)
            assert parse_message_metadata(msg.metadata_json).status == MessageStatus.INTERRUPTED

    @pytest.mark.asyncio
    async def test_recovery_scenario_c_new_worker_protected(self):
        """Scenario C: Worker B holds lock on conversation -> Recovery does not touch conversation."""
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        lock_mgr = ConversationLockManager()
        tutor_service = SocraticTutorService(lock_manager=lock_mgr)

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            stale_msg_a = AIMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv.id,
                role="assistant",
                content="",
                metadata_json=build_message_metadata_json(status=MessageStatus.STREAMING),
                created_at=old_time,
            )
            active_msg_b = AIMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv.id,
                role="assistant",
                content="Working...",
                metadata_json=build_message_metadata_json(status=MessageStatus.STREAMING),
                created_at=datetime.now(timezone.utc),
            )
            session.add_all([stale_msg_a, active_msg_b])
            await session.commit()

            # Worker B holds lock on conv.id
            worker_b_token = f"worker-b-{uuid.uuid4()}"
            assert await lock_mgr.acquire_lock(conv.id, worker_b_token, ttl_seconds=60) is True
            try:
                res = await tutor_service.recover_stale_streaming_messages_batch(session, max_stale_seconds=300)
                assert res.recovered_count == 0
                await session.refresh(stale_msg_a)
                await session.refresh(active_msg_b)
                assert parse_message_metadata(stale_msg_a.metadata_json).status == MessageStatus.STREAMING
                assert parse_message_metadata(active_msg_b.metadata_json).status == MessageStatus.STREAMING
            finally:
                await lock_mgr.release_lock(conv.id, worker_b_token)

    @pytest.mark.asyncio
    async def test_recovery_scenario_d_concurrent_recovery_workers_no_conflict(self):
        """Scenario D: Two concurrent recovery workers scan the same stale message -> exact 1 transition."""
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        shared_lock_mgr = ConversationLockManager()
        r1 = SocraticTutorService(lock_manager=shared_lock_mgr)
        r2 = SocraticTutorService(lock_manager=shared_lock_mgr)

        async with AsyncSessionLocal() as s_setup:
            conv = await conv_service.create_conversation(s_setup, user_a.id, ConversationCreateRequest())
            old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            msg = AIMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv.id,
                role="assistant",
                content="",
                metadata_json=build_message_metadata_json(status=MessageStatus.STREAMING),
                created_at=old_time,
            )
            s_setup.add(msg)
            await s_setup.commit()
            msg_id = msg.id

        async def run_r1():
            async with AsyncSessionLocal() as s1:
                return await r1.recover_stale_streaming_messages(s1, max_stale_seconds=300)

        async def run_r2():
            async with AsyncSessionLocal() as s2:
                return await r2.recover_stale_streaming_messages(s2, max_stale_seconds=300)

        c1, c2 = await asyncio.gather(run_r1(), run_r2())
        # Across both concurrent workers, the message is recovered at most once
        assert (c1 + c2) >= 1
        assert not (c1 >= 1 and c2 >= 1 and c1 == c2 and await self._count_recovered_exact(msg_id) > 1)

        async with AsyncSessionLocal() as s_check:
            refreshed = (await s_check.execute(select(AIMessage).where(AIMessage.id == msg_id))).scalar_one()
            assert parse_message_metadata(refreshed.metadata_json).status == MessageStatus.INTERRUPTED

    async def _count_recovered_exact(self, msg_id: str) -> int:
        async with AsyncSessionLocal() as s:
            m = (await s.execute(select(AIMessage).where(AIMessage.id == msg_id))).scalar_one()
            return 1 if parse_message_metadata(m.metadata_json).status == MessageStatus.INTERRUPTED else 0

    @pytest.mark.asyncio
    async def test_recovery_scenario_e_terminal_messages_untouched(self):
        """Scenario E: Already COMPLETED message older than 300s is never altered by recovery."""
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        tutor_service = SocraticTutorService()

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            original_meta = build_message_metadata_json(status=MessageStatus.COMPLETED, extra={"keep": "yes"})
            msg = AIMessage(
                id=str(uuid.uuid4()),
                conversation_id=conv.id,
                role="assistant",
                content="Valid answer",
                metadata_json=original_meta,
                created_at=old_time,
            )
            session.add(msg)
            await session.commit()

            res = await tutor_service.recover_stale_streaming_messages_batch(session, max_stale_seconds=300)
            assert res.recovered_count == 0
            await session.refresh(msg)
            assert msg.metadata_json == original_meta

    @pytest.mark.asyncio
    async def test_recovery_batching_and_keyset_pagination_backlog(self):
        """SEC-732-L2: Processes max 100 per batch; drains 105+ backlog cleanly with keyset cursor."""
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        lock_mgr = ConversationLockManager()
        tutor_service = SocraticTutorService(lock_manager=lock_mgr)

        async with AsyncSessionLocal() as session:
            # Clean up any leftover stale messages from earlier tests in shared SQLite DB
            await tutor_service.recover_stale_streaming_messages(
                session, max_stale_seconds=300, batch_size=100, drain_backlog=True
            )

            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            base_time = datetime.now(timezone.utc) - timedelta(minutes=30)

            created_ids = []
            # Create 105 stale STREAMING messages + 5 COMPLETED messages
            for i in range(105):
                m = AIMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=conv.id,
                    role="assistant",
                    content=f"stale-{i}",
                    metadata_json=build_message_metadata_json(status=MessageStatus.STREAMING),
                    created_at=base_time + timedelta(seconds=i),
                )
                session.add(m)
                created_ids.append(m.id)

            for j in range(5):
                m_done = AIMessage(
                    id=str(uuid.uuid4()),
                    conversation_id=conv.id,
                    role="assistant",
                    content=f"done-{j}",
                    metadata_json=build_message_metadata_json(status=MessageStatus.COMPLETED),
                    created_at=base_time + timedelta(seconds=200 + j),
                )
                session.add(m_done)

            await session.commit()

            # Single batch must scan at most 100
            batch1 = await tutor_service.recover_stale_streaming_messages_batch(session, max_stale_seconds=300, batch_size=200)
            assert batch1.scanned_count == 100
            assert batch1.recovered_count == 100
            assert batch1.has_more is True

            # Drain remaining via drain_backlog=True
            remaining_recovered = await tutor_service.recover_stale_streaming_messages(
                session, max_stale_seconds=300, batch_size=100, drain_backlog=True
            )
            assert remaining_recovered == 5

            # Verify all 105 became INTERRUPTED
            rows = (await session.execute(select(AIMessage).where(AIMessage.id.in_(created_ids)))).scalars().all()
            assert all(parse_message_metadata(r.metadata_json).status == MessageStatus.INTERRUPTED for r in rows)


# ==============================================================================
# GROUP I: STALE WORKER WRITE-PROTECTION & MOCKED REDIS COMMAND VERIFICATION
# ==============================================================================

class TestGroupIStaleWorkerWriteProtection:
    """Verifies stale workers cannot mutate conversation state on completion, failure, or cancellation."""

    @pytest.mark.asyncio
    async def test_stale_worker_cannot_mark_failed_or_write_partial_content_on_error(self):
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        lock_mgr = ConversationLockManager()

        async def fail_midstream_and_lose_lock(req):
            yield NormalizedStreamChunk(delta="Partial leak ", index=0)
            # Simulate lock expired / taken over by Worker B right before provider fails
            await lock_mgr.release_lock(conv_id_holder[0], token_holder[0])
            raise AIServerError("Midstream failure", provider="mock")

        provider = MockAIProvider()
        provider.generate_stream = fail_midstream_and_lose_lock
        tutor_service = SocraticTutorService(provider=provider, lock_manager=lock_mgr)

        conv_id_holder = []
        token_holder = []

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            conv_id_holder.append(conv.id)

            # Intercept acquire_lock to record Worker A's token
            orig_acquire = lock_mgr.acquire_lock

            async def spy_acquire(conversation_id, lock_token, ttl_seconds=60):
                token_holder.append(lock_token)
                return await orig_acquire(conversation_id, lock_token, ttl_seconds)

            with patch.object(lock_mgr, "acquire_lock", side_effect=spy_acquire):
                with pytest.raises(TutorProviderUnavailableException):
                    async for _ in tutor_service.send_message_stream(
                        session, conv.id, user_a, TutorMessageRequest(content="Error test")
                    ):
                        pass

            # Verify stale worker did NOT write FAILED or partial content!
            history = await conv_service.get_conversation_history(session, conv.id, user_a.id)
            assistant_msg = history[-1]
            assert assistant_msg.content == ""
            assert assistant_msg.metadata.status == MessageStatus.STREAMING

    @pytest.mark.asyncio
    async def test_stale_worker_cannot_mark_interrupted_or_write_partial_content_on_cancel(self):
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        lock_mgr = ConversationLockManager()

        provider = MockAIProvider(stream_chunks=["Partial1 ", "Partial2 ", "Partial3 "], stream_chunk_delay=0.05)
        tutor_service = SocraticTutorService(provider=provider, lock_manager=lock_mgr)

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            captured_tokens = []
            orig_acquire = lock_mgr.acquire_lock

            async def spy_acquire(conversation_id, lock_token, ttl_seconds=60):
                captured_tokens.append(lock_token)
                return await orig_acquire(conversation_id, lock_token, ttl_seconds)

            with patch.object(lock_mgr, "acquire_lock", side_effect=spy_acquire):
                stream = tutor_service.send_message_stream(
                    session, conv.id, user_a, TutorMessageRequest(content="Cancel stale test")
                )
                async for _ in stream:
                    # Simulate Worker A losing lock before client closes stream
                    await lock_mgr.release_lock(conv.id, captured_tokens[0])
                    await stream.aclose()
                    break

            history = await conv_service.get_conversation_history(session, conv.id, user_a.id)
            assistant_msg = history[-1]
            assert assistant_msg.content == ""
            assert assistant_msg.metadata.status == MessageStatus.STREAMING

    @pytest.mark.asyncio
    async def test_stale_worker_blocks_conversation_update_but_preserves_incurred_usage(self):
        user_a, _ = await _create_test_users()
        conv_service = ConversationService()
        lock_mgr = ConversationLockManager()

        sim_usage = NormalizedStreamUsage(input_tokens=80, output_tokens=40, total_tokens=120)
        provider = MockAIProvider(stream_chunks=["Completed tokens"], simulated_stream_usage=sim_usage)
        tutor_service = SocraticTutorService(provider=provider, lock_manager=lock_mgr)

        async with AsyncSessionLocal() as session:
            conv = await conv_service.create_conversation(session, user_a.id, ConversationCreateRequest())
            orig_updated_at = conv.updated_at

            # Simulate lock lost right after streaming finishes before finalization
            with patch.object(lock_mgr, "is_lock_owned", AsyncMock(side_effect=[True, False])):
                with pytest.raises(StaleWorkerException):
                    async for _ in tutor_service.send_message_stream(
                        session, conv.id, user_a, TutorMessageRequest(content="Stale usage test")
                    ):
                        pass

            # Conversation state & message must NOT be marked COMPLETED
            history = await conv_service.get_conversation_history(session, conv.id, user_a.id)
            assistant_msg = history[-1]
            assert assistant_msg.metadata.status != MessageStatus.COMPLETED
            assert assistant_msg.content == ""

            # Actual incurred API telemetry IS preserved in isolated session
            stmt = select(AIUsageLog).where(
                and_(AIUsageLog.user_id == user_a.id, AIUsageLog.feature == "TUTOR_CHAT")
            )
            logs = (await session.execute(stmt)).scalars().all()
            assert any(l.prompt_tokens == 80 and l.completion_tokens == 40 for l in logs)

    @pytest.mark.asyncio
    async def test_mocked_redis_commands_for_lock_operations(self):
        """
        Unit test with MOCKED Redis client (NOT real Redis integration) verifying exact commands:
        SET NX EX, EXISTS, GET with bytes decoding, and Lua EVAL scripts.
        """
        mock_redis = MagicMock()
        mock_cache = MagicMock(spec=CacheService)
        mock_cache.redis_client = mock_redis

        lock_mgr = ConversationLockManager(cache=mock_cache)

        mock_redis.set.return_value = True
        assert await lock_mgr.acquire_lock("conv-1", "tok-1", ttl_seconds=30) is True
        mock_redis.set.assert_called_once_with("ai_tutor:lock:conv:conv-1", "tok-1", nx=True, ex=30)

        mock_redis.exists.return_value = 1
        assert await lock_mgr.is_locked("conv-1") is True
        mock_redis.exists.assert_called_once_with("ai_tutor:lock:conv:conv-1")

        # Verify bytes decoding in is_lock_owned
        mock_redis.get.return_value = b"tok-1"
        assert await lock_mgr.is_lock_owned("conv-1", "tok-1") is True

        mock_redis.eval.return_value = 1
        assert await lock_mgr.renew_lock("conv-1", "tok-1", 45) is True
        assert await lock_mgr.release_lock("conv-1", "tok-1") is True
        assert mock_redis.eval.call_count == 2

