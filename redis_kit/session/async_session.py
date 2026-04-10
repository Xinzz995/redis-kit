from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from redis_kit.exceptions import SessionNotFoundError

if TYPE_CHECKING:
    import redis.asyncio

# Atomically update session fields only if the key already exists.
# Returns 1 on success, 0 if the session key does not exist.
# KEYS[1]: session key
# ARGV[1]: TTL in seconds
# ARGV[2..N]: interleaved field/value pairs to HSET
_UPDATE_SCRIPT = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
if redis.call("exists", key) == 0 then
    return 0
end
for i = 2, #ARGV, 2 do
    redis.call("hset", key, ARGV[i], ARGV[i + 1])
end
redis.call("expire", key, ttl)
return 1
"""


class AsyncSessionManager:
    """Async Redis-backed session management using Hash per session."""

    def __init__(
        self,
        client: redis.asyncio.Redis,
        prefix: str = "session",
        ttl: int = 1800,
        id_generator: Callable[[], str] | None = None,
    ) -> None:
        self._client = client
        self._prefix = prefix
        self._ttl = ttl
        self._id_generator = id_generator or (lambda: uuid.uuid4().hex)
        self._update_script = self._client.register_script(_UPDATE_SCRIPT)

    def _make_key(self, session_id: str) -> str:
        return f"{self._prefix}:{session_id}"

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
