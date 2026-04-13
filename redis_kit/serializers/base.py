from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from redis_kit.exceptions import SerializationError


@runtime_checkable
class Serializer(Protocol):
    """Protocol for data serialization. All implementations use bytes I/O."""

    def dumps(self, value: Any) -> bytes: ...
    def loads(self, data: bytes) -> Any: ...


def wrap_serialization(fn: Callable[[], Any], exceptions: tuple, msg: str) -> Any:
    """Call *fn* and wrap expected exceptions into SerializationError."""
    try:
        return fn()
    except exceptions as e:
        raise SerializationError(f"{msg}: {e}") from e
