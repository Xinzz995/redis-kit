import fakeredis
import pytest

from redis_kit.exceptions import QueueEmptyError
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
