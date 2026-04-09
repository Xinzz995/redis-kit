from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

from redis_kit.cache._logic import _MISS, DataPipeline, apply_jitter, parse_ttl
from redis_kit.compressors.base import Compressor
from redis_kit.exceptions import FallbackPolicy
from redis_kit.hooks import CommandHook
from redis_kit.serializers.base import Serializer

if TYPE_CHECKING:
    from collections.abc import Callable

    import redis.asyncio


class AsyncBoundCache:
    """Async cache operations bound to a specific key."""

    def __init__(self, cache: AsyncCache, key: str) -> None:
        self._cache = cache
        self._key = key

    async def get(self) -> Any:
        return await self._cache.get(self._key)

    async def set(self, value: Any, ttl: str | int | None = None) -> None:
        await self._cache.set(self._key, value, ttl=ttl)

    async def delete(self) -> None:
        await self._cache.delete(self._key)

    async def ttl(self) -> int:
        return await self._cache.ttl(self._key)

    async def pttl(self) -> int:
        return await self._cache.pttl(self._key)

    async def persist(self) -> None:
        await self._cache.persist(self._key)

    async def expire(self, seconds: int) -> None:
        await self._cache.expire(self._key, seconds)

    async def expire_at(self, when: datetime) -> None:
        await self._cache.expire_at(self._key, when)


class AsyncCache:
    """Async Redis cache with serialization, compression, TTL jitter, and fallback."""

    def __init__(
        self,
        client: redis.asyncio.Redis,
        prefix: str = "",
        serializer: Serializer | None = None,
        compressor: Compressor | None = None,
        ttl_jitter: float = 0.1,
        fallback_policy: FallbackPolicy | None = None,
        hooks: list[CommandHook] | None = None,
    ) -> None:
        self._client = client
        self._prefix = prefix
        self._pipeline = DataPipeline(serializer, compressor)
        self._ttl_jitter = ttl_jitter
        self._fallback = fallback_policy or FallbackPolicy()
        self._hooks = hooks or []

    def _make_key(self, key: str) -> str:
        return f"{self._prefix}:{key}" if self._prefix else key

    def _resolve_ttl(self, ttl: str | int | None) -> int | None:
        if ttl is None:
            return None
        seconds = parse_ttl(ttl)
        return apply_jitter(seconds, self._ttl_jitter)

    async def get(self, key: str) -> Any:
        full_key = self._make_key(key)
        raw = await self._client.get(full_key)
        value = self._pipeline.decode(raw)
        return value if value is not _MISS else None

    async def set(self, key: str, value: Any, ttl: str | int | None = None) -> None:
        full_key = self._make_key(key)
        encoded = self._pipeline.encode(value)
        resolved_ttl = self._resolve_ttl(ttl)
        if resolved_ttl is not None and resolved_ttl > 0:
            await self._client.setex(full_key, resolved_ttl, encoded)
        else:
            await self._client.set(full_key, encoded)

    async def delete(self, key: str) -> None:
        await self._client.delete(self._make_key(key))

    async def ttl(self, key: str) -> int:
        return await self._client.ttl(self._make_key(key))

    async def pttl(self, key: str) -> int:
        return await self._client.pttl(self._make_key(key))

    async def persist(self, key: str) -> None:
        await self._client.persist(self._make_key(key))

    async def expire(self, key: str, seconds: int) -> None:
        await self._client.expire(self._make_key(key), seconds)

    async def expire_at(self, key: str, when: datetime) -> None:
        await self._client.expireat(self._make_key(key), when)

    async def remember(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: str | int | None = None,
    ) -> Any:
        value = await self.get(key)
        if value is not None:
            return value
        result = factory()
        if asyncio.iscoroutine(result):
            result = await result
        value = result
        await self.set(key, value, ttl=ttl)
        return value

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        full_keys = [self._make_key(k) for k in keys]
        raw_values = await self._client.mget(full_keys)
        result = {}
        for key, raw in zip(keys, raw_values):
            val = self._pipeline.decode(raw)
            result[key] = val if val is not _MISS else None
        return result

    async def set_many(self, mapping: dict[str, Any], ttl: str | int | None = None) -> None:
        resolved_ttl = self._resolve_ttl(ttl)
        pipe = self._client.pipeline(transaction=False)
        for key, value in mapping.items():
            full_key = self._make_key(key)
            encoded = self._pipeline.encode(value)
            if resolved_ttl is not None and resolved_ttl > 0:
                pipe.setex(full_key, resolved_ttl, encoded)
            else:
                pipe.set(full_key, encoded)
        await pipe.execute()

    async def delete_pattern(self, pattern: str, batch_size: int = 100) -> int:
        full_pattern = self._make_key(pattern)
        count = 0
        async for key in self._client.scan_iter(match=full_pattern, count=batch_size):
            await self._client.delete(key)
            count += 1
        return count

    async def iter_keys(self, pattern: str, batch_size: int = 100) -> AsyncIterator[str]:
        full_pattern = self._make_key(pattern)
        prefix_len = len(self._prefix) + 1 if self._prefix else 0
        async for key in self._client.scan_iter(match=full_pattern, count=batch_size):
            decoded = key.decode() if isinstance(key, bytes) else key
            yield decoded[prefix_len:] if prefix_len else decoded

    def bind(self, key: str) -> AsyncBoundCache:
        return AsyncBoundCache(self, key)
