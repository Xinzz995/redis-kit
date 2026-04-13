from __future__ import annotations

import inspect
import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from redis_kit.queue._base import PubSubBase

if TYPE_CHECKING:
    import redis.asyncio

_logger = logging.getLogger("redis_kit")
_MSG_TYPES = frozenset({"message", "pmessage"})


class AsyncPubSub(PubSubBase):
    """Async Redis PubSub wrapper with serialization and prefix support."""

    def __init__(self, client: redis.asyncio.Redis, prefix: str = "") -> None:
        super().__init__(client, prefix)
        self._pubsub = client.pubsub()
        self._running: bool = True

    async def publish(self, channel: str, data: Any) -> int:
        payload = json.dumps(data).encode("utf-8")
        return await self._client.publish(self._make_channel(channel), payload)

    async def subscribe(self, channel: str, handler: Callable[[Any], None]) -> None:
        full_channel = self._make_channel(channel)
        self._handlers[full_channel] = handler
        await self._pubsub.subscribe(full_channel)

    async def psubscribe(self, pattern: str, handler: Callable[[Any], None]) -> None:
        full_pattern = self._make_channel(pattern)
        self._handlers[full_pattern] = handler
        await self._pubsub.psubscribe(full_pattern)

    async def unsubscribe(self, channel: str) -> None:
        full_channel = self._make_channel(channel)
        await self._pubsub.unsubscribe(full_channel)
        self._handlers.pop(full_channel, None)

    async def listen(self, timeout: float | None = None) -> None:
        self._running = True
        while self._running:
            message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout or 0.1)
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
                        result = handler(data)
                        if inspect.isawaitable(result):
                            await result
                except Exception:
                    _logger.exception("Error in PubSub listener")

    def stop(self) -> None:
        """Signal listen() to stop after the current poll cycle."""
        self._running = False

    async def close(self) -> None:
        self._running = False
        await self._pubsub.aclose()
