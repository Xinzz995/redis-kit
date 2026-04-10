from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from typing import Any

from redis_kit.cache.async_cache import AsyncCache
from redis_kit.cache.local import _MISS, LRUCache

_NEGATIVE = object()


class AsyncTieredCache:
    """Async two-tier cache: L1 (local LRU) -> L2 (Redis AsyncCache)."""

    def __init__(
        self,
        cache: AsyncCache,
        local_maxsize: int = 1000,
        local_ttl: float = 30.0,
        negative_ttl: float = 5.0,
    ) -> None:
        self._l1 = LRUCache(maxsize=local_maxsize, ttl=local_ttl)
        self._l2 = cache
        self._negative_ttl = negative_ttl

    async def get(self, key: str) -> Any:
        local_val = self._l1.get(key)
        if local_val is _NEGATIVE:
            return None
        if local_val is not _MISS:
            return local_val
        value = await self._l2.get(key)
        if value is not None:
            self._l1.set(key, value)
            return value
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
        value = await self._l2.get(key)
        if value is not None:
            self._l1.set(key, value)
            return value
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
            l2_result = await self._l2.get_many(l2_keys)
            for key, value in l2_result.items():
                if value is not None:
                    self._l1.set(key, value)
                else:
                    self._l1.set(key, _NEGATIVE, ttl=self._negative_ttl)
                result[key] = value
        return result

    async def set_many(self, mapping: dict[str, Any], ttl: str | int | None = None) -> None:
        await self._l2.set_many(mapping, ttl=ttl)
        for key, value in mapping.items():
            self._l1.set(key, value)

    async def delete_pattern(self, pattern: str, batch_size: int = 100) -> int:
        self._l1.clear()
        return await self._l2.delete_pattern(pattern, batch_size=batch_size)

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

    @property
    def local_size(self) -> int:
        return self._l1.size
