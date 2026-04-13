from __future__ import annotations

import asyncio
import functools
import inspect
import re
from collections.abc import Callable
from typing import Any

from redis_kit.exceptions import RateLimitExceeded
from redis_kit.ratelimit.async_sliding_window import AsyncSlidingWindowLimiter
from redis_kit.ratelimit.async_token_bucket import AsyncTokenBucketLimiter
from redis_kit.ratelimit.sliding_window import SlidingWindowLimiter
from redis_kit.ratelimit.token_bucket import TokenBucketLimiter

_TIME_UNITS = {
    "second": 1,
    "seconds": 1,
    "minute": 60,
    "minutes": 60,
    "hour": 3600,
    "hours": 3600,
    "day": 86400,
    "days": 86400,
}

_RATE_DSL_RE = re.compile(r"\s*(\d+)\s*/\s*(\w+)\s*")


def parse_rate_dsl(dsl: str) -> tuple[int, int]:
    """Parse '100/minute' -> (limit=100, window_seconds=60)."""
    match = _RATE_DSL_RE.fullmatch(dsl)
    if not match:
        raise ValueError(f"Invalid rate limit DSL: '{dsl}'")
    limit = int(match.group(1))
    unit = match.group(2).lower()
    if unit not in _TIME_UNITS:
        raise ValueError(f"Unknown time unit: '{unit}'")
    return limit, _TIME_UNITS[unit]


def rate_limit(
    client: Any,  # redis.Redis for sync functions, redis.asyncio.Redis for async functions
    key: str | Callable[..., str],
    limit: str,
    algorithm: str = "sliding_window",
    prefix: str = "redis_kit:rl",
) -> Callable:
    """Decorator to apply rate limiting to a function.

    Args:
        client: Redis client instance. Pass a ``redis.Redis`` (sync) client for
            synchronous functions and a ``redis.asyncio.Redis`` (async) client
            for async functions.  Passing a sync client to an async function
            will raise an error at runtime when the limiter tries to await the
            Redis commands.
        key: Key template string (e.g. "api:{user_id}") or callable.
        limit: Rate limit DSL string (e.g. "100/minute").
        algorithm: "token_bucket" or "sliding_window".
        prefix: Redis key prefix.
    """
    parsed_limit, window = parse_rate_dsl(limit)
    if algorithm not in {"token_bucket", "sliding_window"}:
        raise ValueError(f"Unknown algorithm: '{algorithm}'")

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)
        sig = inspect.signature(func)

        if algorithm == "token_bucket":
            if is_async:
                limiter = AsyncTokenBucketLimiter(
                    client,
                    prefix=prefix,
                    rate=parsed_limit / window,
                    capacity=parsed_limit,
                )
            else:
                limiter = TokenBucketLimiter(
                    client,
                    prefix=prefix,
                    rate=parsed_limit / window,
                    capacity=parsed_limit,
                )
        else:
            if is_async:
                limiter = AsyncSlidingWindowLimiter(
                    client,
                    prefix=prefix,
                    limit=parsed_limit,
                    window=window,
                )
            else:
                limiter = SlidingWindowLimiter(
                    client,
                    prefix=prefix,
                    limit=parsed_limit,
                    window=window,
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
