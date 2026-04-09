from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from redis_kit.queue.async_pubsub import AsyncPubSub
from redis_kit.queue.pubsub import PubSub

# ---------------------------------------------------------------------------
# Sync PubSub
# ---------------------------------------------------------------------------


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

        ps._pubsub.listen.return_value = [
            {
                "type": "message",
                "channel": b"app:chat",
                "data": json.dumps({"msg": "hello"}).encode(),
            },
        ]
        ps.listen()
        handler.assert_called_once_with({"msg": "hello"})

    # -- psubscribe + pmessage dispatch (C6 fix) --

    def test_psubscribe_dispatch(self, mock_client: MagicMock) -> None:
        ps = PubSub(mock_client, prefix="test")
        handler = MagicMock()
        ps.psubscribe("events.*", handler)

        ps._pubsub.listen.return_value = [
            {
                "type": "pmessage",
                "pattern": b"test:events.*",
                "channel": b"test:events.order.123",
                "data": json.dumps({"key": "value"}).encode(),
            },
        ]
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

        ps._pubsub.listen.return_value = [
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
        ]
        ps.listen()

        bad_handler.assert_called_once_with({"x": 1})
        good_handler.assert_called_once_with({"x": 2})

    def test_listen_invalid_json_isolation(self, mock_client: MagicMock) -> None:
        """Invalid JSON in one message must not kill the loop."""
        ps = PubSub(mock_client, prefix="app")
        handler = MagicMock()
        ps.subscribe("ch", handler)

        ps._pubsub.listen.return_value = [
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
        ]
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

        ps._pubsub.listen.return_value = [
            {
                "type": "message",
                "channel": b"raw",
                "data": json.dumps(42).encode(),
            },
        ]
        ps.listen()
        handler.assert_called_once_with(42)

    # -- unsubscribe --

    def test_unsubscribe(self, mock_client: MagicMock) -> None:
        ps = PubSub(mock_client, prefix="app")
        handler = MagicMock()
        ps.subscribe("ch", handler)
        ps.unsubscribe("ch")

        ps._pubsub.listen.return_value = [
            {
                "type": "message",
                "channel": b"app:ch",
                "data": json.dumps({"x": 1}).encode(),
            },
        ]
        ps.listen()
        handler.assert_not_called()

    # -- ignored message types --

    def test_non_message_types_ignored(self, mock_client: MagicMock) -> None:
        ps = PubSub(mock_client, prefix="app")
        handler = MagicMock()
        ps.subscribe("ch", handler)

        ps._pubsub.listen.return_value = [
            {"type": "subscribe", "channel": b"app:ch", "data": 1},
        ]
        ps.listen()
        handler.assert_not_called()


# ---------------------------------------------------------------------------
# Async PubSub
# ---------------------------------------------------------------------------


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

        client = MagicMock()
        client.pubsub.return_value = mock_ps
        client.publish = AsyncMock()
        return client

    async def test_subscribe_and_dispatch(self, mock_client: MagicMock) -> None:
        ps = AsyncPubSub(mock_client, prefix="app")
        handler = MagicMock()
        await ps.subscribe("chat", handler)

        async def _messages():
            yield {
                "type": "message",
                "channel": b"app:chat",
                "data": json.dumps({"msg": "hello"}).encode(),
            }

        ps._pubsub.listen.return_value = _messages()
        await ps.listen()
        handler.assert_called_once_with({"msg": "hello"})

    async def test_psubscribe_dispatch(self, mock_client: MagicMock) -> None:
        ps = AsyncPubSub(mock_client, prefix="test")
        handler = MagicMock()
        await ps.psubscribe("events.*", handler)

        async def _messages():
            yield {
                "type": "pmessage",
                "pattern": b"test:events.*",
                "channel": b"test:events.order.123",
                "data": json.dumps({"key": "value"}).encode(),
            }

        ps._pubsub.listen.return_value = _messages()
        await ps.listen()
        handler.assert_called_once_with({"key": "value"})

    async def test_listen_error_isolation(self, mock_client: MagicMock) -> None:
        ps = AsyncPubSub(mock_client, prefix="app")

        bad_handler = MagicMock(side_effect=RuntimeError("boom"))
        good_handler = MagicMock()

        await ps.subscribe("bad", bad_handler)
        await ps.subscribe("good", good_handler)

        async def _messages():
            yield {
                "type": "message",
                "channel": b"app:bad",
                "data": json.dumps({"x": 1}).encode(),
            }
            yield {
                "type": "message",
                "channel": b"app:good",
                "data": json.dumps({"x": 2}).encode(),
            }

        ps._pubsub.listen.return_value = _messages()
        await ps.listen()

        bad_handler.assert_called_once_with({"x": 1})
        good_handler.assert_called_once_with({"x": 2})

    async def test_publish(self, mock_client: MagicMock) -> None:
        ps = AsyncPubSub(mock_client, prefix="app")
        await ps.publish("chat", {"msg": "hi"})

        mock_client.publish.assert_awaited_once_with(
            "app:chat",
            json.dumps({"msg": "hi"}).encode("utf-8"),
        )
