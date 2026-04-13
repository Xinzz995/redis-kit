from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any

from redis_kit.cache._logic import _MISS as _L2_MISS
from redis_kit.cache._logic import _NEGATIVE
from redis_kit.cache._tiered_base import TieredCacheBase
from redis_kit.cache.local import _MISS


class AsyncTieredCache(TieredCacheBase):
    """Async two-tier cache: L1 (local LRU) -> L2 (Redis AsyncCache)."""

    async def get(self, key: str) -> Any:
        local_val = self._l1.get(key)
        if local_val is _NEGATIVE:
            return None
        if local_val is not _MISS:
            return local_val
        l2_val = await self._l2._get_raw(key)
        if l2_val is not _L2_MISS:
            self._l1.set(key, l2_val)
            return l2_val
        self._l1.set(key, _NEGATIVE, ttl=self._negative_ttl)
        return None

    async def set(self, key: str, value: Any, ttl: str | int | None = None) -> None:
        await self._l2.set(key, value, ttl=ttl)
        self._l1.set(key, value)

    async def delete(self, key: str) -> None:
        self._l1.delete(key)
        await self._l2.delete(key)

    async def remember(self, key: str, factory: Callable[[], Any], ttl: str | int | None = None) -> Any:
        local_val = self._l1.get(key)
        if local_val is _NEGATIVE:
            pass
        elif local_val is not _MISS:
            return local_val
        l2_val = await self._l2._get_raw(key)
        if l2_val is not _L2_MISS:
            self._l1.set(key, l2_val)
            return l2_val
        result = factory()
        if asyncio.iscoroutine(result):
            result = await result
        value = result
        await self._l2.set(key, value, ttl=ttl)
        self._l1.set(key, value)
        return value

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        l2_keys: list[str] = []
        for key in keys:
            local_val = self._l1.get(key)
            if local_val is _NEGATIVE:
                result[key] = None
            elif local_val is not _MISS:
                result[key] = local_val
            else:
                l2_keys.append(key)
        if l2_keys:
            l2_result = await self._l2._get_many_raw(l2_keys)
            for key, value in l2_result.items():
                if value is not _L2_MISS:
                    self._l1.set(key, value)
                    result[key] = value
                else:
                    self._l1.set(key, _NEGATIVE, ttl=self._negative_ttl)
                    result[key] = None
        return result

    async def set_many(self, mapping: dict[str, Any], ttl: str | int | None = None) -> None:
        await self._l2.set_many(mapping, ttl=ttl)
        for key, value in mapping.items():
            self._l1.set(key, value)

    async def delete_pattern(self, pattern: str, batch_size: int = 100) -> int:
        self._l1.clear()
        return await self._l2.delete_pattern(pattern, batch_size=batch_size)

    async def iter_keys(self, pattern: str, batch_size: int = 100) -> AsyncIterator[str]:
        async for key in self._l2.iter_keys(pattern, batch_size=batch_size):
            yield key

    async def ttl(self, key: str) -> int:
        return await self._l2.ttl(key)

    async def pttl(self, key: str) -> int:
        return await self._l2.pttl(key)

    async def persist(self, key: str) -> None:
        await self._l2.persist(key)

    async def expire(self, key: str, seconds: int) -> None:
        await self._l2.expire(key, seconds)

    async def expire_at(self, key: str, when: datetime) -> None:
        await self._l2.expire_at(key, when)

    def invalidate_local(self, key: str) -> None:
        self._l1.delete(key)

    def clear_local(self) -> None:
        self._l1.clear()

    def bind(self, key: str) -> AsyncBoundTieredCache:
        return AsyncBoundTieredCache(self, key)

    @property
    def local_size(self) -> int:
        return self._l1.size


class AsyncBoundTieredCache:
    """AsyncTieredCache operations bound to a specific key."""

    def __init__(self, cache: AsyncTieredCache, key: str) -> None:
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
