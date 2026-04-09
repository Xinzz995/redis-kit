from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

from redis_kit.cache._logic import _MISS, DataPipeline, apply_jitter, parse_ttl
from redis_kit.compressors.base import Compressor
from redis_kit.exceptions import FallbackPolicy
from redis_kit.hooks import CommandHook
from redis_kit.serializers.base import Serializer

if TYPE_CHECKING:
    from collections.abc import Callable

    import redis


class BoundCache:
    """Cache operations bound to a specific key."""

    def __init__(self, cache: Cache, key: str) -> None:
        self._cache = cache
        self._key = key

    def get(self) -> Any:
        return self._cache.get(self._key)

    def set(self, value: Any, ttl: str | int | None = None) -> None:
        self._cache.set(self._key, value, ttl=ttl)

    def delete(self) -> None:
        self._cache.delete(self._key)

    def ttl(self) -> int:
        return self._cache.ttl(self._key)

    def pttl(self) -> int:
        return self._cache.pttl(self._key)

    def persist(self) -> None:
        self._cache.persist(self._key)

    def expire(self, seconds: int) -> None:
        self._cache.expire(self._key, seconds)

    def expire_at(self, when: datetime) -> None:
        self._cache.expire_at(self._key, when)


class Cache:
    """Redis cache with serialization, compression, TTL jitter, and fallback."""

    def __init__(
        self,
        client: redis.Redis,
        prefix: str = "",
        serializer: Serializer | None = None,
        compressor: Compressor | None = None,
        ttl_jitter: float = 0.1,
        fallback_policy: FallbackPolicy | None = None,
        hooks: list[CommandHook] | None = None,
        is_cluster: bool = False,
    ) -> None:
        self._client = client
        self._prefix = prefix
        self._pipeline = DataPipeline(serializer, compressor)
        self._ttl_jitter = ttl_jitter
        self._fallback = fallback_policy or FallbackPolicy()
        self._hooks = hooks or []
        self._is_cluster = is_cluster

    def _make_key(self, key: str) -> str:
        return f"{self._prefix}:{key}" if self._prefix else key

    def _resolve_ttl(self, ttl: str | int | None) -> int | None:
        if ttl is None:
            return None
        seconds = parse_ttl(ttl)
        return apply_jitter(seconds, self._ttl_jitter)

    def _notify_hooks(self, phase: str, command: str, key: str, **kwargs: Any) -> None:
        for hook in self._hooks:
            if phase == "before":
                hook.before(command, key, kwargs.get("args", ()))
            elif phase == "after":
                hook.after(command, key, kwargs.get("result"), kwargs.get("duration_ms", 0))
            elif phase == "error":
                hook.on_error(command, key, kwargs.get("error", RuntimeError()))

    def get(self, key: str) -> Any:
        full_key = self._make_key(key)
        start = time.monotonic()
        raw = self._client.get(full_key)
        duration = (time.monotonic() - start) * 1000
        value = self._pipeline.decode(raw)
        if value is _MISS:
            self._notify_hooks("after", "GET", key, result=None, duration_ms=duration)
            return None
        self._notify_hooks("after", "GET", key, result=value, duration_ms=duration)
        return value

    def set(self, key: str, value: Any, ttl: str | int | None = None) -> None:
        full_key = self._make_key(key)
        encoded = self._pipeline.encode(value)
        resolved_ttl = self._resolve_ttl(ttl)
        if resolved_ttl is not None and resolved_ttl > 0:
            self._client.setex(full_key, resolved_ttl, encoded)
        else:
            self._client.set(full_key, encoded)
        self._notify_hooks("after", "SET", key, result=None, duration_ms=0)

    def delete(self, key: str) -> None:
        self._client.delete(self._make_key(key))

    def ttl(self, key: str) -> int:
        return self._client.ttl(self._make_key(key))

    def pttl(self, key: str) -> int:
        return self._client.pttl(self._make_key(key))

    def persist(self, key: str) -> None:
        self._client.persist(self._make_key(key))

    def expire(self, key: str, seconds: int) -> None:
        self._client.expire(self._make_key(key), seconds)

    def expire_at(self, key: str, when: datetime) -> None:
        self._client.expireat(self._make_key(key), when)

    def remember(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: str | int | None = None,
    ) -> Any:
        value = self.get(key)
        if value is not None:
            return value
        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        full_keys = [self._make_key(k) for k in keys]
        if self._is_cluster:
            raw_values = [self._client.get(k) for k in full_keys]
        else:
            raw_values = self._client.mget(full_keys)
        result = {}
        for key, raw in zip(keys, raw_values):
            val = self._pipeline.decode(raw)
            result[key] = val if val is not _MISS else None
        return result

    def set_many(self, mapping: dict[str, Any], ttl: str | int | None = None) -> None:
        resolved_ttl = self._resolve_ttl(ttl)
        if self._is_cluster:
            for key, value in mapping.items():
                full_key = self._make_key(key)
                encoded = self._pipeline.encode(value)
                if resolved_ttl is not None and resolved_ttl > 0:
                    self._client.setex(full_key, resolved_ttl, encoded)
                else:
                    self._client.set(full_key, encoded)
        else:
            pipe = self._client.pipeline(transaction=False)
            for key, value in mapping.items():
                full_key = self._make_key(key)
                encoded = self._pipeline.encode(value)
                if resolved_ttl is not None and resolved_ttl > 0:
                    pipe.setex(full_key, resolved_ttl, encoded)
                else:
                    pipe.set(full_key, encoded)
            pipe.execute()

    def delete_pattern(self, pattern: str, batch_size: int = 100) -> int:
        full_pattern = self._make_key(pattern)
        count = 0
        for key in self._client.scan_iter(match=full_pattern, count=batch_size):
            self._client.delete(key)
            count += 1
        return count

    def iter_keys(self, pattern: str, batch_size: int = 100) -> Iterator[str]:
        full_pattern = self._make_key(pattern)
        prefix_len = len(self._prefix) + 1 if self._prefix else 0
        for key in self._client.scan_iter(match=full_pattern, count=batch_size):
            decoded = key.decode() if isinstance(key, bytes) else key
            yield decoded[prefix_len:] if prefix_len else decoded

    def bind(self, key: str) -> BoundCache:
        return BoundCache(self, key)
