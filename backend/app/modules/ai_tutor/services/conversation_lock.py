"""
Distributed Conversation Lock Manager - SMART LEARNING PRO
Provides atomic Redis-based distributed locking with in-memory fallback for conversation synchronization.
Guarantees:
  - Atomic acquire via SET NX EX
  - Atomic release via Lua script (token-verified)
  - Atomic heartbeat lease renewal via Lua script
  - Stale worker detection (prevents stale writes after lock expiration)
  - Explicit boundaries: in-memory fallback is single-process local only.
"""

import asyncio
import logging
import time
import uuid
from typing import Optional, Dict, Tuple

from app.core.cache import CacheService, cache_service

logger = logging.getLogger(__name__)

DEFAULT_LOCK_TTL_SECONDS: int = 60
DEFAULT_HEARTBEAT_INTERVAL: float = 20.0


class ConversationLockManager:
    """
    Coordinates access to active conversation turns to prevent race conditions
    and history divergence.
    """

    def __init__(self, cache: Optional[CacheService] = None):
        self._cache = cache or cache_service
        self._mem_guard = asyncio.Lock()
        # In-memory store: lock_key -> (lock_token, expire_timestamp)
        self._in_memory_locks: Dict[str, Tuple[str, float]] = {}

    def _get_lock_key(self, conversation_id: str) -> str:
        return f"ai_tutor:lock:conv:{conversation_id}"

    async def acquire_lock(
        self,
        conversation_id: str,
        lock_token: str,
        ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
    ) -> bool:
        """
        Atomically acquire exclusive lease on a conversation.
        Returns True if acquired, False if already held by another turn.
        """
        lock_key = self._get_lock_key(conversation_id)

        # 1. Distributed Redis Lock
        if hasattr(self._cache, "redis_client") and self._cache.redis_client is not None:
            try:
                acquired = self._cache.redis_client.set(lock_key, lock_token, nx=True, ex=ttl_seconds)
                return bool(acquired)
            except Exception as exc:
                logger.warning("Redis acquire_lock failed (%s). Falling back to in-memory lock.", exc)

        # 2. In-memory process-local fallback
        async with self._mem_guard:
            now = time.time()
            existing = self._in_memory_locks.get(lock_key)
            if existing is not None:
                _, expire_at = existing
                if expire_at > now:
                    # Still locked by active local turn
                    return False

            self._in_memory_locks[lock_key] = (lock_token, now + ttl_seconds)
            return True

    async def renew_lock(
        self,
        conversation_id: str,
        lock_token: str,
        extension_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
    ) -> bool:
        """
        Renew/extend lock lease only if caller still holds the matching lock_token.
        Uses atomic Lua script on Redis.
        """
        lock_key = self._get_lock_key(conversation_id)

        # 1. Redis atomic renewal
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
                logger.warning("Redis renew_lock failed (%s).", exc)
                return False

        # 2. In-memory fallback renewal
        async with self._mem_guard:
            existing = self._in_memory_locks.get(lock_key)
            if existing is not None:
                token, _ = existing
                if token == lock_token:
                    self._in_memory_locks[lock_key] = (lock_token, time.time() + extension_seconds)
                    return True
            return False

    async def release_lock(
        self,
        conversation_id: str,
        lock_token: str,
    ) -> bool:
        """
        Atomically release lock ONLY IF caller is the current token owner.
        Prevents releasing a lock that expired and was re-acquired by another worker.
        """
        lock_key = self._get_lock_key(conversation_id)

        # 1. Redis atomic release
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
                logger.warning("Redis release_lock failed (%s).", exc)

        # 2. In-memory fallback release
        async with self._mem_guard:
            existing = self._in_memory_locks.get(lock_key)
            if existing is not None:
                token, _ = existing
                if token == lock_token:
                    del self._in_memory_locks[lock_key]
                    return True
            return False

    async def is_locked(
        self,
        conversation_id: str,
    ) -> bool:
        """
        Check whether a conversation currently holds ANY active lock (regardless of token owner).
        Used by crash recovery to avoid interfering with active long-running or newly acquired turns.
        """
        lock_key = self._get_lock_key(conversation_id)

        if hasattr(self._cache, "redis_client") and self._cache.redis_client is not None:
            try:
                return bool(self._cache.redis_client.exists(lock_key))
            except Exception as exc:
                logger.warning("Redis is_locked check failed (%s). Conservatively treating as locked.", exc)
                return True

        async with self._mem_guard:
            now = time.time()
            existing = self._in_memory_locks.get(lock_key)
            if existing is not None:
                _, expire_at = existing
                return expire_at > now
            return False

    async def is_lock_owned(
        self,
        conversation_id: str,
        lock_token: str,
    ) -> bool:
        """
        Verify if caller is still the authoritative owner of the lock.
        Crucial for stale worker protection before finalizing database records.
        """
        lock_key = self._get_lock_key(conversation_id)

        if hasattr(self._cache, "redis_client") and self._cache.redis_client is not None:
            try:
                current_holder = self._cache.redis_client.get(lock_key)
                if isinstance(current_holder, bytes):
                    current_holder = current_holder.decode("utf-8", errors="ignore")
                return current_holder == lock_token
            except Exception as exc:
                logger.warning("Redis is_lock_owned check failed (%s).", exc)
                return False

        async with self._mem_guard:
            now = time.time()
            existing = self._in_memory_locks.get(lock_key)
            if existing is not None:
                token, expire_at = existing
                return (token == lock_token) and (expire_at > now)
            return False

    def spawn_heartbeat_worker(
        self,
        conversation_id: str,
        lock_token: str,
        ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
        interval_seconds: float = DEFAULT_HEARTBEAT_INTERVAL,
    ) -> asyncio.Task:
        """
        Start an asynchronous background task that periodically extends the lock TTL.
        """
        async def _heartbeat_loop():
            try:
                while True:
                    await asyncio.sleep(interval_seconds)
                    renewed = await self.renew_lock(conversation_id, lock_token, ttl_seconds)
                    if not renewed:
                        logger.warning(
                            "Heartbeat failed to renew lock for conversation %s (token mismatch or lost). Terminating heartbeat.",
                            conversation_id,
                        )
                        break
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.error("Heartbeat error for conversation %s: %s", conversation_id, exc)

        return asyncio.create_task(_heartbeat_loop())


# Global singleton instance for application use
conversation_lock_manager = ConversationLockManager()
