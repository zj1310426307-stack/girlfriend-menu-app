"""Optional Redis cache with a no-failure local fallback boundary."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any


logger = logging.getLogger(__name__)

try:
    import redis
except ImportError:  # Local development remains fully functional without Redis.
    redis = None


class StateCache:
    """Store transient game state and presence when REDIS_URL is configured."""

    def __init__(self):
        self.url = os.getenv("REDIS_URL", "").strip()
        self.client = None
        self.last_attempt = 0.0
        self._connect()

    def _connect(self) -> None:
        """Connect lazily and retry after transient outages without blocking every call."""
        if not self.url or not redis or self.client:
            return
        now = time.monotonic()
        if now - self.last_attempt < 30:
            return
        self.last_attempt = now
        if self.url and redis:
            try:
                self.client = redis.Redis.from_url(self.url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)
                self.client.ping()
            except Exception as error:
                logger.warning("Redis unavailable; PostgreSQL/in-memory fallback active: %s", error)
                self.client = None

    @property
    def enabled(self) -> bool:
        """Return whether Redis passed startup connectivity validation."""
        self._connect()
        return self.client is not None

    def set_json(self, key: str, value: Any, ttl: int = 86400) -> None:
        """Best-effort JSON write that never interrupts a business transaction."""
        self._connect()
        if not self.client:
            return
        try:
            self.client.setex(key, ttl, json.dumps(value, ensure_ascii=False, default=str))
        except Exception as error:
            logger.warning("Redis write failed for %s: %s", key, error)
            self.client = None

    def get_json(self, key: str) -> Any | None:
        """Best-effort JSON read; malformed or unavailable entries behave as misses."""
        self._connect()
        if not self.client:
            return None
        try:
            raw = self.client.get(key)
            return json.loads(raw) if raw else None
        except Exception as error:
            logger.warning("Redis read failed for %s: %s", key, error)
            self.client = None
            return None

    def delete(self, key: str) -> None:
        """Best-effort removal for finished or revoked transient state."""
        if self.client:
            try:
                self.client.delete(key)
            except Exception:
                pass

    def set_game_state(self, room_code: str, value: dict, ttl: int = 7 * 86400) -> None:
        """Cache one recoverable room snapshot."""
        self.set_json(f"game:room:{room_code.upper()}", value, ttl)

    def get_game_state(self, room_code: str) -> dict | None:
        """Read one recoverable room snapshot."""
        return self.get_json(f"game:room:{room_code.upper()}")

    def touch_presence(self, user_code: str, ttl: int = 90) -> None:
        """Mark a device identity online with a short Redis TTL."""
        self.set_json(f"presence:{user_code}", {"online": True}, ttl)

    def is_online(self, user_code: str) -> bool:
        """Return current Redis presence; false when Redis is disabled."""
        return bool(self.get_json(f"presence:{user_code}"))


state_cache = StateCache()
