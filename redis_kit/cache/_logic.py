from __future__ import annotations

import random
import re
from typing import Any

from redis_kit.compressors.base import Compressor
from redis_kit.serializers.base import Serializer
from redis_kit.serializers.json import JsonSerializer

# Sentinel for distinguishing None cache values from cache miss
_MISS = object()

# Marker prefix for cached None values
_NONE_MARKER = b"__REDIS_KIT_NONE__"
_NONE_MARKER_STR = "__REDIS_KIT_NONE__"


def parse_ttl(ttl: str | int | float) -> int:
    """Parse TTL from string like '2h30m' or numeric seconds."""
    if isinstance(ttl, (int, float)):
        return int(ttl)
    if isinstance(ttl, str):
        total = 0
        for match in re.finditer(r"(\d+)\s*([dhms])", ttl.lower()):
            value, unit = int(match.group(1)), match.group(2)
            multipliers = {"d": 86400, "h": 3600, "m": 60, "s": 1}
            total += value * multipliers[unit]
        if total == 0:
            raise ValueError(f"Invalid TTL string: '{ttl}'")
        return total
    raise TypeError(f"TTL must be str, int, or float, got {type(ttl)}")


def apply_jitter(ttl: int, jitter: float) -> int:
    """Apply random jitter to TTL. jitter=0.1 means +/- 10%."""
    if jitter <= 0 or ttl <= 0:
        return ttl
    delta = int(ttl * jitter)
    return max(1, ttl + random.randint(-delta, delta))


def resolve_callable(value: Any, args: tuple, kwargs: dict) -> Any:
    """If value is callable, call it with the function's args/kwargs."""
    if callable(value):
        return value(*args, **kwargs)
    return value


class DataPipeline:
    """Handles serialize -> compress -> store and retrieve -> decompress -> deserialize."""

    def __init__(
        self,
        serializer: Serializer | None = None,
        compressor: Compressor | None = None,
    ) -> None:
        self.serializer = serializer or JsonSerializer()
        self.compressor = compressor

    def encode(self, value: Any) -> bytes:
        if value is None:
            return _NONE_MARKER
        data = self.serializer.dumps(value)
        if self.compressor:
            data = self.compressor.compress(data)
        return data

    def decode(self, data: bytes | None) -> Any:
        if data is None:
            return _MISS
        if data == _NONE_MARKER or data == _NONE_MARKER_STR:
            return None
        if self.compressor:
            data = self.compressor.decompress(data)
        return self.serializer.loads(data)
