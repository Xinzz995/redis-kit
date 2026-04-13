from __future__ import annotations

from typing import Any

from redis_kit.repository._lua import OPTIMISTIC_LOCK_PARTIAL_SET, OPTIMISTIC_LOCK_SET


class RepositoryBase:
    """Shared logic for sync and async Repository implementations."""

    def __init__(
        self,
        client: Any,
        model_class: type,
        prefix: str = "",
        is_cluster: bool = False,
        max_history: int | None = None,
    ) -> None:
        self._client = client
        self._model_class = model_class
        self._prefix = prefix
        self._is_cluster = is_cluster
        self._max_history = max_history
        self._lock_set_script = self._client.register_script(OPTIMISTIC_LOCK_SET)
        self._lock_partial_set_script = self._client.register_script(OPTIMISTIC_LOCK_PARTIAL_SET)
        self._index_key = f"{self._prefix}:_index" if self._prefix else "_index"

    def _make_key(self, entity_id: str) -> str:
        return f"{self._prefix}:{entity_id}" if self._prefix else entity_id

    def _history_key(self, entity_id: str) -> str:
        return f"{self._make_key(entity_id)}:history"

    def _max_history_arg(self) -> str:
        """Return max_history as a Lua-compatible string arg (-1 = unlimited)."""
        return str(self._max_history) if self._max_history is not None else "-1"
