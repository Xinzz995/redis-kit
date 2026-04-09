import time

from redis_kit.cache.local import _MISS, LRUCache


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
