from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from redis_kit.exceptions import QueueEmptyError

if TYPE_CHECKING:
    import redis


@dataclass
class Message:
    """A message from a ReliableQueue with ack/nack support."""

    id: str
    data: Any
    _queue: ReliableQueue

    def ack(self) -> None:
        self._queue._ack(self.id)

    def nack(self) -> None:
        self._queue._nack(self.id, self.data)


class ReliableQueue:
    """Redis-backed reliable queue with ack/nack support."""

    def __init__(self, client: redis.Redis, name: str, prefix: str = "") -> None:
        self._client = client
        base = f"{prefix}:{name}" if prefix else name
        self._queue_key = f"{base}:queue"
        self._processing_key = f"{base}:processing"

    def put(self, data: Any) -> None:
        msg_id = uuid.uuid4().hex[:12]
        payload = json.dumps({"id": msg_id, "data": data}).encode("utf-8")
        self._client.lpush(self._queue_key, payload)

    def get(self, timeout: int = 0) -> Message:
        if timeout > 0:
            result = self._client.brpoplpush(self._queue_key, self._processing_key, timeout=timeout)
        else:
            result = self._client.rpoplpush(self._queue_key, self._processing_key)
        if result is None:
            raise QueueEmptyError("Queue is empty")
        msg = json.loads(result)
        return Message(id=msg["id"], data=msg["data"], _queue=self)

    def _ack(self, msg_id: str) -> None:
        items = self._client.lrange(self._processing_key, 0, -1)
        for item in items:
            msg = json.loads(item)
            if msg["id"] == msg_id:
                self._client.lrem(self._processing_key, 1, item)
                return

    def _nack(self, msg_id: str, data: Any) -> None:
        self._ack(msg_id)
        self.put(data)

    def size(self) -> int:
        return self._client.llen(self._queue_key)

    def processing_count(self) -> int:
        return self._client.llen(self._processing_key)
