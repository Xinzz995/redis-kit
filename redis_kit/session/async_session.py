from __future__ import annotations

import json
from typing import Any

from redis_kit.exceptions import SessionNotFoundError
from redis_kit.session._base import SessionManagerBase


class AsyncSessionManager(SessionManagerBase):
    """Async Redis-backed session management using Hash per session."""

    async def create(self, data: dict[str, Any]) -> str:
        session_id = self._id_generator()
        key = self._make_key(session_id)
        str_data = {k: json.dumps(v) for k, v in data.items()}
        pipe = self._client.pipeline(transaction=True)
        pipe.hset(key, mapping=str_data)
        pipe.expire(key, self._ttl)
        await pipe.execute()
        return session_id

    async def get(self, session_id: str) -> dict[str, Any] | None:
        key = self._make_key(session_id)
        data = await self._client.hgetall(key)
        if not data:
            return None
        return {
            (k.decode() if isinstance(k, bytes) else k): json.loads(v.decode() if isinstance(v, bytes) else v)
            for k, v in data.items()
        }

    async def update(self, session_id: str, data: dict[str, Any]) -> None:
        key = self._make_key(session_id)
        # Flatten field/value pairs for the Lua script
        argv: list[Any] = [self._ttl]
        for field, value in data.items():
            argv.append(field)
            argv.append(json.dumps(value))
        result = await self._update_script(keys=[key], args=argv)
        if not result:
            raise SessionNotFoundError(f"Session '{session_id}' not found")

    async def delete(self, session_id: str) -> None:
        await self._client.delete(self._make_key(session_id))

    async def refresh(self, session_id: str) -> None:
        key = self._make_key(session_id)
        # expire() returns 0 if the key does not exist — single atomic command
        if not await self._client.expire(key, self._ttl):
            raise SessionNotFoundError(f"Session '{session_id}' not found")

    async def exists(self, session_id: str) -> bool:
        return bool(await self._client.exists(self._make_key(session_id)))
