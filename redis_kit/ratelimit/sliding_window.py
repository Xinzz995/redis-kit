from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from redis_kit.ratelimit._lua import SLIDING_WINDOW_SCRIPT
from redis_kit.ratelimit._result import RateLimitResult

if TYPE_CHECKING:
    import redis


class SlidingWindowLimiter:
    """Sliding window rate limiter backed by Redis Sorted Set + Lua script."""

    def __init__(
        self,
        client: redis.Redis,
        prefix: str = "redis_kit:rl:sw",
        limit: int = 100,
        window: int = 60,
    ) -> None:
        self._client = client
        self._prefix = prefix
        self._limit = limit
        self._window = window
        self._script = self._client.register_script(SLIDING_WINDOW_SCRIPT)

    def _make_key(self, key: str) -> str:
        return f"{self._prefix}:{key}"

    def acquire(self, key: str) -> RateLimitResult:
        full_key = self._make_key(key)
        now_ms = int(time.time() * 1000)
        member = f"{now_ms}:{uuid.uuid4().hex[:8]}"
        window_ms = self._window * 1000
        ttl_ms = window_ms + 1000

        result = self._script(
            keys=[full_key],
            args=[self._limit, window_ms, now_ms, member, ttl_ms],
        )
        return RateLimitResult(
            allowed=bool(result[0]),
            limit=int(result[1]),
            remaining=int(result[2]),
            retry_after=int(result[3]) / 1000.0,
            reset_at=int(result[4]) / 1000.0,
        )

    def reset(self, key: str) -> None:
        self._client.delete(self._make_key(key))
