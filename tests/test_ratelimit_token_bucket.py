import fakeredis
import pytest

from redis_kit.exceptions import RateLimitExceeded, RedisKitError
from redis_kit.ratelimit._result import RateLimitResult
from redis_kit.ratelimit.token_bucket import TokenBucketLimiter


class TestRateLimitResult:
    def test_fields(self):
        r = RateLimitResult(allowed=True, limit=100, remaining=99, retry_after=0.0, reset_at=1000.0)
        assert r.allowed is True
        assert r.limit == 100
        assert r.remaining == 99
        assert r.retry_after == 0.0
        assert r.reset_at == 1000.0

    def test_frozen(self):
        r = RateLimitResult(allowed=True, limit=100, remaining=99, retry_after=0.0, reset_at=1000.0)
        with pytest.raises(AttributeError):
            r.allowed = False


class TestRateLimitExceeded:
    def test_inherits_from_base(self):
        r = RateLimitResult(allowed=False, limit=100, remaining=0, retry_after=5.0, reset_at=1000.0)
        with pytest.raises(RedisKitError):
            raise RateLimitExceeded(r)

    def test_carries_result(self):
        r = RateLimitResult(allowed=False, limit=100, remaining=0, retry_after=5.0, reset_at=1000.0)
        exc = RateLimitExceeded(r)
        assert exc.result is r
        assert "retry after 5.0s" in str(exc)


class TestTokenBucketLimiter:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_allows_within_capacity(self):
        limiter = TokenBucketLimiter(self.client, rate=10, capacity=5)
        result = limiter.acquire("user:1")
        assert result.allowed is True
        assert result.remaining >= 0
        assert result.limit == 5

    def test_exhausts_capacity(self):
        limiter = TokenBucketLimiter(self.client, rate=1, capacity=3)
        for _ in range(3):
            result = limiter.acquire("user:1")
            assert result.allowed is True
        result = limiter.acquire("user:1")
        assert result.allowed is False
        assert result.retry_after > 0

    def test_different_keys_independent(self):
        limiter = TokenBucketLimiter(self.client, rate=1, capacity=1)
        r1 = limiter.acquire("user:1")
        r2 = limiter.acquire("user:2")
        assert r1.allowed is True
        assert r2.allowed is True

    def test_reset_clears_state(self):
        limiter = TokenBucketLimiter(self.client, rate=1, capacity=1)
        limiter.acquire("user:1")
        limiter.acquire("user:1")  # exhausted
        limiter.reset("user:1")
        result = limiter.acquire("user:1")
        assert result.allowed is True

    def test_cost_parameter(self):
        limiter = TokenBucketLimiter(self.client, rate=1, capacity=5)
        result = limiter.acquire("user:1", cost=3)
        assert result.allowed is True
        assert result.remaining == 2
        result = limiter.acquire("user:1", cost=3)
        assert result.allowed is False

    def test_result_has_retry_after(self):
        limiter = TokenBucketLimiter(self.client, rate=1, capacity=1)
        limiter.acquire("user:1")
        result = limiter.acquire("user:1")
        assert result.allowed is False
        assert result.retry_after > 0
        assert result.reset_at > 0

    def test_hash_tag_in_keys(self):
        limiter = TokenBucketLimiter(self.client, prefix="rl")
        limiter.acquire("test")
        keys = [k.decode() for k in self.client.keys(b"*")]
        for k in keys:
            assert "{" in k and "}" in k
