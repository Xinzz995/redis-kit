from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Serializer(Protocol):
    """Protocol for data serialization. All implementations use bytes I/O."""

    def dumps(self, value: Any) -> bytes: ...
    def loads(self, data: bytes) -> Any: ...
