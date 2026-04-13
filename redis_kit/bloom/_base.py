from __future__ import annotations

from typing import Any

from redis_kit.bloom._math import _get_offsets, _optimal_hash_count, _optimal_size


class BloomFilterBase:
    """Shared logic for sync and async Bloom filter implementations."""

    def __init__(
        self,
        client: Any,
        name: str,
        expected_items: int = 10_000,
        false_positive_rate: float = 0.01,
        prefix: str = "redis_kit:bloom",
    ) -> None:
        self._client = client
        self._key = f"{prefix}:{name}"
        self._size = _optimal_size(expected_items, false_positive_rate)
        self._hash_count = _optimal_hash_count(self._size, expected_items)

    def _get_offsets(self, item: str) -> list[int]:
        return _get_offsets(item, self._size, self._hash_count)
