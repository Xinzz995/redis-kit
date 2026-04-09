import fakeredis
import fakeredis.aioredis
import pytest

from redis_kit.counter.async_counter import AsyncCounter, AsyncIDGenerator
from redis_kit.counter.counter import Counter, IDGenerator


class TestCounter:
    def setup_method(self, method):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self, method):
        self.client.flushall()
        self.client.close()

    def _make_counter(self, prefix="test:counter"):
        return Counter(self.client, prefix=prefix)

    def test_incr_default(self):
        c = self._make_counter()
        assert c.incr("views") == 1

    def test_incr_by_amount(self):
        c = self._make_counter()
        assert c.incr("views", 5) == 5

    def test_incr_accumulates(self):
        c = self._make_counter()
        c.incr("views")
        c.incr("views")
        assert c.get("views") == 2

    def test_decr(self):
        c = self._make_counter()
        c.incr("views", 10)
        assert c.decr("views") == 9

    def test_decr_by_amount(self):
        c = self._make_counter()
        c.incr("views", 10)
        assert c.decr("views", 3) == 7

    def test_get_nonexistent(self):
        c = self._make_counter()
        assert c.get("nonexistent") == 0

    def test_reset(self):
        c = self._make_counter()
        c.incr("views", 10)
        c.reset("views")
        assert c.get("views") == 0

    def test_prefix_applied(self):
        c = self._make_counter(prefix="myapp")
        c.incr("views")
        assert self.client.exists(b"myapp:views")

    def test_bind(self):
        c = self._make_counter()
        bound = c.bind("views")
        bound.incr()
        bound.incr(5)
        assert bound.get() == 6
        bound.reset()
        assert bound.get() == 0


class TestIDGenerator:
    def setup_method(self, method):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self, method):
        self.client.flushall()
        self.client.close()

    def test_next_returns_int(self):
        gen = IDGenerator(self.client, "order_id")
        assert gen.next() == 1
        assert gen.next() == 2

    def test_next_str_zero_padded(self):
        gen = IDGenerator(self.client, "order_id", padding=6)
        assert gen.next_str() == "000001"

    def test_next_str_with_prefix(self):
        gen = IDGenerator(self.client, "order_id", prefix="ORD", padding=8)
        assert gen.next_str() == "ORD00000001"

    def test_sequential(self):
        gen = IDGenerator(self.client, "seq")
        ids = [gen.next() for _ in range(5)]
        assert ids == [1, 2, 3, 4, 5]


class TestAsyncCounter:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    @pytest.mark.asyncio
    async def test_incr(self):
        c = AsyncCounter(self.client, prefix="test")
        assert await c.incr("views") == 1

    @pytest.mark.asyncio
    async def test_get(self):
        c = AsyncCounter(self.client, prefix="test")
        await c.incr("views", 5)
        assert await c.get("views") == 5

    @pytest.mark.asyncio
    async def test_bind(self):
        c = AsyncCounter(self.client, prefix="test")
        bound = c.bind("views")
        await bound.incr(3)
        assert await bound.get() == 3
        await bound.reset()
        assert await bound.get() == 0


class TestAsyncIDGenerator:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    @pytest.mark.asyncio
    async def test_next(self):
        gen = AsyncIDGenerator(self.client, "order")
        assert await gen.next() == 1
        assert await gen.next() == 2

    @pytest.mark.asyncio
    async def test_next_str(self):
        gen = AsyncIDGenerator(self.client, "order", prefix="ORD", padding=6)
        assert await gen.next_str() == "ORD000001"
