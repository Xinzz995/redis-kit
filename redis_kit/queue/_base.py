from __future__ import annotations

import json
import uuid
from typing import Any

from redis_kit.queue._lua import NACK_SCRIPT, POLL_SCRIPT, PUT_SCRIPT


def _encode_message(data: Any) -> bytes:
    """Encode data into a JSON message with a random ID."""
    msg_id = uuid.uuid4().hex[:12]
    return json.dumps({"id": msg_id, "data": data}).encode("utf-8")


class ReliableQueueBase:
    """Shared logic for sync and async ReliableQueue."""

    def __init__(self, client: Any, name: str, prefix: str = "") -> None:
        self._client = client
        base = f"{prefix}:{name}" if prefix else name
        self._queue_key = f"{base}:queue"
        self._processing_key = f"{base}:processing"
        self._nack_script = self._client.register_script(NACK_SCRIPT)

    _encode_message = staticmethod(_encode_message)


class DelayQueueBase:
    """Shared logic for sync and async DelayQueue."""

    def __init__(self, client: Any, name: str, prefix: str = "") -> None:
        self._client = client
        self._key = f"{prefix}:{name}" if prefix else name
        self._poll_script = self._client.register_script(POLL_SCRIPT)
        self._put_script = self._client.register_script(PUT_SCRIPT)

    _encode_message = staticmethod(_encode_message)

    @staticmethod
    def _decode_poll_results(results: list) -> list[Any]:
        items: list[Any] = []
        for r in results:
            msg = json.loads(r)
            items.append(msg["data"] if isinstance(msg, dict) and "data" in msg else msg)
        return items


class PubSubBase:
    """Shared logic for sync and async PubSub."""

    def __init__(self, client: Any, prefix: str = "") -> None:
        self._client = client
        self._prefix = prefix
        self._handlers: dict[str, Any] = {}

    def _make_channel(self, channel: str) -> str:
        return f"{self._prefix}:{channel}" if self._prefix else channel


MSG_TYPES = frozenset({"message", "pmessage"})
