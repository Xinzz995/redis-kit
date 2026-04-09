from __future__ import annotations

import hashlib
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio


class AsyncBloomFilter:
    """Async Redis-backed Bloom filter using bit operations."""

    def __init__(
        self,
        client: redis.asyncio.Redis,
        name: str,
        expected_items: int = 10_000,
        false_positive_rate: float = 0.01,
        prefix: str = "redis_kit:bloom",
    ) -> None:
        self._client = client
        self._key = f"{prefix}:{name}"
        self._size = self._optimal_size(expected_items, false_positive_rate)
        self._hash_count = self._optimal_hash_count(self._size, expected_items)

    @staticmethod
    def _optimal_size(n: int, p: float) -> int:
        return int(-(n * math.log(p)) / (math.log(2) ** 2))

    @staticmethod
    def _optimal_hash_count(m: int, n: int) -> int:
        return max(1, int((m / n) * math.log(2)))

    def _get_offsets(self, item: str) -> list[int]:
        offsets = []
        for i in range(self._hash_count):
            h = hashlib.sha256(f"{i}:{item}".encode()).hexdigest()
            offsets.append(int(h, 16) % self._size)
        return offsets

    async def add(self, item: str) -> None:
        pipe = self._client.pipeline(transaction=False)
        for offset in self._get_offsets(item):
            pipe.setbit(self._key, offset, 1)
        await pipe.execute()

    async def exists(self, item: str) -> bool:
        pipe = self._client.pipeline(transaction=False)
        for offset in self._get_offsets(item):
            pipe.getbit(self._key, offset)
        return all(await pipe.execute())

    async def add_many(self, items: list[str]) -> None:
        pipe = self._client.pipeline(transaction=False)
        for item in items:
            for offset in self._get_offsets(item):
                pipe.setbit(self._key, offset, 1)
        await pipe.execute()

    async def exists_many(self, items: list[str]) -> list[bool]:
        results = []
        for item in items:
            results.append(await self.exists(item))
        return results
