import fakeredis
import fakeredis.aioredis
import pytest

from redis_kit.cache._logic import apply_jitter, parse_ttl
from redis_kit.cache.async_cache import AsyncCache
from redis_kit.cache.cache import Cache


class TestParseTtl:
    def test_int(self):
        assert parse_ttl(60) == 60

    def test_float(self):
        assert parse_ttl(60.5) == 60

    def test_string_hours_minutes(self):
        assert parse_ttl("2h30m") == 9000

    def test_string_seconds(self):
        assert parse_ttl("30s") == 30

    def test_string_days(self):
        assert parse_ttl("1d") == 86400

    def test_invalid_string(self):
        with pytest.raises(ValueError):
            parse_ttl("invalid")


class TestApplyJitter:
    def test_jitter_clamps_to_minimum_one(self):
        """apply_jitter should never return less than 1."""
        # With ttl=1 and jitter=1.0, delta=1, range is [-1, 1]
        # Even worst case (1 + (-1) = 0) should be clamped to 1
        results = {apply_jitter(1, 1.0) for _ in range(200)}
        assert all(r >= 1 for r in results)

    def test_jitter_no_jitter_passthrough(self):
        assert apply_jitter(60, 0) == 60

    def test_jitter_zero_ttl_passthrough(self):
        assert apply_jitter(0, 0.5) == 0


class TestCache:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make_cache(self, **kwargs):
        return Cache(self.client, prefix="test:cache", ttl_jitter=0, **kwargs)

    def test_set_and_get(self):
        cache = self._make_cache()
        cache.set("user:1", {"name": "Alice"}, ttl=3600)
        assert cache.get("user:1") == {"name": "Alice"}

    def test_get_nonexistent(self):
        cache = self._make_cache()
        assert cache.get("nonexistent") is None

    def test_delete(self):
        cache = self._make_cache()
        cache.set("user:1", "data")
        cache.delete("user:1")
        assert cache.get("user:1") is None

    def test_ttl(self):
        cache = self._make_cache()
        cache.set("user:1", "data", ttl=3600)
        assert 3598 <= cache.ttl("user:1") <= 3600

    def test_persist(self):
        cache = self._make_cache()
        cache.set("user:1", "data", ttl=3600)
        cache.persist("user:1")
        assert cache.ttl("user:1") == -1

    def test_expire(self):
        cache = self._make_cache()
        cache.set("user:1", "data")
        cache.expire("user:1", 600)
        assert 598 <= cache.ttl("user:1") <= 600

    def test_remember_cache_hit(self):
        cache = self._make_cache()
        cache.set("user:1", {"name": "Alice"})
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return {"name": "Bob"}

        result = cache.remember("user:1", factory)
        assert result == {"name": "Alice"}
        assert call_count == 0

    def test_remember_cache_miss(self):
        cache = self._make_cache()
        result = cache.remember("user:1", lambda: {"name": "Alice"}, ttl=3600)
        assert result == {"name": "Alice"}
        assert cache.get("user:1") == {"name": "Alice"}

    def test_get_many(self):
        cache = self._make_cache()
        cache.set("a", 1)
        cache.set("b", 2)
        result = cache.get_many(["a", "b", "c"])
        assert result == {"a": 1, "b": 2, "c": None}

    def test_set_many(self):
        cache = self._make_cache()
        cache.set_many({"a": 1, "b": 2}, ttl=3600)
        assert cache.get("a") == 1
        assert cache.get("b") == 2

    def test_remember_caches_none_value(self):
        """remember() should cache None from factory and not re-call factory."""
        cache = self._make_cache()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return None

        result1 = cache.remember("none_key", factory, ttl=60)
        assert result1 is None
        assert call_count == 1

        result2 = cache.remember("none_key", factory, ttl=60)
        assert result2 is None
        assert call_count == 1  # factory NOT called again

    def test_cache_none_value(self):
        cache = self._make_cache()
        cache.set("user:999", None, ttl=60)
        assert self.client.exists(b"test:cache:user:999")

    def test_prefix_applied(self):
        cache = self._make_cache()
        cache.set("mykey", "val")
        assert self.client.exists(b"test:cache:mykey")

    def test_bind(self):
        cache = self._make_cache()
        bound = cache.bind("user:1")
        bound.set({"name": "Alice"}, ttl=3600)
        assert bound.get() == {"name": "Alice"}
        assert bound.ttl() > 0
        bound.delete()
        assert bound.get() is None

    def test_ttl_string_format(self):
        cache = self._make_cache()
        cache.set("key", "val", ttl="1h30m")
        ttl_val = cache.ttl("key")
        assert 5398 <= ttl_val <= 5400

    def test_delete_pattern(self):
        cache = self._make_cache()
        cache.set("user:1", "a")
        cache.set("user:2", "b")
        cache.set("product:1", "c")
        count = cache.delete_pattern("user:*")
        assert count == 2
        assert cache.get("product:1") == "c"

    def test_iter_keys(self):
        cache = self._make_cache()
        cache.set("user:1", "a")
        cache.set("user:2", "b")
        keys = list(cache.iter_keys("user:*"))
        assert sorted(keys) == ["user:1", "user:2"]


class TestAsyncCache:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    def _make_cache(self, **kwargs):
        return AsyncCache(self.client, prefix="test:cache", ttl_jitter=0, **kwargs)

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        cache = self._make_cache()
        await cache.set("key", {"name": "Alice"}, ttl=3600)
        assert await cache.get("key") == {"name": "Alice"}

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        cache = self._make_cache()
        assert await cache.get("missing") is None

    @pytest.mark.asyncio
    async def test_delete(self):
        cache = self._make_cache()
        await cache.set("key", "val")
        await cache.delete("key")
        assert await cache.get("key") is None

    @pytest.mark.asyncio
    async def test_ttl_and_persist(self):
        cache = self._make_cache()
        await cache.set("key", "val", ttl=3600)
        assert await cache.ttl("key") > 3500
        await cache.persist("key")
        assert await cache.ttl("key") == -1

    @pytest.mark.asyncio
    async def test_expire(self):
        cache = self._make_cache()
        await cache.set("key", "val")
        await cache.expire("key", 600)
        assert 500 < await cache.ttl("key") <= 600

    @pytest.mark.asyncio
    async def test_remember(self):
        cache = self._make_cache()
        result = await cache.remember("key", lambda: {"val": 1}, ttl=3600)
        assert result == {"val": 1}
        result2 = await cache.remember("key", lambda: {"val": 2}, ttl=3600)
        assert result2 == {"val": 1}

    @pytest.mark.asyncio
    async def test_remember_caches_none_value(self):
        """remember() should cache None from factory and not re-call factory."""
        cache = self._make_cache()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return None

        result1 = await cache.remember("none_key", factory, ttl=60)
        assert result1 is None
        assert call_count == 1

        result2 = await cache.remember("none_key", factory, ttl=60)
        assert result2 is None
        assert call_count == 1  # factory NOT called again

    @pytest.mark.asyncio
    async def test_get_many(self):
        cache = self._make_cache()
        await cache.set("a", 1)
        await cache.set("b", 2)
        result = await cache.get_many(["a", "b", "c"])
        assert result == {"a": 1, "b": 2, "c": None}

    @pytest.mark.asyncio
    async def test_set_many(self):
        cache = self._make_cache()
        await cache.set_many({"a": 1, "b": 2}, ttl=3600)
        assert await cache.get("a") == 1
        assert await cache.get("b") == 2

    @pytest.mark.asyncio
    async def test_bind(self):
        cache = self._make_cache()
        bound = cache.bind("key")
        await bound.set({"name": "Alice"}, ttl=3600)
        assert await bound.get() == {"name": "Alice"}
        assert await bound.ttl() > 0
        await bound.delete()
        assert await bound.get() is None
