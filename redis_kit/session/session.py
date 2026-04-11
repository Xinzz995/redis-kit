from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from redis_kit.exceptions import SessionNotFoundError
from redis_kit.session._lua import UPDATE_SCRIPT

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
        self._update_script = self._client.register_script(UPDATE_SCRIPT)

    def _make_key(self, session_id: str) -> str:
        return f"{self._prefix}:{session_id}"

    def create(self, data: dict[str, Any]) -> str:
        session_id = self._id_generator()
        key = self._make_key(session_id)
        str_data = {k: json.dumps(v) for k, v in data.items()}
        pipe = self._client.pipeline(transaction=True)
        pipe.hset(key, mapping=str_data)
        pipe.expire(key, self._ttl)
        pipe.execute()
        return session_id

    def get(self, session_id: str) -> dict[str, Any] | None:
        key = self._make_key(session_id)
        data = self._client.hgetall(key)
        if not data:
            return None
        return {
            (k.decode() if isinstance(k, bytes) else k): json.loads(v.decode() if isinstance(v, bytes) else v)
            for k, v in data.items()
        }

    def update(self, session_id: str, data: dict[str, Any]) -> None:
        key = self._make_key(session_id)
        # Flatten field/value pairs for the Lua script
        argv: list[Any] = [self._ttl]
        for field, value in data.items():
            argv.append(field)
            argv.append(json.dumps(value))
        result = self._update_script(keys=[key], args=argv)
        if not result:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

    def delete(self, session_id: str) -> None:
        self._client.delete(self._make_key(session_id))

    def refresh(self, session_id: str) -> None:
        key = self._make_key(session_id)
        # expire() returns 0 if the key does not exist — single atomic command
        if not self._client.expire(key, self._ttl):
            raise SessionNotFoundError(f"Session '{session_id}' not found")

    def exists(self, session_id: str) -> bool:
        return bool(self._client.exists(self._make_key(session_id)))
