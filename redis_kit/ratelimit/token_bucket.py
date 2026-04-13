from __future__ import annotations

from typing import TYPE_CHECKING

from redis_kit.ratelimit._base import TokenBucketBase
from redis_kit.ratelimit._result import RateLimitResult

if TYPE_CHECKING:
    pass


class TokenBucketLimiter(TokenBucketBase):
    """Token bucket rate limiter backed by Redis + Lua script."""

    def acquire(self, key: str, cost: int = 1) -> RateLimitResult:
        tokens_key, ts_key = self._make_keys(key)
        result = self._script(
            keys=[tokens_key, ts_key],
            args=[self._rate, self._capacity, cost, self._ttl],
        )
        return RateLimitResult.from_lua(result)

    def reset(self, key: str) -> None:
        tokens_key, ts_key = self._make_keys(key)
        self._client.delete(tokens_key, ts_key)
