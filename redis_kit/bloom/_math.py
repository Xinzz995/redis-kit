from __future__ import annotations

import hashlib
import math


def optimal_size(n: int, p: float) -> int:
    """Calculate optimal bit array size for n items with false positive rate p."""
    return int(-(n * math.log(p)) / (math.log(2) ** 2))


def optimal_hash_count(m: int, n: int) -> int:
    """Calculate optimal number of hash functions for m bits and n items."""
    return max(1, int((m / n) * math.log(2)))


def get_offsets(item: str, size: int, hash_count: int) -> list[int]:
    """Double hashing: compute 2 base hashes, derive k offsets."""
    digest = hashlib.md5(item.encode()).digest()  # noqa: S324
    h1 = int.from_bytes(digest[:8], "big")
    h2 = int.from_bytes(digest[8:], "big")
    return [(h1 + i * h2) % size for i in range(hash_count)]
