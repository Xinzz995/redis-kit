from __future__ import annotations

import hashlib
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis


class BloomFilter:
    """Redis-backed Bloom filter using bit operations."""

    def __init__(
        self,
        client: redis.Redis,
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
        """Double hashing: compute 2 base hashes, derive k offsets."""
        data = item.encode()
        h = hashlib.md5(data).hexdigest()  # noqa: S324
        h1 = int(h[:16], 16)
        h2 = int(h[16:], 16)
        return [(h1 + i * h2) % self._size for i in range(self._hash_count)]

    def add(self, item: str) -> None:
        pipe = self._client.pipeline(transaction=False)
        for offset in self._get_offsets(item):
            pipe.setbit(self._key, offset, 1)
        pipe.execute()

    def exists(self, item: str) -> bool:
        pipe = self._client.pipeline(transaction=False)
        for offset in self._get_offsets(item):
            pipe.getbit(self._key, offset)
        return all(pipe.execute())

    def add_many(self, items: list[str]) -> None:
        pipe = self._client.pipeline(transaction=False)
        for item in items:
            for offset in self._get_offsets(item):
                pipe.setbit(self._key, offset, 1)
        pipe.execute()

    def exists_many(self, items: list[str]) -> list[bool]:
        pipe = self._client.pipeline(transaction=False)
        item_offsets = [self._get_offsets(item) for item in items]
        for offsets in item_offsets:
            for offset in offsets:
                pipe.getbit(self._key, offset)
        all_bits = pipe.execute()

        results = []
        idx = 0
        for offsets in item_offsets:
            item_bits = all_bits[idx : idx + len(offsets)]
            results.append(all(item_bits))
            idx += len(offsets)
        return results

    def reset(self) -> None:
        """Delete the bloom filter key, resetting it."""
        self._client.delete(self._key)
