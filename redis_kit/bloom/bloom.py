from __future__ import annotations

from typing import TYPE_CHECKING

from redis_kit.bloom._base import BloomFilterBase

if TYPE_CHECKING:
    pass


class BloomFilter(BloomFilterBase):
    """Redis-backed Bloom filter using bit operations."""

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
