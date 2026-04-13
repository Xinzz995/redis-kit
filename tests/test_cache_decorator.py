import fakeredis
import pytest

from redis_kit.cache.decorator import cached


class TestCachedDecorator:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_caches_result(self):
        call_count = 0

        @cached(self.client, key="user:{user_id}", ttl=60, ttl_jitter=0)
        def get_user(user_id: int) -> dict:
            nonlocal call_count
            call_count += 1
            return {"id": user_id, "name": "Alice"}

        result1 = get_user(1)
        result2 = get_user(1)
        assert result1 == {"id": 1, "name": "Alice"}
        assert result2 == {"id": 1, "name": "Alice"}
        assert call_count == 1

    def test_different_args_different_keys(self):
        @cached(self.client, key="user:{user_id}", ttl=60, ttl_jitter=0)
        def get_user(user_id: int) -> dict:
            return {"id": user_id}

        assert get_user(1) == {"id": 1}
        assert get_user(2) == {"id": 2}

    def test_callable_key(self):
        @cached(self.client, key=lambda uid: f"custom:{uid}", ttl=60, ttl_jitter=0)
        def get_user(uid: int) -> dict:
            return {"id": uid}

        get_user(1)
        assert self.client.exists(b"custom:1")

    def test_callable_ttl(self):
        @cached(
            self.client,
            key="item:{priority}",
            ttl=lambda priority: 3600 if priority == "high" else 60,
            ttl_jitter=0,
        )
        def get_item(priority: str) -> dict:
            return {"priority": priority}

        get_item("high")
        assert self.client.ttl(b"item:high") > 3000

        get_item("low")
        assert self.client.ttl(b"item:low") <= 60

    def test_bypass_cache(self):
        call_count = 0

        @cached(
            self.client,
            key="data:{key}",
            ttl=60,
            bypass=lambda key, force=False: force,
            ttl_jitter=0,
        )
        def get_data(key: str, force: bool = False) -> dict:
            nonlocal call_count
            call_count += 1
            return {"key": key, "count": call_count}

        get_data("a")
        assert call_count == 1
        get_data("a")
        assert call_count == 1
        get_data("a", force=True)
        assert call_count == 2

    def test_string_ttl(self):
        @cached(self.client, key="item:{x}", ttl="1h", ttl_jitter=0)
        def get_item(x: int) -> int:
            return x

        get_item(1)
        assert 3598 <= self.client.ttl(b"item:1") <= 3600

    def test_invalidate_removes_cached_value(self):
        """@cached .invalidate() should delete the cache key for given args."""

        @cached(self.client, key="inv:{x}", ttl=60, ttl_jitter=0)
        def compute(x: int) -> int:
            return x * 10

        assert compute(5) == 50
        compute.invalidate(5)
        raw = self.client.get(b"inv:5")
        assert raw is None

    @pytest.mark.asyncio
    async def test_async_function(self):
        async_client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        call_count = 0

        @cached(async_client, key="async:{x}", ttl=60, ttl_jitter=0)
        async def async_fn(x: int) -> dict:
            nonlocal call_count
            call_count += 1
            return {"x": x}

        try:
            result = await async_fn(1)
            assert result == {"x": 1}
            result2 = await async_fn(1)
            assert result2 == {"x": 1}
            assert call_count == 1
        finally:
            await async_client.flushall()
            await async_client.aclose()

    @pytest.mark.asyncio
    async def test_async_invalidate_removes_cached_value(self):
        """@cached async .invalidate() should delete the cache key for given args."""
        async_client = fakeredis.aioredis.FakeRedis(decode_responses=False)

        @cached(async_client, key="ainv:{x}", ttl=60, ttl_jitter=0)
        async def compute(x: int) -> int:
            return x * 10

        try:
            assert await compute(5) == 50
            await compute.invalidate(5)
            raw = await async_client.get(b"ainv:5")
            assert raw is None
        finally:
            await async_client.flushall()
            await async_client.aclose()


def test_cached_with_compressor(redis_client):
    """@cached with compressor should produce data decodable by Cache with same compressor."""
    from redis_kit.cache.decorator import cached
    from redis_kit.cache._logic import DataPipeline
    from redis_kit.compressors.zlib import ZlibCompressor

    compressor = ZlibCompressor()

    @cached(redis_client, key="comp:{x}", ttl=300, compressor=compressor)
    def compute(x: int) -> dict:
        return {"result": x * 2}

    result = compute(5)
    assert result == {"result": 10}

    # Verify the stored data can be decoded with the same compressor
    pipeline = DataPipeline(compressor=compressor)
    raw = redis_client.get("comp:5")
    assert raw is not None
    decoded = pipeline.decode(raw)
    assert decoded == {"result": 10}
