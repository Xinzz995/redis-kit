import fakeredis

from redis_kit.cache.cache import Cache


class TestCacheClusterMode:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_is_cluster_flag_stored(self):
        cache = Cache(self.client, prefix="test", is_cluster=True, ttl_jitter=0)
        assert cache._is_cluster is True

    def test_is_cluster_default_false(self):
        cache = Cache(self.client, prefix="test", ttl_jitter=0)
        assert cache._is_cluster is False

    def test_get_many_works_in_cluster_mode(self):
        cache = Cache(self.client, prefix="test", is_cluster=True, ttl_jitter=0)
        cache.set("a", 1)
        cache.set("b", 2)
        result = cache.get_many(["a", "b", "c"])
        assert result == {"a": 1, "b": 2, "c": None}

    def test_set_many_works_in_cluster_mode(self):
        cache = Cache(self.client, prefix="test", is_cluster=True, ttl_jitter=0)
        cache.set_many({"a": 1, "b": 2}, ttl=3600)
        assert cache.get("a") == 1
        assert cache.get("b") == 2

    def test_standalone_get_many_unchanged(self):
        cache = Cache(self.client, prefix="test", is_cluster=False, ttl_jitter=0)
        cache.set("a", 1)
        cache.set("b", 2)
        result = cache.get_many(["a", "b"])
        assert result == {"a": 1, "b": 2}
