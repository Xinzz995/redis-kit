from __future__ import annotations

import math
from typing import Any

from redis_kit.ratelimit._lua import SLIDING_WINDOW_SCRIPT, TOKEN_BUCKET_SCRIPT


class SlidingWindowBase:
    """Shared logic for sync and async SlidingWindowLimiter."""

    def __init__(
        self,
        client: Any,
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


class TokenBucketBase:
    """Shared logic for sync and async TokenBucketLimiter."""

    def __init__(
        self,
        client: Any,
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
