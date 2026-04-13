from __future__ import annotations

import zstandard


class ZstdCompressor:
    """Zstandard compressor. Fast with high compression ratio.

    The underlying ``zstandard`` compressor/decompressor instances are
    reused across calls. Per the ``python-zstandard`` documentation,
    ``ZstdCompressor`` instances are safe to use from multiple threads.
    """

    def __init__(self, level: int = 3) -> None:
        self._compressor = zstandard.ZstdCompressor(level=level)
        self._decompressor = zstandard.ZstdDecompressor()

    def compress(self, data: bytes) -> bytes:
        return self._compressor.compress(data)

    def decompress(self, data: bytes) -> bytes:
        return self._decompressor.decompress(data)
