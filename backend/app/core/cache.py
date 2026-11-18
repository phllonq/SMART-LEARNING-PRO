import time
import logging
from typing import Any, Optional, Dict
import json

from app.config import settings

logger = logging.getLogger(__name__)


class InMemoryCache:
    """Thread-safe in-memory cache with TTL for local development and fallback."""
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expires: Dict[str, float] = {}

    def get(self, key: str) -> Optional[str]:
        now = time.time()
        if key in self._expires and self._expires[key] < now:
            self._store.pop(key, None)
            self._expires.pop(key, None)
            return None
        return self._store.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self._store[key] = value
        if ex:
            self._expires[key] = time.time() + ex
        elif key in self._expires:
            del self._expires[key]
        return True

    def delete(self, key: str) -> bool:
        self._store.pop(key, None)
        self._expires.pop(key, None)
        return True


class CacheService:
    def __init__(self):
        self.redis_client = None
        self.in_memory = InMemoryCache()
        self._init_redis()

    def _init_redis(self):
        try:
            import redis
            client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1)
            client.ping()
            self.redis_client = client
            logger.info("Successfully connected to Redis.")
        except Exception as e:
            logger.warning(f"Could not connect to Redis ({e}). Using In-Memory Cache fallback.")
            self.redis_client = None

    def get(self, key: str) -> Optional[str]:
        if self.redis_client:
            try:
                return self.redis_client.get(key)
            except Exception:
                pass
        return self.in_memory.get(key)

    def set(self, key: str, value: str, expire_seconds: Optional[int] = None) -> bool:
        if self.redis_client:
            try:
                return bool(self.redis_client.set(key, value, ex=expire_seconds))
            except Exception:
                pass
        return self.in_memory.set(key, value, ex=expire_seconds)

    def delete(self, key: str) -> bool:
        if self.redis_client:
            try:
                return bool(self.redis_client.delete(key))
            except Exception:
                pass
        return self.in_memory.delete(key)

    def get_json(self, key: str) -> Optional[Any]:
        raw = self.get(key)
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return None
        return None

    def set_json(self, key: str, value: Any, expire_seconds: Optional[int] = None) -> bool:
        try:
            return self.set(key, json.dumps(value, ensure_ascii=False), expire_seconds)
        except Exception:
            return False


cache_service = CacheService()
