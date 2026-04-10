from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

from redis_kit.cache._logic import _MISS  # noqa: F401 — re-exported for tiered caches


class LRUCache:
    """Thread-safe LRU cache with per-entry TTL."""

    def __init__(self, maxsize: int = 1000, ttl: float = 30.0) -> None:
        self._maxsize = maxsize
        self._default_ttl = ttl
        self._data: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        """Get value. Returns _MISS sentinel if expired or not found."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return _MISS
            value, expire_at = entry
            if time.monotonic() > expire_at:
                del self._data[key]
                return _MISS
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set value. Evicts oldest entries when maxsize exceeded."""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expire_at = time.monotonic() + effective_ttl
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (value, expire_at)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._data)
