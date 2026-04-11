from __future__ import annotations

import asyncio
import functools
import inspect
from typing import TYPE_CHECKING, Any

from redis_kit.cache._logic import _MISS, DataPipeline, apply_jitter, parse_ttl
from redis_kit.serializers.base import Serializer

if TYPE_CHECKING:
    from collections.abc import Callable

    import redis


def cached(
    client: redis.Redis,
    key: str | Callable[..., str],
    ttl: str | int | Callable[..., str | int],
    serializer: Serializer | None = None,
    bypass: Callable[..., bool] | None = None,
    prefix: str = "",
    ttl_jitter: float = 0.1,
) -> Callable:
    """Decorator to cache function results in Redis.

    Automatically detects sync/async functions.

    Note: Unlike ``Cache``, this decorator does not support ``FallbackPolicy``
    or hooks. Redis connection errors will propagate directly to the caller.
    Use ``Cache`` with ``remember()`` if you need resilience features.

    Args:
        client: Redis client instance.
        key: Cache key template string (e.g. "user:{user_id}") or callable.
        ttl: TTL in seconds, string format ("2h30m"), or callable.
        serializer: Custom serializer (default: JsonSerializer).
        bypass: Callable returning True to force-refresh the cache for this call.
            When bypass returns True, the cache read is skipped but the result
            is still written back to cache (force-refresh behavior, not skip).
        prefix: Optional key prefix prepended as "{prefix}:{key}".
        ttl_jitter: TTL jitter factor (0.1 = +/- 10%).
    """
    pipeline = DataPipeline(serializer)

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)
        sig = inspect.signature(func)

        def _resolve_key(args: tuple, kwargs: dict) -> str:
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            if callable(key):
                raw_key = key(*bound_args.args, **bound_args.kwargs)
            else:
                raw_key = key.format(**bound_args.arguments)
            return f"{prefix}:{raw_key}" if prefix else raw_key

        def _resolve_ttl(args: tuple, kwargs: dict) -> int:
            if callable(ttl):
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                raw = ttl(*bound_args.args, **bound_args.kwargs)
            else:
                raw = ttl
            seconds = parse_ttl(raw)
            return apply_jitter(seconds, ttl_jitter)

        def _should_bypass(args: tuple, kwargs: dict) -> bool:
            if bypass is None:
                return False
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            return bypass(*bound_args.args, **bound_args.kwargs)

        def _invalidate(*args: Any, **kwargs: Any) -> None:
            """Invalidate the cached result for the given arguments."""
            cache_key = _resolve_key(args, kwargs)
            client.delete(cache_key)

        async def _async_invalidate(*args: Any, **kwargs: Any) -> None:
            """Async invalidate the cached result for the given arguments."""
            cache_key = _resolve_key(args, kwargs)
            await client.delete(cache_key)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if _should_bypass(args, kwargs):
                    result = await func(*args, **kwargs)
                    cache_key = _resolve_key(args, kwargs)
                    resolved_ttl = _resolve_ttl(args, kwargs)
                    encoded = pipeline.encode(result)
                    if resolved_ttl > 0:
                        await client.setex(cache_key, resolved_ttl, encoded)
                    else:
                        await client.set(cache_key, encoded)
                    return result

                cache_key = _resolve_key(args, kwargs)
                raw = await client.get(cache_key)
                value = pipeline.decode(raw)
                if value is not _MISS:
                    return value

                result = await func(*args, **kwargs)
                resolved_ttl = _resolve_ttl(args, kwargs)
                encoded = pipeline.encode(result)
                if resolved_ttl > 0:
                    await client.setex(cache_key, resolved_ttl, encoded)
                else:
                    await client.set(cache_key, encoded)
                return result

            async_wrapper.invalidate = _async_invalidate  # type: ignore[attr-defined]
            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                if _should_bypass(args, kwargs):
                    result = func(*args, **kwargs)
                    cache_key = _resolve_key(args, kwargs)
                    resolved_ttl = _resolve_ttl(args, kwargs)
                    encoded = pipeline.encode(result)
                    if resolved_ttl > 0:
                        client.setex(cache_key, resolved_ttl, encoded)
                    else:
                        client.set(cache_key, encoded)
                    return result

                cache_key = _resolve_key(args, kwargs)
                raw = client.get(cache_key)
                value = pipeline.decode(raw)
                if value is not _MISS:
                    return value

                result = func(*args, **kwargs)
                resolved_ttl = _resolve_ttl(args, kwargs)
                encoded = pipeline.encode(result)
                if resolved_ttl > 0:
                    client.setex(cache_key, resolved_ttl, encoded)
                else:
                    client.set(cache_key, encoded)
                return result

            sync_wrapper.invalidate = _invalidate  # type: ignore[attr-defined]
            return sync_wrapper

    return decorator
