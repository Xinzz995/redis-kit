from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

from redis_kit.queue._lua import POLL_SCRIPT, PUT_SCRIPT

if TYPE_CHECKING:
    import redis


class DelayQueue:
    """Redis-backed delay queue using Sorted Set."""

    def __init__(self, client: redis.Redis, name: str, prefix: str = "") -> None:
        self._client = client
        self._key = f"{prefix}:{name}" if prefix else name
        self._poll_script = self._client.register_script(POLL_SCRIPT)
        self._put_script = self._client.register_script(PUT_SCRIPT)

    def put(self, data: Any, delay: int) -> None:
        msg_id = uuid.uuid4().hex[:12]
        payload = json.dumps({"id": msg_id, "data": data}).encode("utf-8")
        self._put_script(keys=[self._key], args=[delay, payload])

    def poll(self, count: int = 10) -> list[Any]:
        results = self._poll_script(keys=[self._key], args=[count])
        items: list[Any] = []
        for r in results:
            msg = json.loads(r)
            items.append(msg["data"] if isinstance(msg, dict) and "data" in msg else msg)
        return items

    def size(self) -> int:
        return self._client.zcard(self._key)
