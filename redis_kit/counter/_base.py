from __future__ import annotations

from typing import Any


class CounterBase:
    """Shared logic for sync and async Counter implementations."""

    def __init__(self, client: Any, prefix: str = "") -> None:
        self._client = client
        self._prefix = prefix

    def _make_key(self, name: str) -> str:
        return f"{self._prefix}:{name}" if self._prefix else name


class IDGeneratorBase:
    """Shared logic for sync and async IDGenerator implementations."""

    def __init__(
        self,
        client: Any,
        name: str,
        prefix: str = "",
        padding: int = 0,
        key_prefix: str = "redis_kit:id",
    ) -> None:
        self._client = client
        self._key = f"{key_prefix}:{name}"
        self._prefix = prefix
        self._padding = padding

    def _format_id(self, value: int) -> str:
        padded = str(value).zfill(self._padding) if self._padding else str(value)
        return f"{self._prefix}{padded}" if self._prefix else padded
