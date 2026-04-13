import fakeredis
import fakeredis.aioredis
import pytest

from redis_kit.exceptions import QueueEmptyError
from redis_kit.queue.async_reliable_queue import AsyncReliableQueue
from redis_kit.queue.reliable_queue import ReliableQueue


class TestReliableQueue:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_put_and_get(self):
        rq = ReliableQueue(self.client, "tasks")
        rq.put({"task": "send_email"})
        msg = rq.get()
        assert msg.data == {"task": "send_email"}

    def test_ack_removes_from_processing(self):
        rq = ReliableQueue(self.client, "tasks")
        rq.put({"task": "a"})
        msg = rq.get()
        assert rq.processing_count() == 1
        msg.ack()
        assert rq.processing_count() == 0

    def test_nack_returns_to_queue(self):
        rq = ReliableQueue(self.client, "tasks")
        rq.put({"task": "a"})
        msg = rq.get()
        msg.nack()
        assert rq.size() == 1
        assert rq.processing_count() == 0

    def test_get_empty_raises(self):
        rq = ReliableQueue(self.client, "tasks")
        with pytest.raises(QueueEmptyError):
            rq.get()

    def test_fifo_order(self):
        rq = ReliableQueue(self.client, "tasks")
        rq.put({"n": 1})
        rq.put({"n": 2})
        rq.put({"n": 3})
        assert rq.get().data == {"n": 1}
        assert rq.get().data == {"n": 2}
        assert rq.get().data == {"n": 3}


class TestRecoverStale:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_recover_stale_moves_processing_back_to_queue(self):
        rq = ReliableQueue(self.client, "tasks")
        rq.put({"task": "a"})
        rq.put({"task": "b"})
        # Simulate consumer crash: get messages but never ack
        rq.get()
        rq.get()
        assert rq.size() == 0
        assert rq.processing_count() == 2

        recovered = rq.recover_stale()
        assert recovered == 2
        assert rq.size() == 2
        assert rq.processing_count() == 0

    def test_recover_stale_empty_processing(self):
        rq = ReliableQueue(self.client, "tasks")
        assert rq.recover_stale() == 0

    def test_recover_stale_respects_max_items(self):
        rq = ReliableQueue(self.client, "tasks")
        for i in range(5):
            rq.put({"task": i})
        for _ in range(5):
            rq.get()
        recovered = rq.recover_stale(max_items=3)
        assert recovered == 3
        assert rq.size() == 3
        assert rq.processing_count() == 2

    def test_recovered_messages_are_consumable(self):
        rq = ReliableQueue(self.client, "tasks")
        rq.put({"task": "important"})
        rq.get()  # Don't ack — simulate crash
        rq.recover_stale()
        msg = rq.get()
        assert msg.data == {"task": "important"}
        msg.ack()
        assert rq.processing_count() == 0


class TestAsyncRecoverStale:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    @pytest.mark.asyncio
    async def test_recover_stale_moves_processing_back(self):
        rq = AsyncReliableQueue(self.client, "tasks")
        await rq.put({"task": "a"})
        await rq.put({"task": "b"})
        await rq.get()
        await rq.get()
        assert await rq.processing_count() == 2

        recovered = await rq.recover_stale()
        assert recovered == 2
        assert await rq.size() == 2
        assert await rq.processing_count() == 0

    @pytest.mark.asyncio
    async def test_recover_stale_empty(self):
        rq = AsyncReliableQueue(self.client, "tasks")
        assert await rq.recover_stale() == 0

    @pytest.mark.asyncio
    async def test_recover_stale_max_items(self):
        rq = AsyncReliableQueue(self.client, "tasks")
        for i in range(5):
            await rq.put({"task": i})
        for _ in range(5):
            await rq.get()
        recovered = await rq.recover_stale(max_items=2)
        assert recovered == 2
        assert await rq.size() == 2
        assert await rq.processing_count() == 3


class TestAsyncReliableQueue:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    @pytest.mark.asyncio
    async def test_put_and_get(self):
        rq = AsyncReliableQueue(self.client, "tasks")
        await rq.put({"task": "email"})
        msg = await rq.get()
        assert msg.data == {"task": "email"}

    @pytest.mark.asyncio
    async def test_get_empty_raises(self):
        rq = AsyncReliableQueue(self.client, "tasks")
        with pytest.raises(QueueEmptyError):
            await rq.get()

    @pytest.mark.asyncio
    async def test_size(self):
        rq = AsyncReliableQueue(self.client, "tasks")
        await rq.put({"a": 1})
        assert await rq.size() == 1
        assert await rq.processing_count() == 0

    @pytest.mark.asyncio
    async def test_ack(self):
        rq = AsyncReliableQueue(self.client, "tasks")
        await rq.put("ack_data")
        msg = await rq.get()
        assert await rq.processing_count() == 1
        await msg.ack()
        assert await rq.processing_count() == 0

    @pytest.mark.asyncio
    async def test_nack_requeues(self):
        rq = AsyncReliableQueue(self.client, "tasks")
        await rq.put("nack_data")
        msg = await rq.get()
        assert await rq.size() == 0
        await msg.nack()
        assert await rq.size() == 1
        assert await rq.processing_count() == 0
