from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from typing import TYPE_CHECKING, Any, Literal

from redis_kit.cache._logic import _MISS, DataPipeline, apply_jitter, parse_ttl
from redis_kit.compressors.base import Compressor
from redis_kit.serializers.base import Serializer

_logger = logging.getLogger("redis_kit.cache")

if TYPE_CHECKING:
    from collections.abc import Callable

    import redis


def cached(
    client: redis.Redis,
    key: str | Callable[..., str],
    ttl: str | int | Callable[..., str | int],
    serializer: Serializer | None = None,
    compressor: Compressor | None = None,
    bypass: Callable[..., bool] | None = None,
    prefix: str = "",
    ttl_jitter: float = 0.1,
    on_error: Literal["raise", "execute"] = "raise",
) -> Callable:
    """Decorator to cache function results in Redis.

    Automatically detects sync/async functions.

    Args:
        client: Redis client instance.
        key: Cache key template string (e.g. "user:{user_id}") or callable.
        ttl: TTL in seconds, string format ("2h30m"), or callable.
        serializer: Custom serializer (default: JsonSerializer).
        compressor: Custom compressor (default: None = no compression).
        bypass: Callable returning True to force-refresh the cache for this call.
            When bypass returns True, the cache read is skipped but the result
            is still written back to cache (force-refresh behavior, not skip).
        prefix: Optional key prefix prepended as "{prefix}:{key}".
        ttl_jitter: TTL jitter factor (0.1 = +/- 10%).
        on_error: Error handling strategy for Redis failures.
            ``"raise"`` (default) propagates the error.
            ``"execute"`` skips the cache and executes the function directly.
    """
    if on_error not in ("raise", "execute"):
        raise ValueError(f"on_error must be 'raise' or 'execute', got {on_error!r}")
    pipeline = DataPipeline(serializer, compressor)

    def decorator(func: Callable) -> Callable:
        is_async = asyncio.iscoroutinefunction(func)
        sig = inspect.signature(func)

        def _bind(args: tuple, kwargs: dict) -> inspect.BoundArguments:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            return bound

        def _resolve_key(bound_args: inspect.BoundArguments) -> str:
            if callable(key):
                raw_key = key(*bound_args.args, **bound_args.kwargs)
            else:
                raw_key = key.format(**bound_args.arguments)
            return f"{prefix}:{raw_key}" if prefix else raw_key

        def _resolve_ttl(bound_args: inspect.BoundArguments) -> int:
            if callable(ttl):
                raw = ttl(*bound_args.args, **bound_args.kwargs)
            else:
                raw = ttl
            seconds = parse_ttl(raw)
            return apply_jitter(seconds, ttl_jitter)

        def _should_bypass(bound_args: inspect.BoundArguments) -> bool:
            if bypass is None:
                return False
            return bypass(*bound_args.args, **bound_args.kwargs)

        def _write_cache(cache_key: str, result: Any, resolved_ttl: int) -> None:
            encoded = pipeline.encode(result)
            if resolved_ttl > 0:
                client.setex(cache_key, resolved_ttl, encoded)
            else:
                client.set(cache_key, encoded)

        async def _async_write_cache(cache_key: str, result: Any, resolved_ttl: int) -> None:
            encoded = pipeline.encode(result)
            if resolved_ttl > 0:
                await client.setex(cache_key, resolved_ttl, encoded)
            else:
                await client.set(cache_key, encoded)

        def _invalidate(*args: Any, **kwargs: Any) -> None:
            """Invalidate the cached result for the given arguments."""
            client.delete(_resolve_key(_bind(args, kwargs)))

        async def _async_invalidate(*args: Any, **kwargs: Any) -> None:
            """Async invalidate the cached result for the given arguments."""
            await client.delete(_resolve_key(_bind(args, kwargs)))

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                bound_args = _bind(args, kwargs)
                try:
                    cache_key = _resolve_key(bound_args)
                except Exception:
                    if on_error == "execute":
                        _logger.debug("@cached key resolution failed, executing directly", exc_info=True)
                        return await func(*args, **kwargs)
                    raise

                if not _should_bypass(bound_args):
                    try:
                        value = pipeline.decode(await client.get(cache_key))
                        if value is not _MISS:
                            return value
                    except Exception:
                        if on_error == "execute":
                            _logger.debug("@cached read failed for '%s', executing directly", cache_key, exc_info=True)
                            return await func(*args, **kwargs)
                        raise

                result = await func(*args, **kwargs)
                try:
                    await _async_write_cache(cache_key, result, _resolve_ttl(bound_args))
                except Exception:
                    if on_error == "execute":
                        _logger.debug("@cached write failed for '%s', skipping", cache_key, exc_info=True)
                    else:
                        raise
                return result

            async_wrapper.invalidate = _async_invalidate  # type: ignore[attr-defined]
            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                bound_args = _bind(args, kwargs)
                try:
                    cache_key = _resolve_key(bound_args)
                except Exception:
                    if on_error == "execute":
                        _logger.debug("@cached key resolution failed, executing directly", exc_info=True)
                        return func(*args, **kwargs)
                    raise

                if not _should_bypass(bound_args):
                    try:
                        value = pipeline.decode(client.get(cache_key))
                        if value is not _MISS:
                            return value
                    except Exception:
                        if on_error == "execute":
                            _logger.debug("@cached read failed for '%s', executing directly", cache_key, exc_info=True)
                            return func(*args, **kwargs)
                        raise

                result = func(*args, **kwargs)
                try:
                    _write_cache(cache_key, result, _resolve_ttl(bound_args))
                except Exception:
                    if on_error == "execute":
                        _logger.debug("@cached write failed for '%s', skipping", cache_key, exc_info=True)
                    else:
                        raise
                return result

            sync_wrapper.invalidate = _invalidate  # type: ignore[attr-defined]
            return sync_wrapper

    return decorator
