from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from redis_kit.exceptions import QueueEmptyError
from redis_kit.queue._base import ReliableQueueBase

if TYPE_CHECKING:
    pass


@dataclass
class Message:
    """A message from a ReliableQueue with ack/nack support."""

    id: str
    data: Any
    _queue: ReliableQueue
    _raw: bytes

    def ack(self) -> None:
        self._queue._ack(self._raw)

    def nack(self) -> None:
        self._queue._nack(self._raw, self.id, self.data)


class ReliableQueue(ReliableQueueBase):
    """Redis-backed reliable queue with ack/nack support."""

    def put(self, data: Any) -> None:
        payload = self._encode_message(data)
        self._client.lpush(self._queue_key, payload)

    def get(self, timeout: int = 0) -> Message:
        if timeout > 0:
            result = self._client.blmove(self._queue_key, self._processing_key, timeout, "RIGHT", "LEFT")
        else:
            result = self._client.lmove(self._queue_key, self._processing_key, "RIGHT", "LEFT")
        if result is None:
            raise QueueEmptyError("Queue is empty")
        msg = json.loads(result)
        return Message(id=msg["id"], data=msg["data"], _queue=self, _raw=result)

    def _ack(self, raw: bytes) -> None:
        """Remove message from processing list. O(N) where N is processing list length."""
        self._client.lrem(self._processing_key, 1, raw)

    def _nack(self, raw: bytes, msg_id: str, data: Any) -> None:
        payload = json.dumps({"id": msg_id, "data": data}).encode("utf-8")
        self._nack_script(
            keys=[self._processing_key, self._queue_key],
            args=[raw, payload],
        )

    def size(self) -> int:
        return self._client.llen(self._queue_key)

    def processing_count(self) -> int:
        return self._client.llen(self._processing_key)
