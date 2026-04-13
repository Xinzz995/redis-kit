from __future__ import annotations

import json
from typing import Any

from redis_kit.serializers.base import wrap_serialization

_DUMP_ERRORS = (TypeError, ValueError, OverflowError)
_LOAD_ERRORS = (json.JSONDecodeError, UnicodeDecodeError)


class JsonSerializer:
    """JSON serializer. Default for redis-kit."""

    def dumps(self, value: Any) -> bytes:
        return wrap_serialization(
            lambda: json.dumps(value, ensure_ascii=False).encode("utf-8"),
            _DUMP_ERRORS,
            "JSON serialization failed",
        )

    def loads(self, data: bytes) -> Any:
        return wrap_serialization(
            lambda: json.loads(data),
            _LOAD_ERRORS,
            "JSON deserialization failed",
        )
