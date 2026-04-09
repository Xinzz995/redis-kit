# Rate Limiter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add distributed rate limiter module with token bucket and sliding window algorithms, Lua-scripted atomicity, sync/async APIs, and `@rate_limit` decorator.

**Architecture:** Two limiter classes (TokenBucketLimiter, SlidingWindowLimiter) each backed by a Lua script for atomic Redis operations. Shared RateLimitResult dataclass. Decorator auto-detects sync/async functions.

**Tech Stack:** Python 3.11+, redis-py >= 7.4.0, Lua scripts, fakeredis[lua] for testing

---

## File Structure

```
redis_kit/ratelimit/
├── __init__.py                    # CREATE: Export all public classes
├── _lua.py                        # CREATE: Lua script constants
├── _result.py                     # CREATE: RateLimitResult dataclass
├── token_bucket.py                # CREATE: TokenBucketLimiter (sync)
├── async_token_bucket.py          # CREATE: AsyncTokenBucketLimiter
├── sliding_window.py              # CREATE: SlidingWindowLimiter (sync)
├── async_sliding_window.py        # CREATE: AsyncSlidingWindowLimiter
└── decorator.py                   # CREATE: @rate_limit decorator

redis_kit/exceptions.py            # MODIFY: Add RateLimitExceeded
redis_kit/__init__.py              # MODIFY: Export new types

tests/
├── test_ratelimit_token_bucket.py # CREATE
├── test_ratelimit_sliding_window.py # CREATE
└── test_ratelimit_decorator.py    # CREATE
```

---

## Task 1: RateLimitResult + RateLimitExceeded Exception

**Files:**
- Create: `redis_kit/ratelimit/_result.py`
- Modify: `redis_kit/exceptions.py`
- Create: `tests/test_ratelimit_token_bucket.py` (initial exception tests)

- [ ] **Step 1: Create RateLimitResult dataclass**

Create `redis_kit/ratelimit/_result.py`:
```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    """Rate limit check result, maps to standard HTTP rate limit headers."""

    allowed: bool
    limit: int
    remaining: int
    retry_after: float
    reset_at: float
```

- [ ] **Step 2: Add RateLimitExceeded exception**

Add to `redis_kit/exceptions.py` after `TopologyConstraintError`:

```python
# --- Rate Limit ---


class RateLimitExceeded(RedisKitError):
    """Rate limit exceeded."""

    def __init__(self, result: Any) -> None:
        self.result = result
        super().__init__(
            f"Rate limit exceeded: {result.remaining}/{result.limit}, "
            f"retry after {result.retry_after:.1f}s"
        )
```

- [ ] **Step 3: Create ratelimit package init**

Create `redis_kit/ratelimit/__init__.py`:
```python
from redis_kit.ratelimit._result import RateLimitResult

__all__ = ["RateLimitResult"]
```

- [ ] **Step 4: Write tests**

Create `tests/test_ratelimit_token_bucket.py` with initial tests:
```python
import pytest

from redis_kit.ratelimit._result import RateLimitResult
from redis_kit.exceptions import RateLimitExceeded, RedisKitError


class TestRateLimitResult:
    def test_fields(self):
        r = RateLimitResult(allowed=True, limit=100, remaining=99, retry_after=0.0, reset_at=1000.0)
        assert r.allowed is True
        assert r.limit == 100
        assert r.remaining == 99
        assert r.retry_after == 0.0
        assert r.reset_at == 1000.0

    def test_frozen(self):
        r = RateLimitResult(allowed=True, limit=100, remaining=99, retry_after=0.0, reset_at=1000.0)
        with pytest.raises(AttributeError):
            r.allowed = False


class TestRateLimitExceeded:
    def test_inherits_from_base(self):
        r = RateLimitResult(allowed=False, limit=100, remaining=0, retry_after=5.0, reset_at=1000.0)
        with pytest.raises(RedisKitError):
            raise RateLimitExceeded(r)

    def test_carries_result(self):
        r = RateLimitResult(allowed=False, limit=100, remaining=0, retry_after=5.0, reset_at=1000.0)
        exc = RateLimitExceeded(r)
        assert exc.result is r
        assert "retry after 5.0s" in str(exc)
```

- [ ] **Step 5: Run tests and commit**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_ratelimit_token_bucket.py -v`
Expected: All tests PASS

```bash
git add redis_kit/ratelimit/_result.py redis_kit/ratelimit/__init__.py redis_kit/exceptions.py tests/test_ratelimit_token_bucket.py
git commit -m "feat: add RateLimitResult dataclass and RateLimitExceeded exception"
```

---

## Task 2: Token Bucket Limiter (sync + async)

**Files:**
- Create: `redis_kit/ratelimit/_lua.py`
- Create: `redis_kit/ratelimit/token_bucket.py`
- Create: `redis_kit/ratelimit/async_token_bucket.py`
- Modify: `tests/test_ratelimit_token_bucket.py`

- [ ] **Step 1: Create Lua scripts**

Create `redis_kit/ratelimit/_lua.py`:
```python
"""Lua scripts for rate limiter algorithms."""

TOKEN_BUCKET_SCRIPT = """
local tokens_key = KEYS[1]
local ts_key = KEYS[2]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local last_tokens = tonumber(redis.call("get", tokens_key))
if last_tokens == nil then
    last_tokens = capacity
end

local last_ts = tonumber(redis.call("get", ts_key))
if last_ts == nil then
    last_ts = now
end

local delta = math.max(0, now - last_ts)
local filled = math.min(capacity, last_tokens + delta * rate)
local allowed = filled >= cost
local new_tokens = filled
local retry_after = 0
local reset_at = now + (capacity - filled) / rate

if allowed then
    new_tokens = filled - cost
else
    retry_after = (cost - filled) / rate
end

redis.call("setex", tokens_key, ttl, new_tokens)
redis.call("setex", ts_key, ttl, now)

return {allowed and 1 or 0, capacity, math.floor(new_tokens), math.floor(retry_after * 1000), math.floor(reset_at * 1000)}
"""

SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])

redis.call("zremrangebyscore", key, "-inf", now - window_ms)

local count = redis.call("zcard", key)

local allowed = count < limit
local remaining = math.max(0, limit - count - 1)
local retry_after = 0
local reset_at = now + window_ms

if allowed then
    redis.call("zadd", key, now, member)
    redis.call("pexpire", key, ttl)
else
    remaining = 0
    local oldest = redis.call("zrange", key, 0, 0, "WITHSCORES")
    if #oldest > 0 then
        retry_after = tonumber(oldest[2]) + window_ms - now
        reset_at = tonumber(oldest[2]) + window_ms
    end
end

return {allowed and 1 or 0, limit, remaining, math.floor(retry_after), math.floor(reset_at)}
"""
```

- [ ] **Step 2: Implement TokenBucketLimiter (sync)**

Create `redis_kit/ratelimit/token_bucket.py`:
```python
from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING

from redis_kit.ratelimit._lua import TOKEN_BUCKET_SCRIPT
from redis_kit.ratelimit._result import RateLimitResult

if TYPE_CHECKING:
    import redis


class TokenBucketLimiter:
    """Token bucket rate limiter backed by Redis + Lua script."""

    def __init__(
        self,
        client: redis.Redis,
        prefix: str = "redis_kit:rl:tb",
        rate: float = 10.0,
        capacity: int = 50,
    ) -> None:
        self._client = client
        self._prefix = prefix
        self._rate = rate
        self._capacity = capacity
        self._script = self._client.register_script(TOKEN_BUCKET_SCRIPT)
        self._ttl = math.ceil(capacity / rate) * 2

    def _make_keys(self, key: str) -> tuple[str, str]:
        base = f"{self._prefix}:{key}"
        return f"{{{base}}}:tokens", f"{{{base}}}:ts"

    def acquire(self, key: str, cost: int = 1) -> RateLimitResult:
        tokens_key, ts_key = self._make_keys(key)
        now = time.time()
        result = self._script(
            keys=[tokens_key, ts_key],
            args=[self._rate, self._capacity, now, cost, self._ttl],
        )
        return RateLimitResult(
            allowed=bool(result[0]),
            limit=int(result[1]),
            remaining=int(result[2]),
            retry_after=int(result[3]) / 1000.0,
            reset_at=int(result[4]) / 1000.0,
        )

    def reset(self, key: str) -> None:
        tokens_key, ts_key = self._make_keys(key)
        self._client.delete(tokens_key, ts_key)
```

- [ ] **Step 3: Implement AsyncTokenBucketLimiter**

Create `redis_kit/ratelimit/async_token_bucket.py`:
```python
from __future__ import annotations

import math
import time
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
        now = time.time()
        result = await self._script(
            keys=[tokens_key, ts_key],
            args=[self._rate, self._capacity, now, cost, self._ttl],
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
```

- [ ] **Step 4: Write token bucket tests**

Append to `tests/test_ratelimit_token_bucket.py`:
```python
import fakeredis

from redis_kit.ratelimit.token_bucket import TokenBucketLimiter


class TestTokenBucketLimiter:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_allows_within_capacity(self):
        limiter = TokenBucketLimiter(self.client, rate=10, capacity=5)
        result = limiter.acquire("user:1")
        assert result.allowed is True
        assert result.remaining >= 0
        assert result.limit == 5

    def test_exhausts_capacity(self):
        limiter = TokenBucketLimiter(self.client, rate=1, capacity=3)
        for _ in range(3):
            result = limiter.acquire("user:1")
            assert result.allowed is True
        result = limiter.acquire("user:1")
        assert result.allowed is False
        assert result.retry_after > 0

    def test_different_keys_independent(self):
        limiter = TokenBucketLimiter(self.client, rate=1, capacity=1)
        r1 = limiter.acquire("user:1")
        r2 = limiter.acquire("user:2")
        assert r1.allowed is True
        assert r2.allowed is True

    def test_reset_clears_state(self):
        limiter = TokenBucketLimiter(self.client, rate=1, capacity=1)
        limiter.acquire("user:1")
        limiter.acquire("user:1")  # exhausted
        limiter.reset("user:1")
        result = limiter.acquire("user:1")
        assert result.allowed is True

    def test_cost_parameter(self):
        limiter = TokenBucketLimiter(self.client, rate=1, capacity=5)
        result = limiter.acquire("user:1", cost=3)
        assert result.allowed is True
        assert result.remaining == 2
        result = limiter.acquire("user:1", cost=3)
        assert result.allowed is False

    def test_result_has_retry_after(self):
        limiter = TokenBucketLimiter(self.client, rate=1, capacity=1)
        limiter.acquire("user:1")
        result = limiter.acquire("user:1")
        assert result.allowed is False
        assert result.retry_after > 0
        assert result.reset_at > 0

    def test_hash_tag_in_keys(self):
        limiter = TokenBucketLimiter(self.client, prefix="rl")
        limiter.acquire("test")
        keys = [k.decode() for k in self.client.keys(b"*")]
        for k in keys:
            assert "{" in k and "}" in k
```

- [ ] **Step 5: Run tests and commit**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_ratelimit_token_bucket.py -v`
Expected: All tests PASS

```bash
git add redis_kit/ratelimit/_lua.py redis_kit/ratelimit/token_bucket.py redis_kit/ratelimit/async_token_bucket.py tests/test_ratelimit_token_bucket.py
git commit -m "feat: add TokenBucketLimiter with Lua-scripted atomic operations"
```

---

## Task 3: Sliding Window Limiter (sync + async)

**Files:**
- Create: `redis_kit/ratelimit/sliding_window.py`
- Create: `redis_kit/ratelimit/async_sliding_window.py`
- Create: `tests/test_ratelimit_sliding_window.py`

- [ ] **Step 1: Implement SlidingWindowLimiter (sync)**

Create `redis_kit/ratelimit/sliding_window.py`:
```python
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
```

- [ ] **Step 2: Implement AsyncSlidingWindowLimiter**

Create `redis_kit/ratelimit/async_sliding_window.py`:
```python
from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from redis_kit.ratelimit._lua import SLIDING_WINDOW_SCRIPT
from redis_kit.ratelimit._result import RateLimitResult

if TYPE_CHECKING:
    import redis.asyncio


class AsyncSlidingWindowLimiter:
    """Async sliding window rate limiter backed by Redis Sorted Set + Lua script."""

    def __init__(
        self,
        client: redis.asyncio.Redis,
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

    async def acquire(self, key: str) -> RateLimitResult:
        full_key = self._make_key(key)
        now_ms = int(time.time() * 1000)
        member = f"{now_ms}:{uuid.uuid4().hex[:8]}"
        window_ms = self._window * 1000
        ttl_ms = window_ms + 1000

        result = await self._script(
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

    async def reset(self, key: str) -> None:
        await self._client.delete(self._make_key(key))
```

- [ ] **Step 3: Write sliding window tests**

Create `tests/test_ratelimit_sliding_window.py`:
```python
import fakeredis

from redis_kit.ratelimit.sliding_window import SlidingWindowLimiter


class TestSlidingWindowLimiter:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_allows_within_limit(self):
        limiter = SlidingWindowLimiter(self.client, limit=5, window=60)
        result = limiter.acquire("user:1")
        assert result.allowed is True
        assert result.limit == 5
        assert result.remaining == 4

    def test_blocks_at_limit(self):
        limiter = SlidingWindowLimiter(self.client, limit=3, window=60)
        for _ in range(3):
            result = limiter.acquire("user:1")
            assert result.allowed is True
        result = limiter.acquire("user:1")
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0

    def test_different_keys_independent(self):
        limiter = SlidingWindowLimiter(self.client, limit=1, window=60)
        r1 = limiter.acquire("user:1")
        r2 = limiter.acquire("user:2")
        assert r1.allowed is True
        assert r2.allowed is True

    def test_reset_clears_state(self):
        limiter = SlidingWindowLimiter(self.client, limit=1, window=60)
        limiter.acquire("user:1")
        limiter.acquire("user:1")  # blocked
        limiter.reset("user:1")
        result = limiter.acquire("user:1")
        assert result.allowed is True

    def test_remaining_decrements(self):
        limiter = SlidingWindowLimiter(self.client, limit=5, window=60)
        results = [limiter.acquire("user:1") for _ in range(5)]
        assert results[0].remaining == 4
        assert results[1].remaining == 3
        assert results[2].remaining == 2
        assert results[3].remaining == 1
        assert results[4].remaining == 0

    def test_result_has_reset_at(self):
        limiter = SlidingWindowLimiter(self.client, limit=1, window=60)
        result = limiter.acquire("user:1")
        assert result.reset_at > 0
```

- [ ] **Step 4: Run tests and commit**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_ratelimit_sliding_window.py -v`
Expected: All tests PASS

```bash
git add redis_kit/ratelimit/sliding_window.py redis_kit/ratelimit/async_sliding_window.py tests/test_ratelimit_sliding_window.py
git commit -m "feat: add SlidingWindowLimiter with Sorted Set + Lua script"
```

---

## Task 4: @rate_limit Decorator

**Files:**
- Create: `redis_kit/ratelimit/decorator.py`
- Create: `tests/test_ratelimit_decorator.py`

- [ ] **Step 1: Implement DSL parser and decorator**

Create `redis_kit/ratelimit/decorator.py`:
```python
from __future__ import annotations

import asyncio
import functools
import inspect
import re
from collections.abc import Callable
from typing import Any, TYPE_CHECKING

from redis_kit.exceptions import RateLimitExceeded
from redis_kit.ratelimit._result import RateLimitResult
from redis_kit.ratelimit.sliding_window import SlidingWindowLimiter
from redis_kit.ratelimit.token_bucket import TokenBucketLimiter
from redis_kit.ratelimit.async_sliding_window import AsyncSlidingWindowLimiter
from redis_kit.ratelimit.async_token_bucket import AsyncTokenBucketLimiter

if TYPE_CHECKING:
    import redis


_TIME_UNITS = {
    "second": 1, "seconds": 1,
    "minute": 60, "minutes": 60,
    "hour": 3600, "hours": 3600,
    "day": 86400, "days": 86400,
}


def parse_rate_dsl(dsl: str) -> tuple[int, int]:
    """Parse '100/minute' -> (limit=100, window_seconds=60)."""
    match = re.match(r"(\d+)\s*/\s*(\w+)", dsl.strip())
    if not match:
        raise ValueError(f"Invalid rate limit DSL: '{dsl}'")
    limit = int(match.group(1))
    unit = match.group(2).lower()
    if unit not in _TIME_UNITS:
        raise ValueError(f"Unknown time unit: '{unit}'")
    return limit, _TIME_UNITS[unit]


def rate_limit(
    client: redis.Redis,
    key: str | Callable[..., str],
    limit: str,
    algorithm: str = "sliding_window",
    prefix: str = "redis_kit:rl",
) -> Callable:
    """Decorator to apply rate limiting to a function.

    Args:
        client: Redis client instance.
        key: Key template string (e.g. "api:{user_id}") or callable.
        limit: Rate limit DSL string (e.g. "100/minute").
        algorithm: "token_bucket" or "sliding_window".
        prefix: Redis key prefix.
    """
    parsed_limit, window = parse_rate_dsl(limit)

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)
        sig = inspect.signature(func)

        if algorithm == "token_bucket":
            if is_async:
                limiter = AsyncTokenBucketLimiter(
                    client, prefix=prefix, rate=parsed_limit / window, capacity=parsed_limit,
                )
            else:
                limiter = TokenBucketLimiter(
                    client, prefix=prefix, rate=parsed_limit / window, capacity=parsed_limit,
                )
        else:
            if is_async:
                limiter = AsyncSlidingWindowLimiter(
                    client, prefix=prefix, limit=parsed_limit, window=window,
                )
            else:
                limiter = SlidingWindowLimiter(
                    client, prefix=prefix, limit=parsed_limit, window=window,
                )

        def _resolve_key(args: tuple, kwargs: dict) -> str:
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            if callable(key):
                return key(*bound_args.args, **bound_args.kwargs)
            return key.format(**bound_args.arguments)

        if is_async:
            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                resolved_key = _resolve_key(args, kwargs)
                result = await limiter.acquire(resolved_key)
                if not result.allowed:
                    raise RateLimitExceeded(result)
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                resolved_key = _resolve_key(args, kwargs)
                result = limiter.acquire(resolved_key)
                if not result.allowed:
                    raise RateLimitExceeded(result)
                return func(*args, **kwargs)
            return sync_wrapper

    return decorator
```

- [ ] **Step 2: Write decorator tests**

Create `tests/test_ratelimit_decorator.py`:
```python
import pytest
import fakeredis

from redis_kit.ratelimit.decorator import rate_limit, parse_rate_dsl
from redis_kit.exceptions import RateLimitExceeded


class TestParseRateDsl:
    def test_per_minute(self):
        assert parse_rate_dsl("100/minute") == (100, 60)

    def test_per_second(self):
        assert parse_rate_dsl("10/second") == (10, 1)

    def test_per_hour(self):
        assert parse_rate_dsl("1000/hour") == (1000, 3600)

    def test_per_day(self):
        assert parse_rate_dsl("10000/day") == (10000, 86400)

    def test_with_spaces(self):
        assert parse_rate_dsl("100 / minute") == (100, 60)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_rate_dsl("invalid")

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError):
            parse_rate_dsl("100/fortnight")


class TestRateLimitDecorator:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_allows_within_limit(self):
        @rate_limit(self.client, key="test:{x}", limit="5/minute", algorithm="sliding_window")
        def fn(x: int) -> int:
            return x * 2

        assert fn(1) == 2

    def test_blocks_over_limit(self):
        @rate_limit(self.client, key="test:{x}", limit="2/minute", algorithm="sliding_window")
        def fn(x: int) -> int:
            return x

        fn(1)
        fn(1)
        with pytest.raises(RateLimitExceeded) as exc_info:
            fn(1)
        assert exc_info.value.result.allowed is False
        assert exc_info.value.result.retry_after > 0

    def test_different_keys_independent(self):
        @rate_limit(self.client, key="test:{x}", limit="1/minute", algorithm="sliding_window")
        def fn(x: int) -> int:
            return x

        assert fn(1) == 1
        assert fn(2) == 2

    def test_callable_key(self):
        @rate_limit(self.client, key=lambda uid: f"custom:{uid}", limit="5/minute", algorithm="sliding_window")
        def fn(uid: int) -> int:
            return uid

        assert fn(1) == 1

    def test_token_bucket_algorithm(self):
        @rate_limit(self.client, key="tb:{x}", limit="3/second", algorithm="token_bucket")
        def fn(x: int) -> int:
            return x

        assert fn(1) == 1

    @pytest.mark.asyncio
    async def test_async_function(self):
        @rate_limit(self.client, key="async:{x}", limit="5/minute", algorithm="sliding_window")
        async def fn(x: int) -> int:
            return x * 2

        result = await fn(1)
        assert result == 2
```

- [ ] **Step 3: Run tests and commit**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_ratelimit_decorator.py -v`
Expected: All tests PASS

```bash
git add redis_kit/ratelimit/decorator.py tests/test_ratelimit_decorator.py
git commit -m "feat: add @rate_limit decorator with DSL parsing and sync/async support"
```

---

## Task 5: Public API Exports & Final Integration

**Files:**
- Modify: `redis_kit/ratelimit/__init__.py`
- Modify: `redis_kit/__init__.py`

- [ ] **Step 1: Update ratelimit __init__.py**

Replace `redis_kit/ratelimit/__init__.py`:
```python
from redis_kit.ratelimit._result import RateLimitResult
from redis_kit.ratelimit.async_sliding_window import AsyncSlidingWindowLimiter
from redis_kit.ratelimit.async_token_bucket import AsyncTokenBucketLimiter
from redis_kit.ratelimit.decorator import rate_limit
from redis_kit.ratelimit.sliding_window import SlidingWindowLimiter
from redis_kit.ratelimit.token_bucket import TokenBucketLimiter

__all__ = [
    "AsyncSlidingWindowLimiter",
    "AsyncTokenBucketLimiter",
    "RateLimitResult",
    "SlidingWindowLimiter",
    "TokenBucketLimiter",
    "rate_limit",
]
```

- [ ] **Step 2: Update top-level __init__.py**

Add to `redis_kit/__init__.py`:

Import:
```python
from redis_kit.exceptions import FallbackPolicy, RateLimitExceeded, RedisKitError, TopologyConstraintError
from redis_kit.ratelimit import (
    AsyncSlidingWindowLimiter,
    AsyncTokenBucketLimiter,
    RateLimitResult,
    SlidingWindowLimiter,
    TokenBucketLimiter,
    rate_limit,
)
```

Add to `__all__`:
```python
    # Rate Limit
    "TokenBucketLimiter",
    "AsyncTokenBucketLimiter",
    "SlidingWindowLimiter",
    "AsyncSlidingWindowLimiter",
    "RateLimitResult",
    "RateLimitExceeded",
    "rate_limit",
```

- [ ] **Step 3: Verify imports**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run python -c "from redis_kit import TokenBucketLimiter, SlidingWindowLimiter, RateLimitResult, RateLimitExceeded, rate_limit; print('All rate limit imports OK')"`
Expected: "All rate limit imports OK"

- [ ] **Step 4: Run full test suite**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 5: Run linter + type check**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run ruff check . && uv run mypy redis_kit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add redis_kit/ratelimit/__init__.py redis_kit/__init__.py
git commit -m "feat: export rate limiter public API"
```

---

## Summary

| Task | Component | Steps |
|------|-----------|-------|
| 1 | RateLimitResult + RateLimitExceeded | 5 |
| 2 | TokenBucketLimiter (sync + async) | 5 |
| 3 | SlidingWindowLimiter (sync + async) | 4 |
| 4 | @rate_limit Decorator | 3 |
| 5 | Public API Exports | 6 |
| **Total** | | **23 steps** |
