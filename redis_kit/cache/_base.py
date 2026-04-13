from __future__ import annotations

import logging
from typing import Any, Literal

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from redis_kit.cache._logic import DataPipeline, apply_jitter, parse_ttl
from redis_kit.compressors.base import Compressor
from redis_kit.hooks import CommandHook
from redis_kit.policy import FallbackPolicy
from redis_kit.serializers.base import Serializer

FALLBACK_ERRORS = (RedisConnectionError, RedisTimeoutError)

_logger = logging.getLogger("redis_kit.cache")


class CacheBase:
    """Shared logic for sync and async Cache implementations."""

    def __init__(
        self,
        client: Any,
        prefix: str = "",
        serializer: Serializer | None = None,
        compressor: Compressor | None = None,
        ttl_jitter: float = 0.1,
        fallback_policy: Any | None = None,
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

    def _apply_fallback_policy(self, error: Exception, command: str, key: str, default: Any = None) -> Any:
        """Evaluate FallbackPolicy for connection errors.

        Caller is responsible for awaiting the result if the callback is async.
        """
        if not isinstance(error, FALLBACK_ERRORS):
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

    def _notify_hooks(self, phase: Literal["before", "after", "error"], command: str, key: str, **kwargs: Any) -> None:
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
