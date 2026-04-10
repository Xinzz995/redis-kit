from __future__ import annotations

import json
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from redis_kit.queue.async_pubsub import AsyncPubSub
from redis_kit.queue.pubsub import PubSub

# ---------------------------------------------------------------------------
# Sync PubSub
# ---------------------------------------------------------------------------


def _make_get_message_side_effect(ps: PubSub, messages: list) -> list:
    """
    Build a side_effect list for get_message that stops the listen() loop
    after all messages have been delivered.

    Each call to get_message pops the next entry from `messages`.  Once the
    list is exhausted a sentinel function is installed that calls ps.stop()
    and returns None so the loop exits cleanly.
    """
    remaining = list(messages)

    def _side_effect(**kwargs):
        if remaining:
            return remaining.pop(0)
        ps.stop()
        return None

    return _side_effect


class TestPubSub:
    @pytest.fixture()
    def mock_client(self) -> MagicMock:
        client = MagicMock()
        client.pubsub.return_value = MagicMock()
        return client

    # -- subscribe + message dispatch --

    def test_subscribe_and_dispatch(self, mock_client: MagicMock) -> None:
        ps = PubSub(mock_client, prefix="app")
        handler = MagicMock()
        ps.subscribe("chat", handler)

        ps._pubsub.get_message.side_effect = _make_get_message_side_effect(
            ps,
            [
                {
                    "type": "message",
                    "channel": b"app:chat",
                    "data": json.dumps({"msg": "hello"}).encode(),
                },
            ],
        )
        ps.listen()
        handler.assert_called_once_with({"msg": "hello"})

    # -- psubscribe + pmessage dispatch (C6 fix) --

    def test_psubscribe_dispatch(self, mock_client: MagicMock) -> None:
        ps = PubSub(mock_client, prefix="test")
        handler = MagicMock()
        ps.psubscribe("events.*", handler)

        ps._pubsub.get_message.side_effect = _make_get_message_side_effect(
            ps,
            [
                {
                    "type": "pmessage",
                    "pattern": b"test:events.*",
                    "channel": b"test:events.order.123",
                    "data": json.dumps({"key": "value"}).encode(),
                },
            ],
        )
        ps.listen()
        handler.assert_called_once_with({"key": "value"})

    # -- error isolation (I17 fix) --

    def test_listen_error_isolation(self, mock_client: MagicMock) -> None:
        """A bad message must not prevent subsequent messages from being handled."""
        ps = PubSub(mock_client, prefix="app")

        bad_handler = MagicMock(side_effect=RuntimeError("boom"))
        good_handler = MagicMock()

        ps.subscribe("bad", bad_handler)
        ps.subscribe("good", good_handler)

        ps._pubsub.get_message.side_effect = _make_get_message_side_effect(
            ps,
            [
                {
                    "type": "message",
                    "channel": b"app:bad",
                    "data": json.dumps({"x": 1}).encode(),
                },
                {
                    "type": "message",
                    "channel": b"app:good",
                    "data": json.dumps({"x": 2}).encode(),
                },
            ],
        )
        ps.listen()

        bad_handler.assert_called_once_with({"x": 1})
        good_handler.assert_called_once_with({"x": 2})

    def test_listen_error_logs_exception(self, mock_client: MagicMock) -> None:
        """Handler errors must be logged via _logger.exception."""
        ps = PubSub(mock_client, prefix="app")
        ps.subscribe("ch", MagicMock(side_effect=RuntimeError("boom")))

        ps._pubsub.get_message.side_effect = _make_get_message_side_effect(
            ps,
            [
                {
                    "type": "message",
                    "channel": b"app:ch",
                    "data": json.dumps({"x": 1}).encode(),
                },
            ],
        )
        with patch("redis_kit.queue.pubsub._logger") as mock_logger:
            ps.listen()
            mock_logger.exception.assert_called_once_with("Error in PubSub listener")

    def test_listen_invalid_json_isolation(self, mock_client: MagicMock) -> None:
        """Invalid JSON in one message must not kill the loop."""
        ps = PubSub(mock_client, prefix="app")
        handler = MagicMock()
        ps.subscribe("ch", handler)

        ps._pubsub.get_message.side_effect = _make_get_message_side_effect(
            ps,
            [
                {
                    "type": "message",
                    "channel": b"app:ch",
                    "data": b"NOT-JSON",
                },
                {
                    "type": "message",
                    "channel": b"app:ch",
                    "data": json.dumps({"ok": True}).encode(),
                },
            ],
        )
        ps.listen()

        # Second message should still arrive
        handler.assert_called_once_with({"ok": True})

    # -- publish --

    def test_publish(self, mock_client: MagicMock) -> None:
        ps = PubSub(mock_client, prefix="app")
        ps.publish("chat", {"msg": "hi"})

        mock_client.publish.assert_called_once_with(
            "app:chat",
            json.dumps({"msg": "hi"}).encode("utf-8"),
        )

    # -- no prefix --

    def test_no_prefix(self, mock_client: MagicMock) -> None:
        ps = PubSub(mock_client, prefix="")
        handler = MagicMock()
        ps.subscribe("raw", handler)

        ps._pubsub.get_message.side_effect = _make_get_message_side_effect(
            ps,
            [
                {
                    "type": "message",
                    "channel": b"raw",
                    "data": json.dumps(42).encode(),
                },
            ],
        )
        ps.listen()
        handler.assert_called_once_with(42)

    # -- unsubscribe --

    def test_unsubscribe(self, mock_client: MagicMock) -> None:
        ps = PubSub(mock_client, prefix="app")
        handler = MagicMock()
        ps.subscribe("ch", handler)
        ps.unsubscribe("ch")

        ps._pubsub.get_message.side_effect = _make_get_message_side_effect(
            ps,
            [
                {
                    "type": "message",
                    "channel": b"app:ch",
                    "data": json.dumps({"x": 1}).encode(),
                },
            ],
        )
        ps.listen()
        handler.assert_not_called()

    # -- ignored message types --

    def test_non_message_types_ignored(self, mock_client: MagicMock) -> None:
        ps = PubSub(mock_client, prefix="app")
        handler = MagicMock()
        ps.subscribe("ch", handler)

        ps._pubsub.get_message.side_effect = _make_get_message_side_effect(
            ps,
            [
                {"type": "subscribe", "channel": b"app:ch", "data": 1},
            ],
        )
        ps.listen()
        handler.assert_not_called()

    # -- graceful stop --

    def test_stop_exits_listen_thread(self, mock_client: MagicMock) -> None:
        """stop() must cause listen() running in a background thread to exit."""
        ps = PubSub(mock_client, prefix="app")

        # get_message always returns None (no messages), so the loop just polls.
        ps._pubsub.get_message.return_value = None

        thread = threading.Thread(target=ps.listen, daemon=True)
        thread.start()

        # Give the thread a moment to enter the loop.
        time.sleep(0.05)
        ps.stop()

        thread.join(timeout=2.0)
        assert not thread.is_alive(), "listen() did not stop after stop() was called"

    def test_stop_sets_running_false(self, mock_client: MagicMock) -> None:
        """stop() must set _running to False."""
        ps = PubSub(mock_client, prefix="app")
        assert ps._running is True
        ps.stop()
        assert ps._running is False

    def test_close_sets_running_false(self, mock_client: MagicMock) -> None:
        """close() must set _running to False and close the underlying pubsub."""
        ps = PubSub(mock_client, prefix="app")
        ps.close()
        assert ps._running is False
        ps._pubsub.close.assert_called_once()

    def test_listen_passes_timeout_to_get_message(self, mock_client: MagicMock) -> None:
        """listen(timeout=N) must pass timeout=N to get_message()."""
        ps = PubSub(mock_client, prefix="app")

        call_count = [0]

        def _side_effect(**kwargs):
            call_count[0] += 1
            ps.stop()
            return None

        ps._pubsub.get_message.side_effect = _side_effect
        ps.listen(timeout=5.0)

        ps._pubsub.get_message.assert_called_with(ignore_subscribe_messages=True, timeout=5.0)


# ---------------------------------------------------------------------------
# Async PubSub
# ---------------------------------------------------------------------------


def _make_async_get_message_side_effect(ps: AsyncPubSub, messages: list):
    """
    Build an async side_effect for get_message that stops the listen() loop
    after all messages have been delivered.
    """
    remaining = list(messages)

    async def _side_effect(**kwargs):
        if remaining:
            return remaining.pop(0)
        ps.stop()
        return None

    return _side_effect


class TestAsyncPubSub:
    @pytest.fixture()
    def mock_client(self) -> MagicMock:
        # client.pubsub() is called synchronously in __init__, so the client
        # must be a MagicMock.  The returned pubsub object needs async methods.
        mock_ps = MagicMock()
        mock_ps.subscribe = AsyncMock()
        mock_ps.psubscribe = AsyncMock()
        mock_ps.unsubscribe = AsyncMock()
        mock_ps.aclose = AsyncMock()
        mock_ps.get_message = AsyncMock()

        client = MagicMock()
        client.pubsub.return_value = mock_ps
        client.publish = AsyncMock()
        return client

    async def test_subscribe_and_dispatch(self, mock_client: MagicMock) -> None:
        ps = AsyncPubSub(mock_client, prefix="app")
        handler = MagicMock()
        await ps.subscribe("chat", handler)

        ps._pubsub.get_message.side_effect = _make_async_get_message_side_effect(
            ps,
            [
                {
                    "type": "message",
                    "channel": b"app:chat",
                    "data": json.dumps({"msg": "hello"}).encode(),
                },
            ],
        )
        await ps.listen()
        handler.assert_called_once_with({"msg": "hello"})

    async def test_psubscribe_dispatch(self, mock_client: MagicMock) -> None:
        ps = AsyncPubSub(mock_client, prefix="test")
        handler = MagicMock()
        await ps.psubscribe("events.*", handler)

        ps._pubsub.get_message.side_effect = _make_async_get_message_side_effect(
            ps,
            [
                {
                    "type": "pmessage",
                    "pattern": b"test:events.*",
                    "channel": b"test:events.order.123",
                    "data": json.dumps({"key": "value"}).encode(),
                },
            ],
        )
        await ps.listen()
        handler.assert_called_once_with({"key": "value"})

    async def test_listen_error_isolation(self, mock_client: MagicMock) -> None:
        ps = AsyncPubSub(mock_client, prefix="app")

        bad_handler = MagicMock(side_effect=RuntimeError("boom"))
        good_handler = MagicMock()

        await ps.subscribe("bad", bad_handler)
        await ps.subscribe("good", good_handler)

        ps._pubsub.get_message.side_effect = _make_async_get_message_side_effect(
            ps,
            [
                {
                    "type": "message",
                    "channel": b"app:bad",
                    "data": json.dumps({"x": 1}).encode(),
                },
                {
                    "type": "message",
                    "channel": b"app:good",
                    "data": json.dumps({"x": 2}).encode(),
                },
            ],
        )
        await ps.listen()

        bad_handler.assert_called_once_with({"x": 1})
        good_handler.assert_called_once_with({"x": 2})

    async def test_listen_error_logs_exception(self, mock_client: MagicMock) -> None:
        """Handler errors must be logged via _logger.exception."""
        ps = AsyncPubSub(mock_client, prefix="app")
        await ps.subscribe("ch", MagicMock(side_effect=RuntimeError("boom")))

        ps._pubsub.get_message.side_effect = _make_async_get_message_side_effect(
            ps,
            [
                {
                    "type": "message",
                    "channel": b"app:ch",
                    "data": json.dumps({"x": 1}).encode(),
                },
            ],
        )
        with patch("redis_kit.queue.async_pubsub._logger") as mock_logger:
            await ps.listen()
            mock_logger.exception.assert_called_once_with("Error in PubSub listener")

    async def test_publish(self, mock_client: MagicMock) -> None:
        ps = AsyncPubSub(mock_client, prefix="app")
        await ps.publish("chat", {"msg": "hi"})

        mock_client.publish.assert_awaited_once_with(
            "app:chat",
            json.dumps({"msg": "hi"}).encode("utf-8"),
        )

    # -- graceful stop --

    async def test_stop_sets_running_false(self, mock_client: MagicMock) -> None:
        """stop() must set _running to False."""
        ps = AsyncPubSub(mock_client, prefix="app")
        assert ps._running is True
        ps.stop()
        assert ps._running is False

    async def test_close_sets_running_false(self, mock_client: MagicMock) -> None:
        """close() must set _running to False and close the underlying pubsub."""
        ps = AsyncPubSub(mock_client, prefix="app")
        await ps.close()
        assert ps._running is False
        mock_client.pubsub.return_value.aclose.assert_awaited_once()

    async def test_listen_passes_timeout_to_get_message(self, mock_client: MagicMock) -> None:
        """listen(timeout=N) must pass timeout=N to get_message()."""
        ps = AsyncPubSub(mock_client, prefix="app")

        async def _side_effect(**kwargs):
            ps.stop()
            return None

        ps._pubsub.get_message.side_effect = _side_effect
        await ps.listen(timeout=3.0)

        ps._pubsub.get_message.assert_awaited_with(ignore_subscribe_messages=True, timeout=3.0)
