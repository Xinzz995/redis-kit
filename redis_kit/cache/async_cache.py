from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

from redis_kit.cache._base import CacheBase
from redis_kit.cache._logic import _MISS

if TYPE_CHECKING:
    from collections.abc import Callable


class AsyncBoundCache:
    """Async cache operations bound to a specific key."""

    def __init__(self, cache: AsyncCache, key: str) -> None:
        self._cache = cache
        self._key = key

    async def get(self) -> Any:
        return await self._cache.get(self._key)

    async def set(self, value: Any, ttl: str | int | None = None) -> None:
        await self._cache.set(self._key, value, ttl=ttl)

    async def delete(self) -> None:
        await self._cache.delete(self._key)

    async def ttl(self) -> int:
        return await self._cache.ttl(self._key)

    async def pttl(self) -> int:
        return await self._cache.pttl(self._key)

    async def persist(self) -> None:
        await self._cache.persist(self._key)

    async def expire(self, seconds: int) -> None:
        await self._cache.expire(self._key, seconds)

    async def expire_at(self, when: datetime) -> None:
        await self._cache.expire_at(self._key, when)


class AsyncCache(CacheBase):
    """Async Redis cache with serialization, compression, TTL jitter, and fallback."""

    async def _handle_fallback(self, error: Exception, command: str, key: str, default: Any = None) -> Any:
        """Apply FallbackPolicy after hooks.on_error() has been called."""
        result = self._apply_fallback_policy(error, command, key, default)
        if inspect.isawaitable(result):
            return await result
        return result

    async def _get_raw(self, key: str) -> Any:
        """Get raw value, returning _MISS sentinel for cache miss.

        This is an internal API used by AsyncTieredCache. Returns ``_MISS``
        (from ``redis_kit.cache._logic``) when the key is not found.
        """
        full_key = self._make_key(key)
        self._notify_hooks("before", "GET", key, args=())
        start = time.monotonic()
        try:
            raw = await self._client.get(full_key)
        except Exception as e:
            self._notify_hooks("error", "GET", key, error=e)
            return await self._handle_fallback(e, "GET", key, default=_MISS)
        duration = (time.monotonic() - start) * 1000
        value = self._pipeline.decode(raw)
        self._notify_hooks("after", "GET", key, result=value if value is not _MISS else None, duration_ms=duration)
        return value

    async def get(self, key: str) -> Any:
        value = await self._get_raw(key)
        return None if value is _MISS else value

    async def set(self, key: str, value: Any, ttl: str | int | None = None) -> None:
        full_key = self._make_key(key)
        encoded = self._pipeline.encode(value)
        resolved_ttl = self._resolve_ttl(ttl)
        self._notify_hooks("before", "SET", key, args=(value, ttl))
        start = time.monotonic()
        try:
            if resolved_ttl is not None and resolved_ttl > 0:
                await self._client.setex(full_key, resolved_ttl, encoded)
            else:
                await self._client.set(full_key, encoded)
        except Exception as e:
            self._notify_hooks("error", "SET", key, error=e)
            await self._handle_fallback(e, "SET", key)
            return
        duration = (time.monotonic() - start) * 1000
        self._notify_hooks("after", "SET", key, result=None, duration_ms=duration)

    async def delete(self, key: str) -> None:
        self._notify_hooks("before", "DELETE", key, args=())
        start = time.monotonic()
        try:
            await self._client.delete(self._make_key(key))
        except Exception as e:
            self._notify_hooks("error", "DELETE", key, error=e)
            await self._handle_fallback(e, "DELETE", key)
            return
        duration = (time.monotonic() - start) * 1000
        self._notify_hooks("after", "DELETE", key, result=None, duration_ms=duration)

    async def ttl(self, key: str) -> int:
        return await self._client.ttl(self._make_key(key))

    async def pttl(self, key: str) -> int:
        return await self._client.pttl(self._make_key(key))

    async def persist(self, key: str) -> None:
        await self._client.persist(self._make_key(key))

    async def expire(self, key: str, seconds: int) -> None:
        await self._client.expire(self._make_key(key), seconds)

    async def expire_at(self, key: str, when: datetime) -> None:
        await self._client.expireat(self._make_key(key), when)

    async def remember(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: str | int | None = None,
    ) -> Any:
        """Get cached value or compute via factory and cache the result.

        .. warning::

            This method does not protect against cache stampede (thundering herd).
            Under high concurrency, multiple requests may invoke ``factory()``
            simultaneously on cache miss. Use ``AsyncLock`` to guard expensive
            factories if this is a concern.
        """
        value = await self._get_raw(key)
        if value is not _MISS:
            return value
        result = factory()
        if asyncio.iscoroutine(result):
            result = await result
        value = result
        await self.set(key, value, ttl=ttl)
        return value

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        keys_str = ",".join(keys)
        self._notify_hooks("before", "GET_MANY", keys_str, args=(keys,))
        start = time.monotonic()
        try:
            raw_result = await self._get_many_raw(keys)
        except Exception as e:
            self._notify_hooks("error", "GET_MANY", keys_str, error=e)
            return await self._handle_fallback(e, "GET_MANY", keys_str, default={k: None for k in keys})
        duration = (time.monotonic() - start) * 1000
        result = {k: (v if v is not _MISS else None) for k, v in raw_result.items()}
        self._notify_hooks("after", "GET_MANY", keys_str, result=result, duration_ms=duration)
        return result

    async def _get_many_raw(self, keys: list[str]) -> dict[str, Any]:
        """Get many raw values, returning _MISS sentinel for cache misses.

        This is an internal API used by AsyncTieredCache.
        """
        if not keys:
            return {}
        full_keys = [self._make_key(k) for k in keys]
        if self._is_cluster:
            pipe = self._client.pipeline(transaction=False)
            for k in full_keys:
                pipe.get(k)
            raw_values = await pipe.execute()
        else:
            raw_values = await self._client.mget(full_keys)
        result = {}
        for key, raw in zip(keys, raw_values):
            result[key] = self._pipeline.decode(raw)
        return result

    async def set_many(self, mapping: dict[str, Any], ttl: str | int | None = None) -> None:
        keys_str = ",".join(mapping.keys())
        self._notify_hooks("before", "SET_MANY", keys_str, args=(mapping, ttl))
        start = time.monotonic()
        try:
            pipe = self._client.pipeline(transaction=False)
            for key, value in mapping.items():
                full_key = self._make_key(key)
                encoded = self._pipeline.encode(value)
                resolved_ttl = self._resolve_ttl(ttl)
                if resolved_ttl is not None and resolved_ttl > 0:
                    pipe.setex(full_key, resolved_ttl, encoded)
                else:
                    pipe.set(full_key, encoded)
            await pipe.execute()
        except Exception as e:
            self._notify_hooks("error", "SET_MANY", keys_str, error=e)
            await self._handle_fallback(e, "SET_MANY", keys_str)
            return
        duration = (time.monotonic() - start) * 1000
        self._notify_hooks("after", "SET_MANY", keys_str, result=None, duration_ms=duration)

    async def _flush_delete_batch(self, batch: list[bytes | str]) -> None:
        if self._is_cluster:
            pipe = self._client.pipeline(transaction=False)
            for k in batch:
                pipe.delete(k)
            await pipe.execute()
        else:
            await self._client.delete(*batch)

    async def delete_pattern(self, pattern: str, batch_size: int = 100) -> int:
        full_pattern = self._make_key(pattern)
        self._notify_hooks("before", "DELETE_PATTERN", pattern, args=(pattern,))
        start = time.monotonic()
        try:
            count = 0
            batch: list[bytes | str] = []
            async for key in self._client.scan_iter(match=full_pattern, count=batch_size):
                batch.append(key)
                if len(batch) >= batch_size:
                    await self._flush_delete_batch(batch)
                    count += len(batch)
                    batch = []
            if batch:
                await self._flush_delete_batch(batch)
                count += len(batch)
        except Exception as e:
            self._notify_hooks("error", "DELETE_PATTERN", pattern, error=e)
            raise
        duration = (time.monotonic() - start) * 1000
        self._notify_hooks("after", "DELETE_PATTERN", pattern, result=count, duration_ms=duration)
        return count

    async def iter_keys(self, pattern: str, batch_size: int = 100) -> AsyncIterator[str]:
        full_pattern = self._make_key(pattern)
        prefix_len = len(self._prefix) + 1 if self._prefix else 0
        async for key in self._client.scan_iter(match=full_pattern, count=batch_size):
            decoded = key.decode() if isinstance(key, bytes) else key
            yield decoded[prefix_len:] if prefix_len else decoded

    def bind(self, key: str) -> AsyncBoundCache:
        return AsyncBoundCache(self, key)
