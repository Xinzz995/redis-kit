# Tiered Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two-tier cache (L1 local LRU + L2 Redis Cache) with read-through backfill, negative caching, and write-through semantics.

**Architecture:** `LRUCache` (thread-safe OrderedDict + TTL) as L1, existing `Cache`/`AsyncCache` as L2. `TieredCache` wraps both with transparent L1→L2 read path and write-through.

**Tech Stack:** Python 3.11+, threading.Lock, OrderedDict, fakeredis for testing

---

## File Structure

```
redis_kit/cache/
├── local.py              # CREATE: LRUCache
├── tiered.py             # CREATE: TieredCache (sync)
├── async_tiered.py       # CREATE: AsyncTieredCache

tests/
├── test_lru_cache.py     # CREATE
├── test_tiered_cache.py  # CREATE
```

---

## Task 1: LRUCache — Thread-safe Local Cache

**Files:**
- Create: `redis_kit/cache/local.py`
- Create: `tests/test_lru_cache.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_lru_cache.py`:
```python
import time

from redis_kit.cache.local import LRUCache, _MISS


class TestLRUCacheBasic:
    def test_get_miss(self):
        cache = LRUCache(maxsize=10, ttl=60)
        assert cache.get("nonexistent") is _MISS

    def test_set_and_get(self):
        cache = LRUCache(maxsize=10, ttl=60)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_set_none_value(self):
        cache = LRUCache(maxsize=10, ttl=60)
        cache.set("key", None)
        assert cache.get("key") is None

    def test_delete(self):
        cache = LRUCache(maxsize=10, ttl=60)
        cache.set("key", "value")
        cache.delete("key")
        assert cache.get("key") is _MISS

    def test_delete_nonexistent(self):
        cache = LRUCache(maxsize=10, ttl=60)
        cache.delete("nonexistent")  # Should not raise

    def test_clear(self):
        cache = LRUCache(maxsize=10, ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.size == 0
        assert cache.get("a") is _MISS

    def test_size(self):
        cache = LRUCache(maxsize=10, ttl=60)
        assert cache.size == 0
        cache.set("a", 1)
        assert cache.size == 1
        cache.set("b", 2)
        assert cache.size == 2


class TestLRUCacheEviction:
    def test_evicts_oldest_when_full(self):
        cache = LRUCache(maxsize=3, ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict "a"
        assert cache.get("a") is _MISS
        assert cache.get("b") == 2
        assert cache.get("d") == 4

    def test_access_refreshes_order(self):
        cache = LRUCache(maxsize=3, ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # Touch "a", now "b" is oldest
        cache.set("d", 4)  # Should evict "b"
        assert cache.get("a") == 1
        assert cache.get("b") is _MISS

    def test_overwrite_refreshes_order(self):
        cache = LRUCache(maxsize=3, ttl=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("a", 10)  # Overwrite "a", now "b" is oldest
        cache.set("d", 4)   # Should evict "b"
        assert cache.get("a") == 10
        assert cache.get("b") is _MISS


class TestLRUCacheTTL:
    def test_expired_entry_returns_miss(self):
        cache = LRUCache(maxsize=10, ttl=0.05)
        cache.set("key", "value")
        time.sleep(0.1)
        assert cache.get("key") is _MISS

    def test_custom_ttl_per_entry(self):
        cache = LRUCache(maxsize=10, ttl=60)
        cache.set("short", "val", ttl=0.05)
        cache.set("long", "val", ttl=60)
        time.sleep(0.1)
        assert cache.get("short") is _MISS
        assert cache.get("long") == "val"

    def test_non_expired_entry_returns_value(self):
        cache = LRUCache(maxsize=10, ttl=60)
        cache.set("key", "value")
        assert cache.get("key") == "value"
```

- [ ] **Step 2: Implement LRUCache**

Create `redis_kit/cache/local.py`:
```python
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

_MISS = object()


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
        return len(self._data)
```

- [ ] **Step 3: Run tests and commit**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_lru_cache.py -v`
Expected: All tests PASS

```bash
git add redis_kit/cache/local.py tests/test_lru_cache.py
git commit -m "feat: add LRUCache — thread-safe local cache with TTL and LRU eviction"
```

---

## Task 2: TieredCache (sync)

**Files:**
- Create: `redis_kit/cache/tiered.py`
- Create: `tests/test_tiered_cache.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tiered_cache.py`:
```python
import fakeredis

from redis_kit.cache.cache import Cache
from redis_kit.cache.tiered import TieredCache


class TestTieredCacheGet:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)
        self.l2 = Cache(self.client, prefix="test", ttl_jitter=0)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make(self, **kwargs):
        return TieredCache(self.l2, local_maxsize=100, local_ttl=60, **kwargs)

    def test_get_from_l2_backfills_l1(self):
        cache = self._make()
        self.l2.set("user:1", {"name": "Alice"})
        # First get: L1 miss, L2 hit, backfill L1
        assert cache.get("user:1") == {"name": "Alice"}
        # Second get: L1 hit
        assert cache.get("user:1") == {"name": "Alice"}
        assert cache.local_size == 1

    def test_get_nonexistent_returns_none(self):
        cache = self._make()
        assert cache.get("nonexistent") is None

    def test_negative_cache(self):
        cache = self._make(negative_ttl=60)
        # First miss writes negative marker
        assert cache.get("missing") is None
        assert cache.local_size == 1
        # Now add to L2, but L1 negative cache prevents L2 lookup
        self.l2.set("missing", "found")
        assert cache.get("missing") is None  # Still negative cached

    def test_l1_hit_skips_l2(self):
        cache = self._make()
        cache.set("key", "value", ttl=3600)
        # Delete from L2 directly
        self.l2.delete("key")
        # L1 still has it
        assert cache.get("key") == "value"


class TestTieredCacheSet:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)
        self.l2 = Cache(self.client, prefix="test", ttl_jitter=0)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make(self, **kwargs):
        return TieredCache(self.l2, local_maxsize=100, local_ttl=60, **kwargs)

    def test_set_writes_both_layers(self):
        cache = self._make()
        cache.set("key", "value", ttl=3600)
        assert cache.get("key") == "value"  # L1
        assert self.l2.get("key") == "value"  # L2

    def test_delete_removes_both_layers(self):
        cache = self._make()
        cache.set("key", "value")
        cache.delete("key")
        assert cache.get("key") is None
        assert self.l2.get("key") is None


class TestTieredCacheRemember:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)
        self.l2 = Cache(self.client, prefix="test", ttl_jitter=0)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make(self, **kwargs):
        return TieredCache(self.l2, local_maxsize=100, local_ttl=60, **kwargs)

    def test_remember_cache_miss(self):
        cache = self._make()
        call_count = 0
        def factory():
            nonlocal call_count
            call_count += 1
            return {"name": "Alice"}
        result = cache.remember("user:1", factory, ttl=3600)
        assert result == {"name": "Alice"}
        assert call_count == 1
        # Second call: L1 hit
        result = cache.remember("user:1", factory, ttl=3600)
        assert result == {"name": "Alice"}
        assert call_count == 1

    def test_remember_l2_hit(self):
        cache = self._make()
        self.l2.set("user:1", {"name": "Bob"})
        call_count = 0
        def factory():
            nonlocal call_count
            call_count += 1
            return {"name": "Alice"}
        result = cache.remember("user:1", factory, ttl=3600)
        assert result == {"name": "Bob"}
        assert call_count == 0


class TestTieredCacheBatch:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)
        self.l2 = Cache(self.client, prefix="test", ttl_jitter=0)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make(self, **kwargs):
        return TieredCache(self.l2, local_maxsize=100, local_ttl=60, **kwargs)

    def test_get_many_mixed(self):
        cache = self._make()
        cache.set("a", 1)  # In both L1 and L2
        self.l2.set("b", 2)  # Only in L2
        result = cache.get_many(["a", "b", "c"])
        assert result == {"a": 1, "b": 2, "c": None}
        # b should now be in L1
        assert cache.local_size == 2  # a + b (c is negative cached or not)

    def test_set_many(self):
        cache = self._make()
        cache.set_many({"a": 1, "b": 2}, ttl=3600)
        assert cache.get("a") == 1
        assert cache.get("b") == 2
        assert self.l2.get("a") == 1
        assert self.l2.get("b") == 2


class TestTieredCacheLocalManagement:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)
        self.l2 = Cache(self.client, prefix="test", ttl_jitter=0)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make(self, **kwargs):
        return TieredCache(self.l2, local_maxsize=100, local_ttl=60, **kwargs)

    def test_invalidate_local(self):
        cache = self._make()
        cache.set("key", "value")
        cache.invalidate_local("key")
        # L1 cleared, but L2 still has it
        assert self.l2.get("key") == "value"
        # Next get will go to L2 and backfill
        assert cache.get("key") == "value"

    def test_clear_local(self):
        cache = self._make()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear_local()
        assert cache.local_size == 0

    def test_local_size(self):
        cache = self._make()
        assert cache.local_size == 0
        cache.set("a", 1)
        assert cache.local_size == 1
```

- [ ] **Step 2: Implement TieredCache**

Create `redis_kit/cache/tiered.py`:
```python
from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

from redis_kit.cache.cache import Cache
from redis_kit.cache.local import LRUCache, _MISS

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
        value = self._l2.get(key)
        if value is not None:
            self._l1.set(key, value)
            return value
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
        value = self._l2.get(key)
        if value is not None:
            self._l1.set(key, value)
            return value
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

    @property
    def local_size(self) -> int:
        return self._l1.size
```

- [ ] **Step 3: Run tests and commit**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_lru_cache.py tests/test_tiered_cache.py -v`
Expected: All tests PASS

```bash
git add redis_kit/cache/local.py redis_kit/cache/tiered.py tests/test_lru_cache.py tests/test_tiered_cache.py
git commit -m "feat: add TieredCache with L1 LRU + L2 Redis, negative caching, read backfill"
```

---

## Task 3: AsyncTieredCache

**Files:**
- Create: `redis_kit/cache/async_tiered.py`
- Modify: `tests/test_tiered_cache.py`

- [ ] **Step 1: Implement AsyncTieredCache**

Create `redis_kit/cache/async_tiered.py`:
```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any

from redis_kit.cache.async_cache import AsyncCache
from redis_kit.cache.local import LRUCache, _MISS

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
```

- [ ] **Step 2: Add async tests**

Append to `tests/test_tiered_cache.py`:
```python
import pytest
import fakeredis.aioredis

from redis_kit.cache.async_cache import AsyncCache
from redis_kit.cache.async_tiered import AsyncTieredCache


class TestAsyncTieredCache:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        self.l2 = AsyncCache(self.client, prefix="test", ttl_jitter=0)
        yield

    def _make(self, **kwargs):
        return AsyncTieredCache(self.l2, local_maxsize=100, local_ttl=60, **kwargs)

    @pytest.mark.asyncio
    async def test_get_backfills_l1(self):
        cache = self._make()
        await self.l2.set("key", "value")
        assert await cache.get("key") == "value"
        assert cache.local_size == 1

    @pytest.mark.asyncio
    async def test_set_writes_both(self):
        cache = self._make()
        await cache.set("key", "value", ttl=3600)
        assert await cache.get("key") == "value"
        assert await self.l2.get("key") == "value"

    @pytest.mark.asyncio
    async def test_delete(self):
        cache = self._make()
        await cache.set("key", "value")
        await cache.delete("key")
        assert await cache.get("key") is None

    @pytest.mark.asyncio
    async def test_negative_cache(self):
        cache = self._make(negative_ttl=60)
        assert await cache.get("missing") is None
        await self.l2.set("missing", "found")
        assert await cache.get("missing") is None  # Negative cached
```

- [ ] **Step 3: Run tests and commit**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest tests/test_lru_cache.py tests/test_tiered_cache.py -v`
Expected: All tests PASS

```bash
git add redis_kit/cache/async_tiered.py tests/test_tiered_cache.py
git commit -m "feat: add AsyncTieredCache with async L2 + sync L1"
```

---

## Task 4: Exports & Integration

**Files:**
- Modify: `redis_kit/cache/__init__.py`
- Modify: `redis_kit/__init__.py`

- [ ] **Step 1: Update cache __init__.py**

Add to `redis_kit/cache/__init__.py`:
```python
from redis_kit.cache.async_tiered import AsyncTieredCache
from redis_kit.cache.local import LRUCache
from redis_kit.cache.tiered import TieredCache
```

Add to `__all__`: `"AsyncTieredCache"`, `"LRUCache"`, `"TieredCache"`

- [ ] **Step 2: Update top-level __init__.py**

Add imports and `__all__` entries for `TieredCache` and `AsyncTieredCache`.

- [ ] **Step 3: Verify imports**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run python -c "from redis_kit import TieredCache, AsyncTieredCache; from redis_kit.cache import LRUCache; print('OK')"`

- [ ] **Step 4: Run full test suite + lint + mypy**

Run: `cd E:/_coding/github/Xinzz995/redis-kit && uv run pytest -v && uv run ruff check . && uv run mypy redis_kit`

- [ ] **Step 5: Commit**

```bash
git add redis_kit/cache/__init__.py redis_kit/__init__.py
git commit -m "feat: export TieredCache, AsyncTieredCache, LRUCache"
```

---

## Summary

| Task | Component | Steps |
|------|-----------|-------|
| 1 | LRUCache (thread-safe, TTL, LRU eviction) | 3 |
| 2 | TieredCache (sync L1→L2, negative cache, batch) | 3 |
| 3 | AsyncTieredCache + async tests | 3 |
| 4 | Exports & integration | 5 |
| **Total** | | **14 steps** |
