from __future__ import annotations

import logging
from typing import Any

from redis_kit.cache._logic import DataPipeline, apply_jitter, parse_ttl
from redis_kit.compressors.base import Compressor
from redis_kit.hooks import CommandHook
from redis_kit.serializers.base import Serializer

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
        from redis_kit.policy import FallbackPolicy

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
