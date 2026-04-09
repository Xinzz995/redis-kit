from __future__ import annotations

from typing import Any

import msgpack


class MsgpackSerializer:
    """MessagePack serializer. Compact binary format, fast."""

    def dumps(self, value: Any) -> bytes:
        return msgpack.packb(value, use_bin_type=True)

    def loads(self, data: bytes) -> Any:
        return msgpack.unpackb(data, raw=False)
