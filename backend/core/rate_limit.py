"""Replaceable fixed-window limiter with an optional Redis implementation."""

from __future__ import annotations

from collections import defaultdict, deque
import os
from threading import Lock
import time


class RateLimitExceeded(Exception):
    pass


class MemoryRateLimiter:
    def __init__(self):
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                raise RateLimitExceeded
            events.append(now)


class RedisRateLimiter:
    def __init__(self, url: str):
        import redis

        self.client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=1)

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        bucket = int(time.time()) // window_seconds
        redis_key = f"gf:rate:{key}:{bucket}"
        with self.client.pipeline() as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, window_seconds + 2)
            count, _ = pipe.execute()
        if int(count) > limit:
            raise RateLimitExceeded


def _build_limiter():
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        try:
            limiter = RedisRateLimiter(redis_url)
            limiter.client.ping()
            return limiter
        except Exception:
            pass
    return MemoryRateLimiter()


rate_limiter = _build_limiter()
