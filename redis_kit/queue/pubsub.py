from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from redis_kit.queue._base import MSG_TYPES as _MSG_TYPES
from redis_kit.queue._base import PubSubBase

if TYPE_CHECKING:
    import redis

_logger = logging.getLogger("redis_kit")


class PubSub(PubSubBase):
    """Redis PubSub wrapper with serialization and prefix support."""

    def __init__(self, client: redis.Redis, prefix: str = "") -> None:
        super().__init__(client, prefix)
        self._pubsub = client.pubsub()
        self._running = threading.Event()
        self._running.set()

    def publish(self, channel: str, data: Any) -> int:
        payload = json.dumps(data).encode("utf-8")
        return self._client.publish(self._make_channel(channel), payload)

    def subscribe(self, channel: str, handler: Callable[[Any], None]) -> None:
        full_channel = self._make_channel(channel)
        self._handlers[full_channel] = handler
        self._pubsub.subscribe(full_channel)

    def psubscribe(self, pattern: str, handler: Callable[[Any], None]) -> None:
        full_pattern = self._make_channel(pattern)
        self._handlers[full_pattern] = handler
        self._pubsub.psubscribe(full_pattern)

    def unsubscribe(self, channel: str) -> None:
        full_channel = self._make_channel(channel)
        self._pubsub.unsubscribe(full_channel)
        self._handlers.pop(full_channel, None)

    def listen(self, timeout: float | None = None) -> None:
        self._running.set()
        while self._running.is_set():
            message = self._pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout or 0.1)
            if message is None:
                continue
            if message["type"] in _MSG_TYPES:
                try:
                    if message["type"] == "pmessage":
                        lookup_key = message.get("pattern", b"")
                    else:
                        lookup_key = message.get("channel", b"")
                    if isinstance(lookup_key, bytes):
                        lookup_key = lookup_key.decode()
                    handler = self._handlers.get(lookup_key)
                    if handler:
                        data = json.loads(message["data"])
                        handler(data)
                except Exception:
                    _logger.exception("Error in PubSub listener")

    def stop(self) -> None:
        """Signal listen() to stop after the current poll cycle."""
        self._running.clear()

    def close(self) -> None:
        self._running.clear()
        self._pubsub.close()
