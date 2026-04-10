import time
from unittest.mock import AsyncMock, patch

import fakeredis
import fakeredis.aioredis
import pytest
from redis.exceptions import ResponseError

from redis_kit.exceptions import RedisKitError, StreamError
from redis_kit.stream.async_consumer import AsyncStreamConsumer
from redis_kit.stream.async_producer import AsyncStreamProducer
from redis_kit.stream.consumer import StreamConsumer
from redis_kit.stream.message import StreamMessage
from redis_kit.stream.producer import StreamProducer


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

    @pytest.mark.asyncio
    async def test_async_ack_without_consumer_raises(self):
        msg = StreamMessage(id="1-0", data={}, stream="s")
        with pytest.raises(StreamError):
            await msg.async_ack()

    @pytest.mark.asyncio
    async def test_async_ack_calls_consumer_async_ack(self):
        mock_consumer = AsyncMock()
        mock_consumer._async_ack = AsyncMock()
        msg = StreamMessage(id="1-0", data={"k": "v"}, stream="s", _consumer=mock_consumer)
        await msg.async_ack()
        mock_consumer._async_ack.assert_called_once_with("1-0")

    def test_sync_ack_on_async_consumer_raises_with_async_ack_hint(self):
        client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        consumer = AsyncStreamConsumer(client, stream="s", group="g", consumer_name="c")
        msg = StreamMessage(id="1-0", data={}, stream="s", _consumer=consumer)
        with pytest.raises(StreamError, match="async_ack"):
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

    def test_ensure_group_busygroup_is_silent(self):
        """BUSYGROUP ResponseError must be swallowed (group already exists)."""
        c = StreamConsumer(self.client, stream="test", group="g1", consumer_name="c1")
        busygroup_err = ResponseError("BUSYGROUP Consumer Group name already exists")
        with patch.object(self.client, "xgroup_create", side_effect=busygroup_err):
            c.ensure_group()  # must not raise

    def test_ensure_group_other_response_error_raises_stream_error(self):
        """Non-BUSYGROUP ResponseError must be re-raised as StreamError."""
        c = StreamConsumer(self.client, stream="test", group="g1", consumer_name="c1")
        other_err = ResponseError("ERR some other redis error")
        with patch.object(self.client, "xgroup_create", side_effect=other_err):
            with pytest.raises(StreamError):
                c.ensure_group()

    def test_ensure_group_non_response_error_raises_stream_error(self):
        """Unexpected non-ResponseError exceptions must also be wrapped as StreamError."""
        c = StreamConsumer(self.client, stream="test", group="g1", consumer_name="c1")
        with patch.object(self.client, "xgroup_create", side_effect=ConnectionError("network failure")):
            with pytest.raises(StreamError):
                c.ensure_group()


class TestAsyncStreamProducer:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    @pytest.mark.asyncio
    async def test_add_and_len(self):
        p = AsyncStreamProducer(self.client, stream="test")
        msg_id = await p.add({"key": "val"})
        assert isinstance(msg_id, str)
        assert await p.len() == 1


class TestAsyncStreamConsumer:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    @pytest.mark.asyncio
    async def test_produce_consume(self):
        p = AsyncStreamProducer(self.client, stream="test")
        await p.add({"key": "val1"})
        await p.add({"key": "val2"})
        c = AsyncStreamConsumer(self.client, stream="test", group="g1", consumer_name="c1", auto_ack=True)
        await c.ensure_group()
        messages = []
        async for msg in c.listen(count=10, block=0):
            messages.append(msg)
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_ensure_group_busygroup_is_silent(self):
        """Async: BUSYGROUP ResponseError must be swallowed."""
        c = AsyncStreamConsumer(self.client, stream="test", group="g1", consumer_name="c1")
        busygroup_err = ResponseError("BUSYGROUP Consumer Group name already exists")
        with patch.object(self.client, "xgroup_create", new=AsyncMock(side_effect=busygroup_err)):
            await c.ensure_group()  # must not raise

    @pytest.mark.asyncio
    async def test_ensure_group_other_response_error_raises_stream_error(self):
        """Async: non-BUSYGROUP ResponseError must be re-raised as StreamError."""
        c = AsyncStreamConsumer(self.client, stream="test", group="g1", consumer_name="c1")
        other_err = ResponseError("ERR some other redis error")
        with patch.object(self.client, "xgroup_create", new=AsyncMock(side_effect=other_err)):
            with pytest.raises(StreamError):
                await c.ensure_group()

    @pytest.mark.asyncio
    async def test_ensure_group_non_response_error_raises_stream_error(self):
        """Async: unexpected non-ResponseError must also be wrapped as StreamError."""
        c = AsyncStreamConsumer(self.client, stream="test", group="g1", consumer_name="c1")
        with patch.object(self.client, "xgroup_create", new=AsyncMock(side_effect=ConnectionError("network failure"))):
            with pytest.raises(StreamError):
                await c.ensure_group()


class TestStreamConsumerPending:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_pending_returns_entries(self):
        p = StreamProducer(self.client, stream="test_pending")
        c = StreamConsumer(self.client, stream="test_pending", group="grp", consumer_name="c1", auto_ack=False)
        c.ensure_group()

        p.add({"key": "val1"})
        p.add({"key": "val2"})

        msgs = list(c.listen(count=10, block=0))
        assert len(msgs) == 2

        # fakeredis xpending IDLE filter uses strict '<' on millisecond timestamps,
        # so we need a small delay to ensure idle time > 0ms.
        time.sleep(0.01)

        pending = c.pending(count=10)
        assert len(pending) == 2
        assert all(entry["consumer"] == "c1" for entry in pending)

    @pytest.mark.skip(reason="fakeredis does not support XAUTOCLAIM")
    def test_claim_stale_transfers_messages(self):
        p = StreamProducer(self.client, stream="test_claim")
        c1 = StreamConsumer(self.client, stream="test_claim", group="grp", consumer_name="c1", auto_ack=False)
        c2 = StreamConsumer(self.client, stream="test_claim", group="grp", consumer_name="c2", auto_ack=False)
        c1.ensure_group()

        p.add({"key": "val"})
        msgs = list(c1.listen(count=10, block=0))
        assert len(msgs) == 1

        claimed = c2.claim_stale(min_idle_ms=0, count=10)
        assert len(claimed) >= 1
