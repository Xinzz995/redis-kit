import fakeredis
import fakeredis.aioredis
import pytest

from redis_kit.bloom.async_bloom import AsyncBloomFilter
from redis_kit.bloom.bloom import BloomFilter


class TestBloomFilter:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_add_and_exists(self):
        bf = BloomFilter(self.client, "emails", expected_items=1000, false_positive_rate=0.01)
        bf.add("alice@example.com")
        assert bf.exists("alice@example.com") is True

    def test_not_exists(self):
        bf = BloomFilter(self.client, "emails", expected_items=1000, false_positive_rate=0.01)
        assert bf.exists("unknown@example.com") is False

    def test_add_many(self):
        bf = BloomFilter(self.client, "emails", expected_items=1000, false_positive_rate=0.01)
        bf.add_many(["a@x.com", "b@x.com", "c@x.com"])
        assert bf.exists("a@x.com") is True
        assert bf.exists("b@x.com") is True
        assert bf.exists("c@x.com") is True

    def test_exists_many(self):
        bf = BloomFilter(self.client, "emails", expected_items=1000, false_positive_rate=0.01)
        bf.add("a@x.com")
        results = bf.exists_many(["a@x.com", "d@x.com"])
        assert results[0] is True
        assert results[1] is False

    def test_false_positive_rate_reasonable(self):
        bf = BloomFilter(self.client, "fp_test", expected_items=1000, false_positive_rate=0.01)
        for i in range(1000):
            bf.add(f"item-{i}")
        false_positives = sum(1 for i in range(1000, 2000) if bf.exists(f"item-{i}"))
        assert false_positives < 50

    def test_prefix_applied(self):
        bf = BloomFilter(self.client, "test_bf", expected_items=100, false_positive_rate=0.01)
        bf.add("item")
        keys = [k.decode() for k in self.client.keys(b"redis_kit:bloom:*")]
        assert len(keys) > 0


class TestAsyncBloomFilter:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    @pytest.mark.asyncio
    async def test_add_and_exists(self):
        bf = AsyncBloomFilter(self.client, "emails", expected_items=1000, false_positive_rate=0.01)
        await bf.add("alice@example.com")
        assert await bf.exists("alice@example.com") is True
        assert await bf.exists("unknown@example.com") is False

    @pytest.mark.asyncio
    async def test_add_many_exists_many(self):
        bf = AsyncBloomFilter(self.client, "emails", expected_items=1000, false_positive_rate=0.01)
        await bf.add_many(["a@x.com", "b@x.com"])
        results = await bf.exists_many(["a@x.com", "c@x.com"])
        assert results[0] is True
        assert results[1] is False
