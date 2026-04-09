from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Compressor(Protocol):
    """Protocol for data compression."""

    def compress(self, data: bytes) -> bytes: ...
    def decompress(self, data: bytes) -> bytes: ...
