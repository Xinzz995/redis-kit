from __future__ import annotations

import json
import time
import uuid
from typing import TYPE_CHECKING, Any

from redis_kit.queue._lua import POLL_SCRIPT

if TYPE_CHECKING:
    import redis


class DelayQueue:
    """Redis-backed delay queue using Sorted Set."""

    def __init__(self, client: redis.Redis, name: str, prefix: str = "") -> None:
        self._client = client
        self._key = f"{prefix}:{name}" if prefix else name
        self._poll_script = self._client.register_script(POLL_SCRIPT)

    def put(self, data: Any, delay: int) -> None:
        score = time.time() + delay
        msg_id = uuid.uuid4().hex[:12]
        payload = json.dumps({"id": msg_id, "data": data}).encode("utf-8")
        self._client.zadd(self._key, {payload: score})

    def poll(self, count: int = 10) -> list[Any]:
        now = time.time()
        results = self._poll_script(keys=[self._key], args=[now, count])
        items: list[Any] = []
        for r in results:
            msg = json.loads(r)
            items.append(msg["data"] if isinstance(msg, dict) and "data" in msg else msg)
        return items

    def size(self) -> int:
        return self._client.zcard(self._key)
