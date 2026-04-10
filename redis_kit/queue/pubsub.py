from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis

_logger = logging.getLogger("redis_kit")


class PubSub:
    """Redis PubSub wrapper with serialization and prefix support."""

    def __init__(self, client: redis.Redis, prefix: str = "") -> None:
        self._client = client
        self._prefix = prefix
        self._pubsub = client.pubsub()
        self._handlers: dict[str, Callable] = {}
        self._running: bool = True

    def _make_channel(self, channel: str) -> str:
        return f"{self._prefix}:{channel}" if self._prefix else channel

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
        self._running = True
        while self._running:
            message = self._pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout or 0.1)
            if message is None:
                continue
            if message["type"] in ("message", "pmessage"):
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
        self._running = False

    def close(self) -> None:
        self._running = False
        self._pubsub.close()
