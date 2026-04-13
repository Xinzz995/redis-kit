from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from redis_kit.session._lua import UPDATE_SCRIPT


class SessionManagerBase:
    """Shared logic for sync and async SessionManager implementations."""

    def __init__(
        self,
        client: Any,
        prefix: str = "session",
        ttl: int = 1800,
        id_generator: Callable[[], str] | None = None,
    ) -> None:
        self._client = client
        self._prefix = prefix
        self._ttl = ttl
        self._id_generator = id_generator or (lambda: uuid.uuid4().hex)
        self._update_script = self._client.register_script(UPDATE_SCRIPT)

    def _make_key(self, session_id: str) -> str:
        return f"{self._prefix}:{session_id}"
