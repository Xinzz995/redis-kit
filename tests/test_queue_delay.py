import fakeredis
import fakeredis.aioredis
import pytest

from redis_kit.queue.async_delay_queue import AsyncDelayQueue
from redis_kit.queue.delay_queue import DelayQueue


class TestDelayQueue:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_put_and_poll(self):
        dq = DelayQueue(self.client, "tasks")
        dq.put({"order_id": 123}, delay=0)
        results = dq.poll(count=10)
        assert len(results) == 1
        assert results[0] == {"order_id": 123}

    def test_delayed_not_ready(self):
        dq = DelayQueue(self.client, "tasks")
        dq.put({"order_id": 123}, delay=9999)
        results = dq.poll(count=10)
        assert len(results) == 0

    def test_size(self):
        dq = DelayQueue(self.client, "tasks")
        dq.put({"a": 1}, delay=0)
        dq.put({"b": 2}, delay=0)
        assert dq.size() == 2

    def test_poll_removes_items(self):
        dq = DelayQueue(self.client, "tasks")
        dq.put({"a": 1}, delay=0)
        dq.poll(count=10)
        assert dq.size() == 0


class TestAsyncDelayQueue:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    @pytest.mark.asyncio
    async def test_put_and_poll(self):
        dq = AsyncDelayQueue(self.client, "tasks")
        await dq.put({"task": "test"}, delay=0)
        results = await dq.poll(count=10)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_size(self):
        dq = AsyncDelayQueue(self.client, "tasks")
        await dq.put({"a": 1}, delay=0)
        assert await dq.size() == 1
