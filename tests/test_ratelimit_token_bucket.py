import pytest

from redis_kit.ratelimit._result import RateLimitResult
from redis_kit.exceptions import RateLimitExceeded, RedisKitError


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
