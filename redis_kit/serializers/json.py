from __future__ import annotations

import json
from typing import Any

from redis_kit.exceptions import SerializationError


class JsonSerializer:
    """JSON serializer. Default for redis-kit."""

    def dumps(self, value: Any) -> bytes:
        try:
            return json.dumps(value, ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError, OverflowError) as e:
            raise SerializationError(f"JSON serialization failed: {e}") from e

    def loads(self, data: bytes) -> Any:
        try:
            return json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise SerializationError(f"JSON deserialization failed: {e}") from e
