import fakeredis
import pytest
from redis_kit.stream.message import StreamMessage
from redis_kit.stream.producer import StreamProducer
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
