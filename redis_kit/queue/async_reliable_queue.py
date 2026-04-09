from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from redis_kit.exceptions import QueueEmptyError

if TYPE_CHECKING:
    import redis.asyncio


@dataclass
class AsyncMessage:
    """An async message from a ReliableQueue with ack/nack support."""

    id: str
    data: Any
    _queue: AsyncReliableQueue

    async def ack(self) -> None:
        await self._queue._ack(self.id)

    async def nack(self) -> None:
        await self._queue._nack(self.id, self.data)


class AsyncReliableQueue:
    """Async Redis-backed reliable queue with ack/nack support."""

    def __init__(self, client: redis.asyncio.Redis, name: str, prefix: str = "") -> None:
        self._client = client
        base = f"{prefix}:{name}" if prefix else name
        self._queue_key = f"{base}:queue"
        self._processing_key = f"{base}:processing"

    async def put(self, data: Any) -> None:
        msg_id = uuid.uuid4().hex[:12]
        payload = json.dumps({"id": msg_id, "data": data}).encode("utf-8")
        await self._client.lpush(self._queue_key, payload)

    async def get(self, timeout: int = 0) -> AsyncMessage:
        if timeout > 0:
            result = await self._client.blmove(self._queue_key, self._processing_key, timeout, "RIGHT", "LEFT")
        else:
            result = await self._client.lmove(self._queue_key, self._processing_key, "RIGHT", "LEFT")
        if result is None:
            raise QueueEmptyError("Queue is empty")
        msg = json.loads(result)
        return AsyncMessage(id=msg["id"], data=msg["data"], _queue=self)

    async def _ack(self, msg_id: str) -> None:
        items = await self._client.lrange(self._processing_key, 0, -1)
        for item in items:
            msg = json.loads(item)
            if msg["id"] == msg_id:
                await self._client.lrem(self._processing_key, 1, item)
                return

    async def _nack(self, msg_id: str, data: Any) -> None:
        await self._ack(msg_id)
        await self.put(data)

    async def size(self) -> int:
        return await self._client.llen(self._queue_key)

    async def processing_count(self) -> int:
        return await self._client.llen(self._processing_key)
