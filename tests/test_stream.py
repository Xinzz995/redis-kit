import pytest
from redis_kit.stream.message import StreamMessage
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
