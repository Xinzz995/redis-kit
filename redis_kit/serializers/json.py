from __future__ import annotations

import json
from typing import Any


class JsonSerializer:
    """JSON serializer. Default for redis-kit."""

    def dumps(self, value: Any) -> bytes:
        return json.dumps(value, ensure_ascii=False).encode("utf-8")

    def loads(self, data: bytes) -> Any:
        return json.loads(data)
