from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from redis_kit.exceptions import QueueEmptyError
from redis_kit.queue._base import ReliableQueueBase

if TYPE_CHECKING:
    pass


@dataclass
class AsyncMessage:
    """An async message from a ReliableQueue with ack/nack support."""

    id: str
    data: Any
    _queue: AsyncReliableQueue
    _raw: bytes

    async def ack(self) -> None:
        await self._queue._ack(self._raw)

    async def nack(self) -> None:
        await self._queue._nack(self._raw, self.id, self.data)


class AsyncReliableQueue(ReliableQueueBase):
    """Async Redis-backed reliable queue with ack/nack support."""

    async def put(self, data: Any) -> None:
        payload = self._encode_message(data)
        await self._client.lpush(self._queue_key, payload)

    async def get(self, timeout: int = 0) -> AsyncMessage:
        if timeout > 0:
            result = await self._client.blmove(self._queue_key, self._processing_key, timeout, "RIGHT", "LEFT")
        else:
            result = await self._client.lmove(self._queue_key, self._processing_key, "RIGHT", "LEFT")
        if result is None:
            raise QueueEmptyError("Queue is empty")
        msg = json.loads(result)
        return AsyncMessage(id=msg["id"], data=msg["data"], _queue=self, _raw=result)

    async def _ack(self, raw: bytes) -> None:
        """Remove message from processing list. O(N) where N is processing list length."""
        await self._client.lrem(self._processing_key, 1, raw)

    async def _nack(self, raw: bytes, msg_id: str, data: Any) -> None:
        payload = json.dumps({"id": msg_id, "data": data}).encode("utf-8")
        await self._nack_script(
            keys=[self._processing_key, self._queue_key],
            args=[raw, payload],
        )

    async def size(self) -> int:
        return await self._client.llen(self._queue_key)

    async def processing_count(self) -> int:
        return await self._client.llen(self._processing_key)
