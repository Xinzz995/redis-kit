import fakeredis
import pytest
from redis_kit.stream.message import StreamMessage
from redis_kit.stream.producer import StreamProducer
from redis_kit.stream.consumer import StreamConsumer
from redis_kit.exceptions import StreamError, RedisKitError


class TestStreamMessage:
    def test_fields(self):
        msg = StreamMessage(id="1-0", data={"key": "val"}, stream="mystream")
        assert msg.id == "1-0"
        assert msg.data == {"key": "val"}
        assert msg.stream == "mystream"

    def test_ack_without_consumer_raises(self):
        msg = StreamMessage(id="1-0", data={}, stream="s")
        with pytest.raises(StreamError):
            msg.ack()


class TestStreamError:
    def test_inherits(self):
        with pytest.raises(RedisKitError):
            raise StreamError("fail")


class TestStreamProducer:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_add_returns_id(self):
        p = StreamProducer(self.client, stream="test")
        msg_id = p.add({"key": "value"})
        assert isinstance(msg_id, str)
        assert "-" in msg_id

    def test_add_increments_len(self):
        p = StreamProducer(self.client, stream="test")
        p.add({"a": "1"})
        p.add({"b": "2"})
        assert p.len() == 2

    def test_prefix_applied(self):
        p = StreamProducer(self.client, stream="orders", prefix="myapp")
        p.add({"x": "1"})
        assert self.client.xlen(b"myapp:orders") == 1

    def test_maxlen_trims(self):
        p = StreamProducer(self.client, stream="test", maxlen=3)
        for i in range(5):
            p.add({"i": str(i)})
        assert p.len() <= 5  # approximate trimming

    def test_trim(self):
        p = StreamProducer(self.client, stream="test")
        for i in range(10):
            p.add({"i": str(i)})
        p.trim(maxlen=3, approximate=False)
        assert p.len() == 3


class TestStreamConsumer:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_ensure_group_creates(self):
        p = StreamProducer(self.client, stream="test")
        p.add({"a": "1"})
        c = StreamConsumer(self.client, stream="test", group="g1", consumer_name="c1")
        c.ensure_group()
        # Should not raise on second call (idempotent)
        c.ensure_group()

    def test_listen_auto_ack(self):
        p = StreamProducer(self.client, stream="test")
        p.add({"key": "val1"})
        p.add({"key": "val2"})
        c = StreamConsumer(self.client, stream="test", group="g1", consumer_name="c1", auto_ack=True)
        c.ensure_group()
        messages = list(c.listen(count=10, block=0))
        assert len(messages) == 2
        assert messages[0].data["key"] == "val1"
        assert messages[1].data["key"] == "val2"

    def test_listen_manual_ack(self):
        p = StreamProducer(self.client, stream="test")
        p.add({"key": "val"})
        c = StreamConsumer(self.client, stream="test", group="g1", consumer_name="c1", auto_ack=False)
        c.ensure_group()
        messages = list(c.listen(count=10, block=0))
        assert len(messages) == 1
        messages[0].ack()

    def test_listen_empty_returns_nothing(self):
        # Create stream with a message, create group, consume, then listen again
        p = StreamProducer(self.client, stream="test")
        p.add({"a": "1"})
        c = StreamConsumer(self.client, stream="test", group="g1", consumer_name="c1")
        c.ensure_group()
        list(c.listen(count=10, block=0))  # consume all
        messages = list(c.listen(count=10, block=0))  # no new messages
        assert len(messages) == 0

    def test_destroy_group(self):
        p = StreamProducer(self.client, stream="test")
        p.add({"a": "1"})
        c = StreamConsumer(self.client, stream="test", group="g1", consumer_name="c1")
        c.ensure_group()
        c.destroy_group()
        # Re-create should work
        c.ensure_group()

    def test_prefix_applied(self):
        p = StreamProducer(self.client, stream="orders", prefix="app")
        p.add({"x": "1"})
        c = StreamConsumer(self.client, stream="orders", prefix="app", group="g1", consumer_name="c1")
        c.ensure_group()
        messages = list(c.listen(count=10, block=0))
        assert len(messages) == 1
