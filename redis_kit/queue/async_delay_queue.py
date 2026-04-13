from __future__ import annotations

from typing import Any

from redis_kit.queue._base import DelayQueueBase


class AsyncDelayQueue(DelayQueueBase):
    """Async Redis-backed delay queue using Sorted Set."""

    async def put(self, data: Any, delay: int) -> None:
        payload = self._encode_message(data)
        await self._put_script(keys=[self._key], args=[delay, payload])

    async def poll(self, count: int = 10) -> list[Any]:
        if count <= 0:
            raise ValueError("count must be positive")
        results = await self._poll_script(keys=[self._key], args=[count])
        return self._decode_poll_results(results)

    async def size(self) -> int:
        return await self._client.zcard(self._key)
