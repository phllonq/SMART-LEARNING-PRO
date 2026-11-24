"""
Wrong Answer Diagnostic Service — Phase 7.2.2

Orchestrates the AI-powered diagnostic workflow for student wrong answers:
- Authoritative database loading & ownership/tenant authorization BEFORE cache lookup.
- Strict read-only invariant on examination domain entities.
- Idempotent caching with distributed locking (Redis) and in-memory fallback.
- AI provider integration via normalized contracts and prompt registry.
- Error-isolated usage telemetry.
"""

import asyncio
import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cache import CacheService, cache_service
from app.modules.ai_engine.diagnostics.exceptions import (
    AIProviderUnavailableException,
    AITimeoutException,
    AIMalformedOutputException,
    AttemptNotFoundException,
    AttemptNotSubmittedException,
    CacheCoordinationException,
    DiagnosticUnauthorizedException,
    GradingUnavailableException,
    QuestionAlreadyCorrectException,
    QuestionNotInAttemptException,
)
from app.modules.ai_engine.diagnostics.prompts import (
    PROMPT_KEY,
    PROMPT_VERSION,
    build_diagnostic_prompt,
)
from app.modules.ai_engine.diagnostics.schemas import (
    DiagnosticContext,
    DiagnosticDetail,
    ErrorCategory,
    WrongAnswerDiagnosticResponse,
    parse_llm_diagnostic_json,
)
from app.modules.ai_engine.exceptions import (
    AIAuthenticationError,
    AIConfigurationError,
    AIMalformedResponseError,
    AIRateLimitError,
    AIServerError,
    AITimeoutError,
)
from app.modules.ai_engine.factory import get_llm_provider
from app.modules.ai_engine.providers.base import BaseLLMProvider
from app.modules.ai_engine.usage import create_usage_record, record_usage_to_db
from app.modules.auth.models import User
from app.modules.exams.models import AttemptStatus, ExamAttempt, ExamQuestion, StudentAnswer
from app.modules.questions.models import Question, QuestionType

logger = logging.getLogger(__name__)

# Terminal statuses where exam review & diagnostics are permitted
ALLOWED_TERMINAL_STATUSES: Set[str] = {
    AttemptStatus.SUBMITTED.value,
    AttemptStatus.AUTO_SUBMITTED.value,
    AttemptStatus.GRADED.value,
}

# Distributed lock TTL in seconds (auto-expires to prevent deadlocks)
# Set to 45s to guarantee outliving standard AI timeout (15s) + retry budget + safety margin
DEFAULT_LOCK_TTL_SECONDS: int = 45

# Polling wait timeout for concurrent requests in seconds
DEFAULT_CONCURRENT_WAIT_TIMEOUT: float = 20.0

# Polling interval in seconds
DEFAULT_POLL_INTERVAL: float = 0.2

# Cache TTL for diagnostic responses (24 hours)
DEFAULT_CACHE_TTL_SECONDS: int = 86400


class WrongAnswerDiagnosticService:
    """
    Production-grade service for analyzing student wrong answers.

    Guarantees & System Boundaries:
    - Never mutates exam attempts, student answers, questions, or scores (strict read-only invariants).
    - Authorizes student ownership & tenant BEFORE checking cache.
    - Mitigates duplicate concurrent AI requests via Redis distributed lock (concurrency mitigation mechanism).
      NOTE: Under normal operating conditions, Redis lock effectively coordinates concurrent requests.
      However, Redis lock does NOT provide an absolute guarantee of exactly-once external execution under
      all failure modes (e.g., Redis network partition, failover split-brain, ungraceful crash, or lease expiry).
    - Prevents stale workers from overwriting fresh cache entries via atomic Lua ownership verification.
    - Provides graceful process-local fallback when Redis is unavailable (degraded mode logged).
    - Emits usage telemetry without breaking response on database failure.
    """

    def __init__(
        self,
        provider: Optional[BaseLLMProvider] = None,
        cache: Optional[CacheService] = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        lock_ttl_seconds: Optional[int] = None,
    ):
        self._provider = provider
        self._cache = cache or cache_service
        self._cache_ttl = cache_ttl_seconds
        self._lock_ttl = lock_ttl_seconds

        # In-memory lock registry for process-local coordination fallback:
        # Maps lock_key -> (lock_token, expire_timestamp)
        self._in_memory_locks: Dict[str, Tuple[str, float]] = {}
        self._mem_lock_guard = asyncio.Lock()

    def _get_provider(self) -> BaseLLMProvider:
        """Return injected provider or default configured provider."""
        if self._provider is not None:
            return self._provider
        return get_llm_provider()

    def _calculate_lock_ttl(self) -> int:
        """
        Dynamically calculate safe lock TTL based on provider total_timeout + safety margin.
        Formula: max(DEFAULT_LOCK_TTL_SECONDS, int(total_timeout + 15.0))
        Guarantees that the lock outlives the maximum provider generation deadline.
        """
        provider = self._get_provider()
        total_timeout = getattr(provider, "total_timeout", getattr(provider, "timeout_seconds", 15.0))
        return max(DEFAULT_LOCK_TTL_SECONDS, int(total_timeout + 15.0))

    def _calculate_poll_timeout(self) -> float:
        """
        Dynamically calculate concurrent request polling timeout.
        Must be at least equal to provider total_timeout + 5.0s margin.
        """
        provider = self._get_provider()
        total_timeout = getattr(provider, "total_timeout", getattr(provider, "timeout_seconds", 15.0))
        return max(DEFAULT_CONCURRENT_WAIT_TIMEOUT, float(total_timeout + 5.0))

    # -----------------------------------------------------------------------
    # Main Entry Point
    # -----------------------------------------------------------------------

    async def diagnose_wrong_answer(
        self,
        db: AsyncSession,
        attempt_id: str,
        question_id: str,
        student: User,
        tenant_id: Optional[str] = None,
    ) -> WrongAnswerDiagnosticResponse:
        """
        Analyze a student's wrong answer for a specific question in a submitted attempt.

        Steps:
        1. AUTHORIZATION & VALIDATION (DB query, read-only, BEFORE cache).
        2. ASSEMBLE CONTEXT from authoritative database/snapshot records.
        3. CONSTRUCT MULTIDIMENSIONAL CACHE KEY & CHECK CACHE.
        4. COORDINATE CONCURRENT REQUESTS (Distributed lock).
        5. CALL AI & VALIDATE OUTPUT against Pydantic schema.
        6. STORE TO CACHE & RECORD USAGE TELEMETRY.
        7. RELEASE LOCK & RETURN RESPONSE.
        """
        # ===================================================================
        # 1. AUTHORIZATION & VALIDATION (BEFORE CACHE LOOKUP)
        # ===================================================================
        attempt, student_answer, question_data = await self._load_and_authorize(
            db=db,
            attempt_id=attempt_id,
            question_id=question_id,
            student=student,
            tenant_id=tenant_id,
        )

        # ===================================================================
        # 2. ASSEMBLE CONTEXT FROM AUTHORITATIVE RECORDS
        # ===================================================================
        context = self._build_diagnostic_context(
            question_data=question_data,
            student_answer=student_answer,
        )

        # Determine effective tenant scope
        effective_tenant = self._resolve_tenant(student, attempt, tenant_id)

        # Determine active model name for cache fingerprinting
        provider = self._get_provider()
        model_name = getattr(provider, "model_name", "default-model")

        # ===================================================================
        # 3. CACHE KEY & CACHE LOOKUP
        # ===================================================================
        cache_key = self._generate_cache_key(
            tenant_id=effective_tenant,
            student_id=student.id,
            attempt_id=attempt.id,
            question_id=question_id,
            student_answer=student_answer,
            context=context,
            model_name=model_name,
        )

        cached_data = self._cache.get_json(cache_key)
        if cached_data is not None:
            try:
                cached_response = WrongAnswerDiagnosticResponse.model_validate(cached_data)
                return cached_response.model_copy(update={"cached": True, "latency_ms": 0.0})
            except Exception as exc:
                logger.warning("Corrupted diagnostic cache entry for key '%s': %s. Regenerating.", cache_key, exc)
                self._cache.delete(cache_key)

        # ===================================================================
        # 4. CONCURRENCY COORDINATION (DISTRIBUTED LOCK)
        # ===================================================================
        lock_key = f"lock:{cache_key}"
        lock_token = str(uuid.uuid4())

        effective_lock_ttl = self._lock_ttl if self._lock_ttl is not None else self._calculate_lock_ttl()
        poll_timeout = self._calculate_poll_timeout()

        # Check if Redis is unavailable and log degraded mode warning
        if not hasattr(self._cache, "redis_client") or self._cache.redis_client is None:
            logger.warning(
                "Redis is unavailable. Running in degraded mode: distributed idempotency across multiple workers is not guaranteed."
            )

        acquired = await self._acquire_lock(lock_key, lock_token, ttl_seconds=effective_lock_ttl)
        if not acquired:
            # Another concurrent request is currently generating this diagnostic.
            # Wait for it to finish and populate the cache.
            logger.info("Concurrent request detected for cache key '%s'. Waiting on cache.", cache_key)
            polled_data = await self._poll_cache(cache_key, timeout_seconds=poll_timeout)
            if polled_data is not None:
                try:
                    response = WrongAnswerDiagnosticResponse.model_validate(polled_data)
                    return response.model_copy(update={"cached": True, "latency_ms": 0.0})
                except Exception:
                    pass

            # Timeout expired without cache population; attempt to acquire lock once more
            acquired = await self._acquire_lock(lock_key, lock_token, ttl_seconds=effective_lock_ttl)
            if not acquired:
                raise CacheCoordinationException(
                    "Hệ thống đang xử lý chẩn đoán này từ một yêu cầu khác. Vui lòng thử lại sau giây lát."
                )

        # Heartbeat renewal task to prevent lock expiration during prolonged AI generation
        heartbeat_task: Optional[asyncio.Task] = None
        if effective_lock_ttl > 5:
            renewal_interval = max(3.0, float(effective_lock_ttl) / 3.0)
            heartbeat_task = asyncio.create_task(
                self._heartbeat_worker(lock_key, lock_token, effective_lock_ttl, renewal_interval)
            )

        # ===================================================================
        # 5. AI INVOCATION & OUTPUT VALIDATION
        # ===================================================================
        try:
            # Notice: No DB row lock or transaction is held open during AI network call.
            prompt_request = build_diagnostic_prompt(context)

            ai_response = await provider.generate(prompt_request)

            # Strict Pydantic v2 validation (raises AIMalformedResponseError on invalid JSON)
            diagnostic_detail = parse_llm_diagnostic_json(ai_response.text)

            # Check if AI lacked evidence
            is_sufficient = diagnostic_detail.error_category != ErrorCategory.INSUFFICIENT_INFORMATION

            response = WrongAnswerDiagnosticResponse(
                diagnostic=diagnostic_detail,
                cached=False,
                latency_ms=ai_response.latency_ms,
                prompt_version=PROMPT_VERSION,
                is_sufficient=is_sufficient,
            )

            # ===============================================================
            # 6. WRITE TO CACHE & RECORD USAGE TELEMETRY
            # ===============================================================
            # Stale worker protection: only write to cache if caller still owns the lock token
            await self._safe_cache_write(
                lock_key=lock_key,
                lock_token=lock_token,
                cache_key=cache_key,
                data=response.model_dump(),
                ttl_seconds=self._cache_ttl,
            )

            # Telemetry is error-isolated: never fails the response
            usage_record = create_usage_record(
                response=ai_response,
                user_id=student.id,
                feature="WRONG_ANSWER_ANALYSIS",
            )
            await record_usage_to_db(db, usage_record)

            return response

        except (AITimeoutError, asyncio.TimeoutError) as exc:
            logger.warning("AI generation timed out for attempt %s, question %s: %s", attempt_id, question_id, exc)
            raise AITimeoutException("Quá thời gian phản hồi từ dịch vụ AI chẩn đoán. Vui lòng thử lại sau.") from exc
        except (AIServerError, AIRateLimitError, AIConfigurationError, AIAuthenticationError) as exc:
            logger.error("AI provider error for attempt %s, question %s: %s", attempt_id, question_id, exc)
            raise AIProviderUnavailableException("Dịch vụ AI chẩn đoán hiện không khả dụng. Vui lòng thử lại sau.") from exc
        except AIMalformedResponseError as exc:
            logger.error("AI returned malformed JSON for attempt %s, question %s: %s", attempt_id, question_id, exc)
            raise AIMalformedOutputException("Phản hồi từ AI không đúng cấu trúc yêu cầu.") from exc
        except Exception as exc:
            # Re-raise cancellation directly
            if isinstance(exc, asyncio.CancelledError):
                raise
            logger.exception("Unexpected error during wrong answer diagnosis: %s", exc)
            raise AIProviderUnavailableException("Lỗi không xác định khi gọi AI chẩn đoán. Vui lòng thử lại sau.") from exc
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
                except Exception as exc:
                    logger.error("Heartbeat task completed with error: %s", exc)
            # Always safely release the lock (token-verified release)
            await self._release_lock(lock_key, lock_token)

    # -----------------------------------------------------------------------
    # Database Loading & Authorization
    # -----------------------------------------------------------------------

    async def _load_and_authorize(
        self,
        db: AsyncSession,
        attempt_id: str,
        question_id: str,
        student: User,
        tenant_id: Optional[str] = None,
    ) -> Tuple[ExamAttempt, StudentAnswer, Dict[str, Any]]:
        """
        Execute all authorization and domain state checks strictly against authoritative DB records.
        Does NOT acquire FOR UPDATE locks (read-only select).
        """
        # 1. Attempt exists
        stmt = (
            select(ExamAttempt)
            .where(ExamAttempt.id == attempt_id)
            .options(
                selectinload(ExamAttempt.answers),
                selectinload(ExamAttempt.exam),
                selectinload(ExamAttempt.assignment),
            )
        )
        res = await db.execute(stmt)
        attempt = res.scalar_one_or_none()
        if not attempt:
            raise AttemptNotFoundException(attempt_id)

        # 2. Ownership: attempt belongs to authenticated student
        if attempt.student_id != student.id:
            raise DiagnosticUnauthorizedException("Bạn không phải chủ sở hữu của bài thi này.")

        # 3. Tenant / School Scope Isolation
        expected_tenant = self._resolve_tenant(student, attempt, tenant_id)
        attempt_tenant = getattr(attempt, "tenant_id", getattr(attempt, "school_id", expected_tenant))
        if attempt_tenant != expected_tenant:
            raise DiagnosticUnauthorizedException(
                "Truy cập bị từ chối do không khớp phạm vi trường học/đơn vị (tenant)."
            )

        # 4. Attempt status: must be in terminal state (SUBMITTED, AUTO_SUBMITTED, GRADED)
        if attempt.status == AttemptStatus.IN_PROGRESS.value:
            raise AttemptNotSubmittedException(attempt.status)
        if attempt.status not in ALLOWED_TERMINAL_STATUSES:
            raise AttemptNotSubmittedException(attempt.status)

        # 5. Question belongs to exam in this attempt
        snapshot = json.loads(attempt.questions_snapshot_json or "[]")
        valid_q_ids = {q["question_id"] for q in snapshot}
        if not valid_q_ids:
            # Fallback to ExamQuestion table
            eq_stmt = select(ExamQuestion.question_id).where(ExamQuestion.exam_id == attempt.exam_id)
            eq_res = await db.execute(eq_stmt)
            valid_q_ids = set(eq_res.scalars().all())

        if question_id not in valid_q_ids:
            raise QuestionNotInAttemptException(question_id)

        # 6. Authoritative grading result exists
        student_answer = next((a for a in attempt.answers if a.question_id == question_id), None)
        if student_answer is None or student_answer.is_correct is None:
            raise GradingUnavailableException(question_id)

        # 7. Answer must be incorrect
        if student_answer.is_correct is True:
            raise QuestionAlreadyCorrectException(question_id)

        # 8. Load authoritative question details (snapshot first, then DB fallback)
        question_data = await self._load_authoritative_question_data(db, attempt, question_id)

        return attempt, student_answer, question_data

    async def _load_authoritative_question_data(
        self,
        db: AsyncSession,
        attempt: ExamAttempt,
        question_id: str,
    ) -> Dict[str, Any]:
        """Extract authoritative question content, options, and explanation."""
        # 1. From answer_key_snapshot_json if present
        if attempt.answer_key_snapshot_json:
            try:
                raw_keys = json.loads(attempt.answer_key_snapshot_json)
                for item in raw_keys:
                    if item.get("question_id") == question_id:
                        return item
            except Exception:
                pass

        # 2. From database fallback
        q_stmt = (
            select(Question)
            .where(Question.id == question_id)
            .options(selectinload(Question.options))
        )
        q_res = await db.execute(q_stmt)
        q_obj = q_res.scalar_one_or_none()
        if not q_obj:
            raise QuestionNotInAttemptException(question_id)

        return {
            "question_id": q_obj.id,
            "content": q_obj.content,
            "question_type": q_obj.question_type,
            "explanation": q_obj.explanation,
            "options": [
                {
                    "id": opt.id,
                    "option_key": opt.option_key,
                    "content": opt.content,
                    "is_correct": opt.is_correct,
                }
                for opt in q_obj.options
            ],
        }

    # -----------------------------------------------------------------------
    # Context Assembly
    # -----------------------------------------------------------------------

    def _build_diagnostic_context(
        self,
        question_data: Dict[str, Any],
        student_answer: StudentAnswer,
    ) -> DiagnosticContext:
        """Construct DiagnosticContext with formatted student answer and correct answer."""
        content = question_data.get("content", "").strip()
        q_type = question_data.get("question_type", QuestionType.SINGLE_CHOICE.value)
        explanation = question_data.get("explanation")
        options = question_data.get("options", [])

        # Format student answer
        student_answer_str = self._format_student_answer(student_answer, options, q_type)

        # Format correct answer
        correct_answer_str = self._format_correct_answer(options, explanation, q_type)

        return DiagnosticContext(
            question_content=content,
            question_type=q_type,
            student_answer=student_answer_str,
            correct_answer=correct_answer_str,
            explanation=explanation.strip() if explanation else None,
        )

    def _format_student_answer(
        self,
        ans: StudentAnswer,
        options: List[Dict[str, Any]],
        q_type: str,
    ) -> Optional[str]:
        """Convert student answer entity into human-readable text."""
        # Skipped question
        if not ans.selected_option_id and not ans.selected_option_ids_json and not ans.answer_text:
            return None

        # Text answer
        if ans.answer_text and ans.answer_text.strip():
            return ans.answer_text.strip()

        # Multiple choice
        if ans.selected_option_ids_json:
            try:
                selected_ids = set(json.loads(ans.selected_option_ids_json))
                matched = [o for o in options if o["id"] in selected_ids]
                if matched:
                    return "; ".join(f"[{o['option_key']}] {o['content']}" for o in matched)
            except Exception:
                pass

        # Single choice
        if ans.selected_option_id:
            matched = next((o for o in options if o["id"] == ans.selected_option_id), None)
            if matched:
                return f"[{matched['option_key']}] {matched['content']}"

        return None

    def _format_correct_answer(
        self,
        options: List[Dict[str, Any]],
        explanation: Optional[str],
        q_type: str,
    ) -> str:
        """Extract authoritative correct answer string."""
        correct_options = [o for o in options if o.get("is_correct")]
        if correct_options:
            return "; ".join(f"[{o['option_key']}] {o['content']}" for o in correct_options)

        if explanation and explanation.strip():
            return explanation.strip()

        return "[KHÔNG CÓ ĐÁP ÁN CHÍNH THỨC]"

    # -----------------------------------------------------------------------
    # Tenant Resolution & Cache Key Design
    # -----------------------------------------------------------------------

    def _resolve_tenant(
        self,
        student: User,
        attempt: ExamAttempt,
        explicit_tenant_id: Optional[str] = None,
    ) -> str:
        """Resolve authoritative tenant/school scope."""
        if explicit_tenant_id:
            return explicit_tenant_id.strip()
        student_tenant = getattr(student, "tenant_id", getattr(student, "school_id", None))
        if student_tenant:
            return str(student_tenant).strip()
        attempt_tenant = getattr(attempt, "tenant_id", getattr(attempt, "school_id", None))
        if attempt_tenant:
            return str(attempt_tenant).strip()
        return "default"

    def _generate_cache_key(
        self,
        tenant_id: str,
        student_id: str,
        attempt_id: str,
        question_id: str,
        student_answer: StudentAnswer,
        context: DiagnosticContext,
        model_name: str,
    ) -> str:
        """
        Construct a collision-free, multidimensional cache key.

        Dimensions accounted for:
        - Tenant/school scope.
        - Student ownership.
        - Attempt ID & Question ID.
        - Answer version + answer text fingerprint.
        - Prompt version.
        - Model/provider identifier.
        """
        answer_fingerprint_raw = (
            f"ver:{student_answer.version}|"
            f"ans:{context.student_answer or ''}|"
            f"corr:{context.correct_answer}|"
            f"prompt:{PROMPT_VERSION}|"
            f"model:{model_name}"
        )
        fingerprint = hashlib.sha256(answer_fingerprint_raw.encode("utf-8")).hexdigest()[:16]
        return f"diag:{tenant_id}:{student_id}:{attempt_id}:{question_id}:{PROMPT_VERSION}:{fingerprint}"

    # -----------------------------------------------------------------------
    # Concurrency & Distributed Lock Management
    # -----------------------------------------------------------------------

    async def _acquire_lock(self, lock_key: str, lock_token: str, ttl_seconds: int = 30) -> bool:
        """Acquire distributed lock via Redis or in-memory fallback."""
        # 1. Redis distributed lock
        if hasattr(self._cache, "redis_client") and self._cache.redis_client is not None:
            try:
                acquired = self._cache.redis_client.set(lock_key, lock_token, ex=ttl_seconds, nx=True)
                return bool(acquired)
            except Exception as exc:
                logger.warning("Redis lock acquisition failed (%s). Falling back to memory lock.", exc)

        # 2. In-memory fallback lock (process-local)
        async with self._mem_lock_guard:
            now = time.time()
            existing = self._in_memory_locks.get(lock_key)
            if existing is not None:
                existing_token, expire_at = existing
                if expire_at > now:
                    # Still locked by another request
                    return False

            # Lock is either free or expired
            self._in_memory_locks[lock_key] = (lock_token, now + ttl_seconds)
            return True

    async def _release_lock(self, lock_key: str, lock_token: str) -> bool:
        """Release distributed lock only if lock_token matches."""
        # 1. Redis distributed lock release (Lua script ensures atomic release only by token owner)
        if hasattr(self._cache, "redis_client") and self._cache.redis_client is not None:
            try:
                lua = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("del", KEYS[1])
                else
                    return 0
                end
                """
                res = self._cache.redis_client.eval(lua, 1, lock_key, lock_token)
                return bool(res)
            except Exception as exc:
                logger.warning("Redis lock release failed (%s).", exc)

        # 2. In-memory fallback lock release
        async with self._mem_lock_guard:
            existing = self._in_memory_locks.get(lock_key)
            if existing is not None:
                existing_token, _ = existing
                if existing_token == lock_token:
                    del self._in_memory_locks[lock_key]
                    return True
            return False

    async def _renew_lock(self, lock_key: str, lock_token: str, extension_seconds: int) -> bool:
        """
        Extend/renew lock TTL only if caller owns the matching lock_token.
        Uses atomic Lua script on Redis or thread-safe in-memory update.
        """
        # 1. Redis distributed lock renewal (Lua script checks token ownership before EXPIRE)
        if hasattr(self._cache, "redis_client") and self._cache.redis_client is not None:
            try:
                lua = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    return redis.call("expire", KEYS[1], ARGV[2])
                else
                    return 0
                end
                """
                res = self._cache.redis_client.eval(lua, 1, lock_key, lock_token, extension_seconds)
                return bool(res)
            except Exception as exc:
                logger.warning("Redis lock renewal failed (%s).", exc)
                return False

        # 2. In-memory fallback lock renewal
        async with self._mem_lock_guard:
            existing = self._in_memory_locks.get(lock_key)
            if existing is not None:
                existing_token, _ = existing
                if existing_token == lock_token:
                    self._in_memory_locks[lock_key] = (lock_token, time.time() + extension_seconds)
                    return True
            return False

    async def _safe_cache_write(
        self,
        lock_key: str,
        lock_token: str,
        cache_key: str,
        data: Dict[str, Any],
        ttl_seconds: int,
    ) -> bool:
        """
        Conditionally write diagnostic response to cache ONLY IF caller still owns the lock.
        Uses an atomic Redis Lua script (or memory-lock guard) to prevent stale workers
        whose lock expired from overwriting cache entries written or owned by newer workers.
        """
        # 1. Redis atomic verification and write via Lua script
        if hasattr(self._cache, "redis_client") and self._cache.redis_client is not None:
            try:
                lua = """
                if redis.call("get", KEYS[1]) == ARGV[1] then
                    redis.call("set", KEYS[2], ARGV[2], "ex", ARGV[3])
                    return 1
                else
                    return 0
                end
                """
                payload = json.dumps(data, ensure_ascii=False)
                res = self._cache.redis_client.eval(lua, 2, lock_key, cache_key, lock_token, payload, ttl_seconds)
                if not bool(res):
                    logger.warning(
                        "Stale worker detected during cache write for key '%s': lock token mismatch or expired. Skipping cache write.",
                        cache_key,
                    )
                    return False
                return True
            except Exception as exc:
                logger.warning("Redis atomic cache write failed (%s). Skipping cache write.", exc)
                return False

        # 2. In-memory fallback verification and write
        async with self._mem_lock_guard:
            now = time.time()
            existing = self._in_memory_locks.get(lock_key)
            if existing is not None:
                existing_token, expire_at = existing
                if existing_token == lock_token and expire_at > now:
                    self._cache.set_json(cache_key, data, expire_seconds=ttl_seconds)
                    return True

            logger.warning(
                "Stale worker detected in memory for key '%s': lock expired or token mismatch. Skipping cache write.",
                cache_key,
            )
            return False

    async def _heartbeat_worker(
        self,
        lock_key: str,
        lock_token: str,
        ttl_seconds: int,
        interval_seconds: float,
    ) -> None:
        """
        Background task that periodically extends the lock TTL while AI is executing.
        Ensures lock does not expire during unusually long generation or retry backoff.
        """
        try:
            while True:
                await asyncio.sleep(interval_seconds)
                renewed = await self._renew_lock(lock_key, lock_token, ttl_seconds)
                if not renewed:
                    logger.warning(
                        "Lock renewal failed for key '%s'; lock lost or taken over. Terminating heartbeat.",
                        lock_key,
                    )
                    break
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(
                "Heartbeat task encountered unexpected error for lock '%s': %s",
                lock_key,
                exc,
                exc_info=True,
            )

    async def _poll_cache(
        self,
        cache_key: str,
        timeout_seconds: float = DEFAULT_CONCURRENT_WAIT_TIMEOUT,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> Optional[Dict[str, Any]]:
        """Poll the cache until data is populated or timeout expires."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            data = self._cache.get_json(cache_key)
            if data is not None:
                return data
            await asyncio.sleep(poll_interval)
        return None
