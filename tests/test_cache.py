from unittest.mock import MagicMock, patch

import fakeredis
import fakeredis.aioredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from redis_kit.cache._logic import apply_jitter, parse_ttl
from redis_kit.cache.async_cache import AsyncCache
from redis_kit.cache.cache import Cache
from redis_kit.exceptions import FallbackPolicy


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

    def test_rejects_negative(self):
        with pytest.raises(ValueError, match="non-negative"):
            parse_ttl(-5)
        with pytest.raises(ValueError, match="non-negative"):
            parse_ttl(-1)
        # Zero should be fine
        assert parse_ttl(0) == 0


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

    def test_hook_exception_does_not_break_cache_operation(self):
        """A misbehaving hook should not break cache get/set."""

        class BrokenHook:
            def before(self, command, key, args):
                raise RuntimeError("hook exploded")

            def after(self, command, key, result, duration_ms):
                raise RuntimeError("hook exploded")

            def on_error(self, command, key, error):
                raise RuntimeError("hook exploded")

        cache = self._make_cache(hooks=[BrokenHook()])
        cache.set("key1", "value1", ttl=60)
        result = cache.get("key1")
        assert result == "value1"


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


# ---------------------------------------------------------------------------
# Hook lifecycle tests
# ---------------------------------------------------------------------------


class _SpyHook:
    """Minimal hook that records all calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []  # (phase, command, key)
        self.errors: list[Exception] = []

    def before(self, command: str, key: str, args: tuple) -> None:
        self.calls.append(("before", command, key))

    def after(self, command: str, key: str, result, duration_ms: float) -> None:
        self.calls.append(("after", command, key))

    def on_error(self, command: str, key: str, error: Exception) -> None:
        self.calls.append(("error", command, key))
        self.errors.append(error)


class TestCacheHooksLifecycle:
    """Verify before/after/error hooks are called in the correct order."""

    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)
        self.hook = _SpyHook()

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def _make_cache(self, **kwargs):
        return Cache(self.client, prefix="t", ttl_jitter=0, hooks=[self.hook], **kwargs)

    def test_get_calls_before_and_after(self):
        cache = self._make_cache()
        cache.set("k", "v")
        self.hook.calls.clear()
        cache.get("k")
        phases = [c[0] for c in self.hook.calls]
        assert phases == ["before", "after"]

    def test_set_calls_before_and_after(self):
        cache = self._make_cache()
        cache.set("k", "v")
        phases = [c[0] for c in self.hook.calls]
        assert phases == ["before", "after"]

    def test_delete_calls_before_and_after_hook(self):
        cache = self._make_cache()
        cache.set("k", "v")
        self.hook.calls.clear()
        cache.delete("k")
        phases = [c[0] for c in self.hook.calls]
        assert "before" in phases
        assert "after" in phases

    def test_get_error_calls_on_error(self):
        cache = self._make_cache()
        err = RedisConnectionError("down")
        with patch.object(self.client, "get", side_effect=err):
            # Default policy is "raise"
            with pytest.raises(RedisConnectionError):
                cache.get("k")
        phases = [c[0] for c in self.hook.calls]
        assert phases == ["before", "error"]
        assert self.hook.errors[0] is err

    def test_set_error_calls_on_error(self):
        cache = self._make_cache()
        err = RedisConnectionError("down")
        with patch.object(self.client, "set", side_effect=err):
            with pytest.raises(RedisConnectionError):
                cache.set("k", "v")
        phases = [c[0] for c in self.hook.calls]
        assert phases == ["before", "error"]

    def test_remember_hooks_called(self):
        cache = self._make_cache()
        cache.remember("k", lambda: "val", ttl=60)
        # remember triggers _get_raw (before+after for GET) then set (before+after for SET)
        commands = [(c[0], c[1]) for c in self.hook.calls]
        assert ("before", "GET") in commands
        assert ("after", "GET") in commands
        assert ("before", "SET") in commands
        assert ("after", "SET") in commands

    def test_get_many_hooks(self):
        cache = self._make_cache()
        cache.set("a", 1)
        self.hook.calls.clear()
        cache.get_many(["a", "b"])
        phases = [c[0] for c in self.hook.calls]
        assert phases == ["before", "after"]
        assert self.hook.calls[0][1] == "GET_MANY"

    def test_set_many_hooks(self):
        cache = self._make_cache()
        cache.set_many({"a": 1, "b": 2})
        # filter to SET_MANY only (set_many doesn't call set() internally)
        sm_calls = [c for c in self.hook.calls if c[1] == "SET_MANY"]
        phases = [c[0] for c in sm_calls]
        assert phases == ["before", "after"]

    def test_delete_pattern_hooks(self):
        cache = self._make_cache()
        cache.set("x:1", "a")
        self.hook.calls.clear()
        cache.delete_pattern("x:*")
        dp_calls = [c for c in self.hook.calls if c[1] == "DELETE_PATTERN"]
        phases = [c[0] for c in dp_calls]
        assert phases == ["before", "after"]

    def test_non_connection_error_always_reraises(self):
        """Non-connection errors should re-raise even with return_none policy."""
        policy = FallbackPolicy(on_connection_error="return_none")
        cache = Cache(self.client, prefix="t", ttl_jitter=0, hooks=[self.hook], fallback_policy=policy)
        with patch.object(self.client, "get", side_effect=ValueError("bad")):
            with pytest.raises(ValueError, match="bad"):
                cache.get("k")
        phases = [c[0] for c in self.hook.calls]
        assert "error" in phases


class TestAsyncCacheHooksLifecycle:
    """Verify before/after/error hooks are called in async variant."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        self.hook = _SpyHook()
        yield

    def _make_cache(self, **kwargs):
        return AsyncCache(self.client, prefix="t", ttl_jitter=0, hooks=[self.hook], **kwargs)

    @pytest.mark.asyncio
    async def test_get_calls_before_and_after(self):
        cache = self._make_cache()
        await cache.set("k", "v")
        self.hook.calls.clear()
        await cache.get("k")
        phases = [c[0] for c in self.hook.calls]
        assert phases == ["before", "after"]

    @pytest.mark.asyncio
    async def test_set_calls_before_and_after(self):
        cache = self._make_cache()
        await cache.set("k", "v")
        phases = [c[0] for c in self.hook.calls]
        assert phases == ["before", "after"]

    @pytest.mark.asyncio
    async def test_get_error_calls_on_error(self):
        cache = self._make_cache()
        err = RedisConnectionError("down")
        with patch.object(self.client, "get", side_effect=err):
            with pytest.raises(RedisConnectionError):
                await cache.get("k")
        phases = [c[0] for c in self.hook.calls]
        assert phases == ["before", "error"]
        assert self.hook.errors[0] is err

    @pytest.mark.asyncio
    async def test_non_connection_error_always_reraises(self):
        policy = FallbackPolicy(on_connection_error="return_none")
        cache = AsyncCache(self.client, prefix="t", ttl_jitter=0, hooks=[self.hook], fallback_policy=policy)
        with patch.object(self.client, "get", side_effect=ValueError("bad")):
            with pytest.raises(ValueError, match="bad"):
                await cache.get("k")
        phases = [c[0] for c in self.hook.calls]
        assert "error" in phases


# ---------------------------------------------------------------------------
# FallbackPolicy tests
# ---------------------------------------------------------------------------


class TestCacheFallbackPolicy:
    """Test FallbackPolicy behavior for sync Cache."""

    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_raise_policy_reraises_connection_error(self):
        policy = FallbackPolicy(on_connection_error="raise")
        cache = Cache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        with patch.object(self.client, "get", side_effect=RedisConnectionError("fail")):
            with pytest.raises(RedisConnectionError):
                cache.get("k")

    def test_raise_policy_reraises_timeout_error(self):
        policy = FallbackPolicy(on_connection_error="raise")
        cache = Cache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        with patch.object(self.client, "get", side_effect=RedisTimeoutError("timeout")):
            with pytest.raises(RedisTimeoutError):
                cache.get("k")

    def test_return_none_policy_get(self):
        policy = FallbackPolicy(on_connection_error="return_none")
        cache = Cache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        with patch.object(self.client, "get", side_effect=RedisConnectionError("fail")):
            result = cache.get("k")
        assert result is None

    def test_return_none_policy_set_silently_skips(self):
        policy = FallbackPolicy(on_connection_error="return_none")
        cache = Cache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        with patch.object(self.client, "set", side_effect=RedisConnectionError("fail")):
            # Should not raise
            cache.set("k", "v")

    def test_return_none_policy_logs_warning(self, caplog):
        policy = FallbackPolicy(on_connection_error="return_none", log_on_fallback=True)
        cache = Cache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        with patch.object(self.client, "get", side_effect=RedisConnectionError("fail")):
            with caplog.at_level("WARNING", logger="redis_kit"):
                cache.get("k")
        assert "fail" in caplog.text

    def test_callback_policy_invokes_fallback(self):
        cb = MagicMock(return_value="fallback_value")
        policy = FallbackPolicy(on_connection_error="callback", fallback=cb)
        cache = Cache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        err = RedisConnectionError("fail")
        with patch.object(self.client, "get", side_effect=err):
            result = cache.get("k")
        assert result == "fallback_value"
        cb.assert_called_once_with("GET", "k", err)

    def test_callback_policy_no_callback_reraises(self):
        policy = FallbackPolicy(on_connection_error="callback", fallback=None)
        cache = Cache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        with patch.object(self.client, "get", side_effect=RedisConnectionError("fail")):
            with pytest.raises(RedisConnectionError):
                cache.get("k")

    def test_default_policy_is_raise(self):
        """Cache with no explicit policy should re-raise connection errors."""
        cache = Cache(self.client, prefix="t", ttl_jitter=0)
        with patch.object(self.client, "get", side_effect=RedisConnectionError("fail")):
            with pytest.raises(RedisConnectionError):
                cache.get("k")

    def test_return_none_with_timeout_error(self):
        policy = FallbackPolicy(on_connection_error="return_none")
        cache = Cache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        with patch.object(self.client, "get", side_effect=RedisTimeoutError("timeout")):
            result = cache.get("k")
        assert result is None


class TestAsyncCacheFallbackPolicy:
    """Test FallbackPolicy behavior for async Cache."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    @pytest.mark.asyncio
    async def test_raise_policy_reraises(self):
        policy = FallbackPolicy(on_connection_error="raise")
        cache = AsyncCache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        with patch.object(self.client, "get", side_effect=RedisConnectionError("fail")):
            with pytest.raises(RedisConnectionError):
                await cache.get("k")

    @pytest.mark.asyncio
    async def test_return_none_policy_get(self):
        policy = FallbackPolicy(on_connection_error="return_none")
        cache = AsyncCache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        with patch.object(self.client, "get", side_effect=RedisConnectionError("fail")):
            result = await cache.get("k")
        assert result is None

    @pytest.mark.asyncio
    async def test_return_none_policy_set_silently_skips(self):
        policy = FallbackPolicy(on_connection_error="return_none")
        cache = AsyncCache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        with patch.object(self.client, "set", side_effect=RedisConnectionError("fail")):
            await cache.set("k", "v")

    @pytest.mark.asyncio
    async def test_callback_policy_invokes_fallback(self):
        cb = MagicMock(return_value="fallback_value")
        policy = FallbackPolicy(on_connection_error="callback", fallback=cb)
        cache = AsyncCache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        err = RedisConnectionError("fail")
        with patch.object(self.client, "get", side_effect=err):
            result = await cache.get("k")
        assert result == "fallback_value"
        cb.assert_called_once_with("GET", "k", err)

    @pytest.mark.asyncio
    async def test_callback_policy_no_callback_reraises(self):
        policy = FallbackPolicy(on_connection_error="callback", fallback=None)
        cache = AsyncCache(self.client, prefix="t", ttl_jitter=0, fallback_policy=policy)
        with patch.object(self.client, "get", side_effect=RedisConnectionError("fail")):
            with pytest.raises(RedisConnectionError):
                await cache.get("k")
