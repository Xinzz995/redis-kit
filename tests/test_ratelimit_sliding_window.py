import fakeredis

from redis_kit.ratelimit.sliding_window import SlidingWindowLimiter


class TestSlidingWindowLimiter:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_allows_within_limit(self):
        limiter = SlidingWindowLimiter(self.client, limit=5, window=60)
        result = limiter.acquire("user:1")
        assert result.allowed is True
        assert result.limit == 5
        assert result.remaining == 4

    def test_blocks_at_limit(self):
        limiter = SlidingWindowLimiter(self.client, limit=3, window=60)
        for _ in range(3):
            result = limiter.acquire("user:1")
            assert result.allowed is True
        result = limiter.acquire("user:1")
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after > 0

    def test_different_keys_independent(self):
        limiter = SlidingWindowLimiter(self.client, limit=1, window=60)
        r1 = limiter.acquire("user:1")
        r2 = limiter.acquire("user:2")
        assert r1.allowed is True
        assert r2.allowed is True

    def test_reset_clears_state(self):
        limiter = SlidingWindowLimiter(self.client, limit=1, window=60)
        limiter.acquire("user:1")
        limiter.acquire("user:1")  # blocked
        limiter.reset("user:1")
        result = limiter.acquire("user:1")
        assert result.allowed is True

    def test_remaining_decrements(self):
        limiter = SlidingWindowLimiter(self.client, limit=5, window=60)
        results = [limiter.acquire("user:1") for _ in range(5)]
        assert results[0].remaining == 4
        assert results[1].remaining == 3
        assert results[2].remaining == 2
        assert results[3].remaining == 1
        assert results[4].remaining == 0

    def test_result_has_reset_at(self):
        limiter = SlidingWindowLimiter(self.client, limit=1, window=60)
        result = limiter.acquire("user:1")
        assert result.reset_at > 0
