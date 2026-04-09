import fakeredis
import fakeredis.aioredis
import pytest

from redis_kit.exceptions import RateLimitExceeded
from redis_kit.ratelimit.decorator import parse_rate_dsl, rate_limit


class TestParseRateDsl:
    def test_per_minute(self):
        assert parse_rate_dsl("100/minute") == (100, 60)

    def test_per_second(self):
        assert parse_rate_dsl("10/second") == (10, 1)

    def test_per_hour(self):
        assert parse_rate_dsl("1000/hour") == (1000, 3600)

    def test_per_day(self):
        assert parse_rate_dsl("10000/day") == (10000, 86400)

    def test_with_spaces(self):
        assert parse_rate_dsl("100 / minute") == (100, 60)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_rate_dsl("invalid")

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError):
            parse_rate_dsl("100/fortnight")


class TestRateLimitDecorator:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)
        self.async_client = fakeredis.aioredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_allows_within_limit(self):
        @rate_limit(self.client, key="test:{x}", limit="5/minute", algorithm="sliding_window")
        def fn(x: int) -> int:
            return x * 2

        assert fn(1) == 2

    def test_blocks_over_limit(self):
        @rate_limit(self.client, key="test:{x}", limit="2/minute", algorithm="sliding_window")
        def fn(x: int) -> int:
            return x

        fn(1)
        fn(1)
        with pytest.raises(RateLimitExceeded) as exc_info:
            fn(1)
        assert exc_info.value.result.allowed is False
        assert exc_info.value.result.retry_after > 0

    def test_different_keys_independent(self):
        @rate_limit(self.client, key="test:{x}", limit="1/minute", algorithm="sliding_window")
        def fn(x: int) -> int:
            return x

        assert fn(1) == 1
        assert fn(2) == 2

    def test_callable_key(self):
        @rate_limit(self.client, key=lambda uid: f"custom:{uid}", limit="5/minute", algorithm="sliding_window")
        def fn(uid: int) -> int:
            return uid

        assert fn(1) == 1

    def test_token_bucket_algorithm(self):
        @rate_limit(self.client, key="tb:{x}", limit="3/second", algorithm="token_bucket")
        def fn(x: int) -> int:
            return x

        assert fn(1) == 1

    @pytest.mark.asyncio
    async def test_async_function(self):
        @rate_limit(self.async_client, key="async:{x}", limit="5/minute", algorithm="sliding_window")
        async def fn(x: int) -> int:
            return x * 2

        result = await fn(1)
        assert result == 2
