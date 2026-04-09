from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import redis

_POLL_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local count = tonumber(ARGV[2])
local results = redis.call("zrangebyscore", key, "-inf", now, "LIMIT", 0, count)
for i, v in ipairs(results) do
    redis.call("zrem", key, v)
end
return results
"""


class DelayQueue:
    """Redis-backed delay queue using Sorted Set."""

    def __init__(self, client: redis.Redis, name: str, prefix: str = "") -> None:
        self._client = client
        self._key = f"{prefix}:{name}" if prefix else name
        self._poll_script = self._client.register_script(_POLL_SCRIPT)

    def put(self, data: Any, delay: int) -> None:
        score = time.time() + delay
        payload = json.dumps(data).encode("utf-8")
        self._client.zadd(self._key, {payload: score})

    def poll(self, count: int = 10) -> list[Any]:
        now = time.time()
        results = self._poll_script(keys=[self._key], args=[now, count])
        return [json.loads(r) for r in results]

    def size(self) -> int:
        return self._client.zcard(self._key)
