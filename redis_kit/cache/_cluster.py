from __future__ import annotations

from collections import defaultdict
from typing import Any


def group_keys_by_slot(client: Any, keys: list[str]) -> dict[int, list[str]]:
    """Group Redis keys by CRC16 slot for Cluster multi-key operations."""
    groups: dict[int, list[str]] = defaultdict(list)
    for key in keys:
        slot = client.keyslot(key)
        groups[slot].append(key)
    return groups
