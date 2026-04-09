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
    lock: bool = False,
    ttl_jitter: float = 0.1,
) -> Callable:
    """Decorator to cache function results in Redis.

    Automatically detects sync/async functions.

    Args:
        client: Redis client instance.
        key: Cache key template string (e.g. "user:{user_id}") or callable.
        ttl: TTL in seconds, string format ("2h30m"), or callable.
        serializer: Custom serializer (default: JsonSerializer).
        bypass: Callable returning True to skip cache for this call.
        lock: If True, use distributed lock on cache miss (anti-breakdown).
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
                return key(*bound_args.args, **bound_args.kwargs)
            return key.format(**bound_args.arguments)

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

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                if _should_bypass(args, kwargs):
                    result = await func(*args, **kwargs)
                    cache_key = _resolve_key(args, kwargs)
                    resolved_ttl = _resolve_ttl(args, kwargs)
                    encoded = pipeline.encode(result)
                    await client.setex(cache_key, resolved_ttl, encoded)
                    return result

                cache_key = _resolve_key(args, kwargs)
                raw = await client.get(cache_key)
                value = pipeline.decode(raw)
                if value is not _MISS:
                    return value

                result = await func(*args, **kwargs)
                resolved_ttl = _resolve_ttl(args, kwargs)
                encoded = pipeline.encode(result)
                await client.setex(cache_key, resolved_ttl, encoded)
                return result

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                if _should_bypass(args, kwargs):
                    result = func(*args, **kwargs)
                    cache_key = _resolve_key(args, kwargs)
                    resolved_ttl = _resolve_ttl(args, kwargs)
                    encoded = pipeline.encode(result)
                    client.setex(cache_key, resolved_ttl, encoded)
                    return result

                cache_key = _resolve_key(args, kwargs)
                raw = client.get(cache_key)
                value = pipeline.decode(raw)
                if value is not _MISS:
                    return value

                result = func(*args, **kwargs)
                resolved_ttl = _resolve_ttl(args, kwargs)
                encoded = pipeline.encode(result)
                client.setex(cache_key, resolved_ttl, encoded)
                return result

            return sync_wrapper

    return decorator
