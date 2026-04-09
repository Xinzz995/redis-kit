from __future__ import annotations

import zlib


class ZlibCompressor:
    """Zlib compressor. No external dependencies."""

    def __init__(self, level: int = 6) -> None:
        self._level = level

    def compress(self, data: bytes) -> bytes:
        return zlib.compress(data, level=self._level)

    def decompress(self, data: bytes) -> bytes:
        return zlib.decompress(data)
