from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from redis_kit.cache._logic import _MISS, DataPipeline, apply_jitter, parse_ttl
from redis_kit.compressors.base import Compressor
from redis_kit.exceptions import FallbackPolicy
from redis_kit.hooks import CommandHook
from redis_kit.serializers.base import Serializer

if TYPE_CHECKING:
    from collections.abc import Callable

    import redis

_FALLBACK_ERRORS = (RedisConnectionError, RedisTimeoutError)
_logger = logging.getLogger("redis_kit.cache")


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
            try:
                if phase == "before":
                    hook.before(command, key, kwargs.get("args", ()))
                elif phase == "after":
                    hook.after(command, key, kwargs.get("result"), kwargs.get("duration_ms", 0))
                elif phase == "error":
                    hook.on_error(command, key, kwargs.get("error", RuntimeError()))
            except Exception:
                _logger.exception("Hook %s() failed for %s", phase, type(hook).__name__)

    def _handle_fallback(self, error: Exception, command: str, key: str, default: Any = None) -> Any:
        """Apply FallbackPolicy after hooks.on_error() has been called."""
        if not isinstance(error, _FALLBACK_ERRORS):
            raise error
        policy = self._fallback.on_connection_error
        if policy == "raise":
            raise error
        if policy == "return_none":
            if self._fallback.log_on_fallback:
                self._fallback.logger.warning("Redis %s on key '%s' failed, returning None: %s", command, key, error)
            return default
        if policy == "callback":
            if self._fallback.fallback is not None:
                return self._fallback.fallback(command, key, error)
            raise error
        raise error  # pragma: no cover

    def _get_raw(self, key: str) -> Any:
        """Internal get returning _MISS sentinel for cache miss."""
        full_key = self._make_key(key)
        self._notify_hooks("before", "GET", key, args=())
        start = time.monotonic()
        try:
            raw = self._client.get(full_key)
        except Exception as e:
            self._notify_hooks("error", "GET", key, error=e)
            return self._handle_fallback(e, "GET", key, default=_MISS)
        duration = (time.monotonic() - start) * 1000
        value = self._pipeline.decode(raw)
        self._notify_hooks("after", "GET", key, result=value if value is not _MISS else None, duration_ms=duration)
        return value

    def get(self, key: str) -> Any:
        value = self._get_raw(key)
        return None if value is _MISS else value

    def set(self, key: str, value: Any, ttl: str | int | None = None) -> None:
        full_key = self._make_key(key)
        encoded = self._pipeline.encode(value)
        resolved_ttl = self._resolve_ttl(ttl)
        self._notify_hooks("before", "SET", key, args=(value, ttl))
        start = time.monotonic()
        try:
            if resolved_ttl is not None and resolved_ttl > 0:
                self._client.setex(full_key, resolved_ttl, encoded)
            else:
                self._client.set(full_key, encoded)
        except Exception as e:
            self._notify_hooks("error", "SET", key, error=e)
            self._handle_fallback(e, "SET", key)
            return
        duration = (time.monotonic() - start) * 1000
        self._notify_hooks("after", "SET", key, result=None, duration_ms=duration)

    def delete(self, key: str) -> None:
        self._notify_hooks("before", "DELETE", key, args=())
        start = time.monotonic()
        try:
            self._client.delete(self._make_key(key))
        except Exception as e:
            self._notify_hooks("error", "DELETE", key, error=e)
            raise
        duration = (time.monotonic() - start) * 1000
        self._notify_hooks("after", "DELETE", key, result=None, duration_ms=duration)

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
        value = self._get_raw(key)
        if value is not _MISS:
            return value
        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    def get_many(self, keys: list[str]) -> dict[str, Any]:
        full_keys = [self._make_key(k) for k in keys]
        keys_str = ",".join(keys)
        self._notify_hooks("before", "GET_MANY", keys_str, args=(keys,))
        start = time.monotonic()
        try:
            if self._is_cluster:
                raw_values = [self._client.get(k) for k in full_keys]
            else:
                raw_values = self._client.mget(full_keys)
        except Exception as e:
            self._notify_hooks("error", "GET_MANY", keys_str, error=e)
            raise
        duration = (time.monotonic() - start) * 1000
        result = {}
        for key, raw in zip(keys, raw_values):
            val = self._pipeline.decode(raw)
            result[key] = val if val is not _MISS else None
        self._notify_hooks("after", "GET_MANY", keys_str, result=result, duration_ms=duration)
        return result

    def _get_many_raw(self, keys: list[str]) -> dict[str, Any]:
        """Internal get_many returning _MISS sentinel for cache misses."""
        full_keys = [self._make_key(k) for k in keys]
        if self._is_cluster:
            raw_values = [self._client.get(k) for k in full_keys]
        else:
            raw_values = self._client.mget(full_keys)
        result = {}
        for key, raw in zip(keys, raw_values):
            result[key] = self._pipeline.decode(raw)
        return result

    def set_many(self, mapping: dict[str, Any], ttl: str | int | None = None) -> None:
        resolved_ttl = self._resolve_ttl(ttl)
        keys_str = ",".join(mapping.keys())
        self._notify_hooks("before", "SET_MANY", keys_str, args=(mapping, ttl))
        start = time.monotonic()
        try:
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
        except Exception as e:
            self._notify_hooks("error", "SET_MANY", keys_str, error=e)
            raise
        duration = (time.monotonic() - start) * 1000
        self._notify_hooks("after", "SET_MANY", keys_str, result=None, duration_ms=duration)

    def delete_pattern(self, pattern: str, batch_size: int = 100) -> int:
        full_pattern = self._make_key(pattern)
        self._notify_hooks("before", "DELETE_PATTERN", pattern, args=(pattern,))
        start = time.monotonic()
        try:
            count = 0
            batch: list[bytes | str] = []
            for key in self._client.scan_iter(match=full_pattern, count=batch_size):
                batch.append(key)
                if len(batch) >= batch_size:
                    self._client.delete(*batch)
                    count += len(batch)
                    batch = []
            if batch:
                self._client.delete(*batch)
                count += len(batch)
        except Exception as e:
            self._notify_hooks("error", "DELETE_PATTERN", pattern, error=e)
            raise
        duration = (time.monotonic() - start) * 1000
        self._notify_hooks("after", "DELETE_PATTERN", pattern, result=count, duration_ms=duration)
        return count

    def iter_keys(self, pattern: str, batch_size: int = 100) -> Iterator[str]:
        full_pattern = self._make_key(pattern)
        prefix_len = len(self._prefix) + 1 if self._prefix else 0
        for key in self._client.scan_iter(match=full_pattern, count=batch_size):
            decoded = key.decode() if isinstance(key, bytes) else key
            yield decoded[prefix_len:] if prefix_len else decoded

    def bind(self, key: str) -> BoundCache:
        return BoundCache(self, key)
