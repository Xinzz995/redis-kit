from __future__ import annotations

from redis_kit.ratelimit._base import TokenBucketBase
from redis_kit.ratelimit._result import RateLimitResult


class AsyncTokenBucketLimiter(TokenBucketBase):
    """Async token bucket rate limiter backed by Redis + Lua script."""

    async def acquire(self, key: str, cost: int = 1) -> RateLimitResult:
        tokens_key, ts_key = self._make_keys(key)
        result = await self._script(
            keys=[tokens_key, ts_key],
            args=[self._rate, self._capacity, cost, self._ttl],
        )
        return RateLimitResult.from_lua(result)

    async def reset(self, key: str) -> None:
        tokens_key, ts_key = self._make_keys(key)
        await self._client.delete(tokens_key, ts_key)
