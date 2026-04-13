from __future__ import annotations

from typing import Any

import msgpack

from redis_kit.exceptions import SerializationError


class MsgpackSerializer:
    """MessagePack serializer. Compact binary format, fast."""

    def dumps(self, value: Any) -> bytes:
        try:
            return msgpack.packb(value, use_bin_type=True)
        except (TypeError, ValueError) as e:
            raise SerializationError(f"Msgpack serialization failed: {e}") from e

    def loads(self, data: bytes) -> Any:
        try:
            return msgpack.unpackb(data, raw=False)
        except (msgpack.UnpackException, TypeError, ValueError) as e:
            raise SerializationError(f"Msgpack deserialization failed: {e}") from e
