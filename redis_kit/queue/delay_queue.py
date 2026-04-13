from __future__ import annotations

from typing import Any

from redis_kit.queue._base import DelayQueueBase


class DelayQueue(DelayQueueBase):
    """Redis-backed delay queue using Sorted Set."""

    def put(self, data: Any, delay: int) -> None:
        payload = self._encode_message(data)
        self._put_script(keys=[self._key], args=[delay, payload])

    def poll(self, count: int = 10) -> list[Any]:
        results = self._poll_script(keys=[self._key], args=[count])
        return self._decode_poll_results(results)

    def size(self) -> int:
        return self._client.zcard(self._key)
