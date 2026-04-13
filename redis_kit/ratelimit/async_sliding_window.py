from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from redis_kit.ratelimit._base import SlidingWindowBase
from redis_kit.ratelimit._result import RateLimitResult

if TYPE_CHECKING:
    pass


class AsyncSlidingWindowLimiter(SlidingWindowBase):
    """Async sliding window rate limiter backed by Redis Sorted Set + Lua script."""

    async def acquire(self, key: str) -> RateLimitResult:
        full_key = self._make_key(key)
        member = uuid.uuid4().hex
        window_ms = self._window * 1000
        ttl_ms = window_ms + 1000

        result = await self._script(
            keys=[full_key],
            args=[self._limit, window_ms, member, ttl_ms],
        )
        return RateLimitResult.from_lua(result)

    async def reset(self, key: str) -> None:
        await self._client.delete(self._make_key(key))
