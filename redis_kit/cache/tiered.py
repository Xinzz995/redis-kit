from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

from redis_kit.cache._logic import _MISS as _L2_MISS
from redis_kit.cache.cache import Cache
from redis_kit.cache.local import _MISS, LRUCache

_NEGATIVE = object()


class TieredCache:
    """Two-tier cache: L1 (local LRU) -> L2 (Redis Cache)."""

    def __init__(
        self,
        cache: Cache,
        local_maxsize: int = 1000,
        local_ttl: float = 30.0,
        negative_ttl: float = 5.0,
    ) -> None:
        self._l1 = LRUCache(maxsize=local_maxsize, ttl=local_ttl)
        self._l2 = cache
        self._negative_ttl = negative_ttl

    def get(self, key: str) -> Any:
        local_val = self._l1.get(key)
        if local_val is _NEGATIVE:
            return None
        if local_val is not _MISS:
            return local_val
        l2_val = self._l2._get_raw(key)
        if l2_val is not _L2_MISS:
            self._l1.set(key, l2_val)
            return l2_val
        self._l1.set(key, _NEGATIVE, ttl=self._negative_ttl)
        return None

    def set(self, key: str, value: Any, ttl: str | int | None = None) -> None:
        self._l2.set(key, value, ttl=ttl)
        self._l1.set(key, value)

    def delete(self, key: str) -> None:
        self._l1.delete(key)
        self._l2.delete(key)

    def remember(self, key: str, factory: Callable[[], Any], ttl: str | int | None = None) -> Any:
        local_val = self._l1.get(key)
        if local_val is _NEGATIVE:
            pass  # Fall through to L2/factory
        elif local_val is not _MISS:
            return local_val
        l2_val = self._l2._get_raw(key)
        if l2_val is not _L2_MISS:
            self._l1.set(key, l2_val)
            return l2_val
        value = factory()
        self._l2.set(key, value, ttl=ttl)
        self._l1.set(key, value)
        return value

    def get_many(self, keys: list[str]) -> dict[str, Any]:
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
            l2_result = self._l2.get_many(l2_keys)
            for key, value in l2_result.items():
                if value is not None:
                    self._l1.set(key, value)
                else:
                    self._l1.set(key, _NEGATIVE, ttl=self._negative_ttl)
                result[key] = value
        return result

    def set_many(self, mapping: dict[str, Any], ttl: str | int | None = None) -> None:
        self._l2.set_many(mapping, ttl=ttl)
        for key, value in mapping.items():
            self._l1.set(key, value)

    def delete_pattern(self, pattern: str, batch_size: int = 100) -> int:
        self._l1.clear()
        return self._l2.delete_pattern(pattern, batch_size=batch_size)

    def iter_keys(self, pattern: str, batch_size: int = 100) -> Iterator[str]:
        return self._l2.iter_keys(pattern, batch_size=batch_size)

    def ttl(self, key: str) -> int:
        return self._l2.ttl(key)

    def pttl(self, key: str) -> int:
        return self._l2.pttl(key)

    def persist(self, key: str) -> None:
        self._l2.persist(key)

    def expire(self, key: str, seconds: int) -> None:
        self._l2.expire(key, seconds)

    def expire_at(self, key: str, when: datetime) -> None:
        self._l2.expire_at(key, when)

    def invalidate_local(self, key: str) -> None:
        self._l1.delete(key)

    def clear_local(self) -> None:
        self._l1.clear()

    def bind(self, key: str) -> BoundTieredCache:
        return BoundTieredCache(self, key)

    @property
    def local_size(self) -> int:
        return self._l1.size


class BoundTieredCache:
    """TieredCache operations bound to a specific key."""

    def __init__(self, cache: TieredCache, key: str) -> None:
        self._cache = cache
        self._key = key

    def get(self) -> Any:
        return self._cache.get(self._key)

    def set(self, value: Any, ttl: str | int | None = None) -> None:
        self._cache.set(self._key, value, ttl=ttl)

    def delete(self) -> None:
        self._cache.delete(self._key)

    def ttl(self) -> int:
        return self._cache.ttl(self._key)
