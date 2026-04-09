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
