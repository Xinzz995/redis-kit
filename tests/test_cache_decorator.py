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


class TestCachedOnError:
    """Tests for @cached(on_error='execute') degradation."""

    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_on_error_rejects_invalid_value(self):
        with pytest.raises(ValueError, match="on_error"):
            cached(self.client, key="k:{x}", ttl=60, on_error="invalid")

    def test_on_error_raise_propagates_redis_error(self):
        """Default on_error='raise' should let Redis errors propagate."""
        from unittest.mock import patch

        @cached(self.client, key="err:{x}", ttl=60, on_error="raise")
        def compute(x: int) -> int:
            return x * 10

        # First call populates cache normally
        assert compute(1) == 10

        # Simulate Redis failure on read
        with patch.object(self.client, "get", side_effect=ConnectionError("down")):
            with pytest.raises(ConnectionError):
                compute(2)

    def test_on_error_execute_skips_cache_on_read_failure(self):
        """on_error='execute' should run the function when cache read fails."""
        from unittest.mock import patch

        call_count = 0

        @cached(self.client, key="safe:{x}", ttl=60, on_error="execute")
        def compute(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 10

        # Normal path: caches result
        assert compute(1) == 10
        assert call_count == 1

        # Simulate Redis failure on read — should execute function directly
        with patch.object(self.client, "get", side_effect=ConnectionError("down")):
            result = compute(2)
            assert result == 20
            assert call_count == 2

    def test_on_error_execute_skips_cache_on_write_failure(self):
        """on_error='execute' should still return result even if cache write fails."""
        from unittest.mock import patch

        @cached(self.client, key="wfail:{x}", ttl=60, on_error="execute")
        def compute(x: int) -> int:
            return x * 10

        # Simulate Redis failure on write (setex)
        with patch.object(self.client, "setex", side_effect=ConnectionError("down")):
            with patch.object(self.client, "set", side_effect=ConnectionError("down")):
                result = compute(1)
                assert result == 10  # function executed, cache write silently failed

    def test_on_error_execute_skips_cache_on_key_resolution_failure(self):
        """on_error='execute' should execute when key template fails."""

        @cached(self.client, key="bad:{missing_param}", ttl=60, on_error="execute")
        def compute(x: int) -> int:
            return x * 10

        # key template references 'missing_param' but function has 'x'
        result = compute(1)
        assert result == 10

    @pytest.mark.asyncio
    async def test_async_on_error_execute(self):
        """on_error='execute' works for async functions."""
        from unittest.mock import patch

        async_client = fakeredis.aioredis.FakeRedis(decode_responses=False)

        @cached(async_client, key="async_safe:{x}", ttl=60, on_error="execute")
        async def compute(x: int) -> int:
            return x * 10

        try:
            # Simulate Redis failure
            with patch.object(async_client, "get", side_effect=ConnectionError("down")):
                result = await compute(1)
                assert result == 10
        finally:
            await async_client.flushall()
            await async_client.aclose()


def test_cached_with_compressor(redis_client):
    """@cached with compressor should produce data decodable by Cache with same compressor."""
    from redis_kit.cache._logic import DataPipeline
    from redis_kit.cache.decorator import cached
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
