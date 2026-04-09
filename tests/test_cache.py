import fakeredis
import pytest

from redis_kit.cache._logic import parse_ttl
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
