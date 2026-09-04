"""
Session store with TTL and per-user/per-channel conversation memory.

Two backends are supported transparently:

* **Redis** - used automatically when ``REDIS_URL`` is configured. Keys expire
  via Redis native TTL so nothing leaks.
* **In-memory** - a thread-safe dict used as a fallback for local development.
  Expired entries are purged lazily on access and by an explicit ``cleanup()``
  call, so sessions never leak here either.

A session is keyed by ``{channel}:{user_id}`` which means the same person is
tracked independently on WhatsApp, Email and the Web Form.
"""

import json
import threading
import time
from typing import Any, Dict, Optional

from . import config
from .logger import get_logger

logger = get_logger("session")


def _empty_session() -> Dict[str, Any]:
    return {
        "current_itinerary": None,
        "flights_data": [],
        "hotels_data": [],
        "is_human_takeover": False,
        "history": [],  # list of {"role": "user"|"assistant", "text": str, "ts": float}
    }


def _make_key(channel: str, user_id: str) -> str:
    return f"travel_session:{channel}:{user_id}"


class _MemoryBackend:
    """Thread-safe in-memory TTL store."""

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            exp = self._expiry.get(key)
            if exp is not None and exp < time.time():
                # expired -> drop
                self._data.pop(key, None)
                self._expiry.pop(key, None)
                return None
            value = self._data.get(key)
            return json.loads(value) if value is not None else None

    def set(self, key: str, value: Dict[str, Any], ttl: int) -> None:
        with self._lock:
            self._data[key] = json.dumps(value, ensure_ascii=False)
            self._expiry[key] = time.time() + ttl

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)
            self._expiry.pop(key, None)

    def cleanup(self) -> int:
        now = time.time()
        removed = 0
        with self._lock:
            for key in [k for k, exp in self._expiry.items() if exp < now]:
                self._data.pop(key, None)
                self._expiry.pop(key, None)
                removed += 1
        return removed


class _RedisBackend:
    """Redis-backed store using native key expiry."""

    def __init__(self, url: str) -> None:
        import redis  # imported lazily so redis is optional

        self._client = redis.Redis.from_url(url, decode_responses=True)
        # Fail fast if the URL is unreachable.
        self._client.ping()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        data = self._client.get(key)
        return json.loads(data) if data else None

    def set(self, key: str, value: Dict[str, Any], ttl: int) -> None:
        self._client.setex(key, ttl, json.dumps(value, ensure_ascii=False))

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def cleanup(self) -> int:
        # Redis handles expiry natively.
        return 0


class SessionManager:
    """High-level API used by the agent and channels."""

    def __init__(self) -> None:
        self._ttl = config.SESSION_TTL_SECONDS
        self._backend: Any
        if config.REDIS_URL:
            try:
                self._backend = _RedisBackend(config.REDIS_URL)
                logger.info("Session store: Redis backend active")
            except Exception as exc:
                logger.warning("Redis unavailable (%s) - falling back to in-memory store", exc)
                self._backend = _MemoryBackend()
        else:
            self._backend = _MemoryBackend()
            logger.info("Session store: in-memory backend active (no REDIS_URL)")

    def get(self, channel: str, user_id: str) -> Dict[str, Any]:
        key = _make_key(channel, user_id)
        try:
            data = self._backend.get(key)
        except Exception as exc:
            logger.error("Session get failed for %s: %s", key, exc)
            data = None
        return data if data is not None else _empty_session()

    def save(self, channel: str, user_id: str, session: Dict[str, Any]) -> None:
        key = _make_key(channel, user_id)
        # Keep conversation history bounded to avoid unbounded growth.
        history = session.get("history", [])
        if len(history) > config.MAX_HISTORY_MESSAGES:
            session["history"] = history[-config.MAX_HISTORY_MESSAGES :]
        try:
            self._backend.set(key, session, self._ttl)
        except Exception as exc:
            logger.error("Session save failed for %s: %s", key, exc)

    def append_history(self, session: Dict[str, Any], role: str, text: str) -> None:
        session.setdefault("history", []).append({"role": role, "text": text, "ts": time.time()})

    def delete(self, channel: str, user_id: str) -> None:
        try:
            self._backend.delete(_make_key(channel, user_id))
        except Exception as exc:
            logger.error("Session delete failed: %s", exc)

    def cleanup(self) -> int:
        try:
            return self._backend.cleanup()
        except Exception as exc:
            logger.error("Session cleanup failed: %s", exc)
            return 0


# Shared singleton used across all channels.
session_manager = SessionManager()
