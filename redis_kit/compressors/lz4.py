from __future__ import annotations

import lz4.frame


class Lz4Compressor:
    """LZ4 compressor. Very fast, moderate compression."""

    def compress(self, data: bytes) -> bytes:
        return lz4.frame.compress(data)

    def decompress(self, data: bytes) -> bytes:
        return lz4.frame.decompress(data)
