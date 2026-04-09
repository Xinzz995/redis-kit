from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis.asyncio


class AsyncPubSub:
    """Async Redis PubSub wrapper with serialization and prefix support."""

    def __init__(self, client: redis.asyncio.Redis, prefix: str = "") -> None:
        self._client = client
        self._prefix = prefix
        self._pubsub = client.pubsub()
        self._handlers: dict[str, Callable] = {}

    def _make_channel(self, channel: str) -> str:
        return f"{self._prefix}:{channel}" if self._prefix else channel

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

    async def close(self) -> None:
        await self._pubsub.aclose()
