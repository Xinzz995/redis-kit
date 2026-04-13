from __future__ import annotations

from typing import Any

import msgpack

from redis_kit.serializers.base import wrap_serialization

_DUMP_ERRORS = (TypeError, ValueError)
_LOAD_ERRORS = (msgpack.UnpackException, TypeError, ValueError)


class MsgpackSerializer:
    """MessagePack serializer. Compact binary format, fast."""

    def dumps(self, value: Any) -> bytes:
        return wrap_serialization(
            lambda: msgpack.packb(value, use_bin_type=True),
            _DUMP_ERRORS,
            "Msgpack serialization failed",
        )

    def loads(self, data: bytes) -> Any:
        return wrap_serialization(
            lambda: msgpack.unpackb(data, raw=False),
            _LOAD_ERRORS,
            "Msgpack deserialization failed",
        )
