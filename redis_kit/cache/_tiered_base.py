from __future__ import annotations

from typing import Any

from redis_kit.cache.local import LRUCache


class TieredCacheBase:
    """Shared logic for sync and async TieredCache implementations."""

    def __init__(
        self,
        cache: Any,
        local_maxsize: int = 1000,
        local_ttl: float = 30.0,
        negative_ttl: float = 5.0,
    ) -> None:
        self._l1 = LRUCache(maxsize=local_maxsize, ttl=local_ttl)
        self._l2 = cache
        self._negative_ttl = negative_ttl
