from __future__ import annotations

import math
from typing import TYPE_CHECKING

from redis_kit.ratelimit._lua import TOKEN_BUCKET_SCRIPT
from redis_kit.ratelimit._result import RateLimitResult

if TYPE_CHECKING:
    import redis.asyncio


class AsyncTokenBucketLimiter:
    """Async token bucket rate limiter backed by Redis + Lua script."""

    def __init__(
        self,
        client: redis.asyncio.Redis,
        prefix: str = "redis_kit:rl:tb",
        rate: float = 10.0,
        capacity: int = 50,
    ) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._client = client
        self._prefix = prefix
        self._rate = rate
        self._capacity = capacity
        self._script = self._client.register_script(TOKEN_BUCKET_SCRIPT)
        self._ttl = math.ceil(capacity / rate) * 2

    def _make_keys(self, key: str) -> tuple[str, str]:
        base = f"{self._prefix}:{key}"
        return f"{{{base}}}:tokens", f"{{{base}}}:ts"

    async def acquire(self, key: str, cost: int = 1) -> RateLimitResult:
        tokens_key, ts_key = self._make_keys(key)
        result = await self._script(
            keys=[tokens_key, ts_key],
            args=[self._rate, self._capacity, cost, self._ttl],
        )
        return RateLimitResult(
            allowed=bool(result[0]),
            limit=int(result[1]),
            remaining=int(result[2]),
            retry_after=int(result[3]) / 1000.0,
            reset_at=int(result[4]) / 1000.0,
        )

    async def reset(self, key: str) -> None:
        tokens_key, ts_key = self._make_keys(key)
        await self._client.delete(tokens_key, ts_key)
