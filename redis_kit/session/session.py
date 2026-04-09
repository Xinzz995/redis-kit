from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from redis_kit.exceptions import SessionNotFoundError

if TYPE_CHECKING:
    import redis


class SessionManager:
    """Redis-backed session management using Hash per session."""

    def __init__(
        self,
        client: redis.Redis,
        prefix: str = "session",
        ttl: int = 1800,
        id_generator: Callable[[], str] | None = None,
    ) -> None:
        self._client = client
        self._prefix = prefix
        self._ttl = ttl
        self._id_generator = id_generator or (lambda: uuid.uuid4().hex)

    def _make_key(self, session_id: str) -> str:
        return f"{self._prefix}:{session_id}"

    def create(self, data: dict[str, Any]) -> str:
        session_id = self._id_generator()
        key = self._make_key(session_id)
        str_data = {k: str(v) for k, v in data.items()}
        self._client.hset(key, mapping=str_data)
        self._client.expire(key, self._ttl)
        return session_id

    def get(self, session_id: str) -> dict[str, str] | None:
        key = self._make_key(session_id)
        data = self._client.hgetall(key)
        if not data:
            return None
        return {
            k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
            for k, v in data.items()
        }

    def update(self, session_id: str, data: dict[str, Any]) -> None:
        key = self._make_key(session_id)
        if not self._client.exists(key):
            raise SessionNotFoundError(f"Session '{session_id}' not found")
        str_data = {k: str(v) for k, v in data.items()}
        self._client.hset(key, mapping=str_data)

    def delete(self, session_id: str) -> None:
        self._client.delete(self._make_key(session_id))

    def refresh(self, session_id: str) -> None:
        key = self._make_key(session_id)
        if not self._client.exists(key):
            raise SessionNotFoundError(f"Session '{session_id}' not found")
        self._client.expire(key, self._ttl)

    def exists(self, session_id: str) -> bool:
        return bool(self._client.exists(self._make_key(session_id)))
