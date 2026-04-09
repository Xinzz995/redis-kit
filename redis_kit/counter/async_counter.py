from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis.asyncio


class AsyncBoundCounter:
    """An async counter bound to a specific key."""

    def __init__(self, client: redis.asyncio.Redis, key: str) -> None:
        self._client = client
        self._key = key

    async def incr(self, amount: int = 1) -> int:
        return await self._client.incrby(self._key, amount)

    async def decr(self, amount: int = 1) -> int:
        return await self._client.decrby(self._key, amount)

    async def get(self) -> int:
        val = await self._client.get(self._key)
        return int(val) if val is not None else 0

    async def reset(self) -> None:
        await self._client.delete(self._key)


class AsyncCounter:
    """Async Redis-backed counter with transparent key prefixing."""

    def __init__(self, client: redis.asyncio.Redis, prefix: str = "") -> None:
        self._client = client
        self._prefix = prefix

    def _make_key(self, name: str) -> str:
        return f"{self._prefix}:{name}" if self._prefix else name

    async def incr(self, name: str, amount: int = 1) -> int:
        return await self._client.incrby(self._make_key(name), amount)

    async def decr(self, name: str, amount: int = 1) -> int:
        return await self._client.decrby(self._make_key(name), amount)

    async def get(self, name: str) -> int:
        val = await self._client.get(self._make_key(name))
        return int(val) if val is not None else 0

    async def reset(self, name: str) -> None:
        await self._client.delete(self._make_key(name))

    def bind(self, name: str) -> AsyncBoundCounter:
        return AsyncBoundCounter(self._client, self._make_key(name))


class AsyncIDGenerator:
    """Async Redis-backed atomic ID generator."""

    def __init__(
        self,
        client: redis.asyncio.Redis,
        name: str,
        prefix: str = "",
        padding: int = 0,
        key_prefix: str = "redis_kit:id",
    ) -> None:
        self._client = client
        self._key = f"{key_prefix}:{name}"
        self._prefix = prefix
        self._padding = padding

    async def next(self) -> int:
        return await self._client.incr(self._key)

    async def next_str(self) -> str:
        val = await self.next()
        padded = str(val).zfill(self._padding) if self._padding else str(val)
        return f"{self._prefix}{padded}" if self._prefix else padded
