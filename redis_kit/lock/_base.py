from __future__ import annotations

from typing import Any

from redis_kit.lock._lua import (
    EXTEND_LOCK,
    EXTEND_REENTRANT_LOCK,
    READ_ACQUIRE,
    READ_RELEASE,
    REENTRANT_ACQUIRE,
    REENTRANT_RELEASE,
    RELEASE_LOCK,
    WRITE_ACQUIRE,
    WRITE_RELEASE,
)


class LockBase:
    """Shared logic for sync and async Lock implementations."""

    def __init__(self, client: Any, prefix: str = "", is_cluster: bool = False) -> None:
        self._client = client
        self._prefix = prefix
        self._is_cluster = is_cluster
        self._release_script = self._client.register_script(RELEASE_LOCK)
        self._reentrant_acquire_script = self._client.register_script(REENTRANT_ACQUIRE)
        self._reentrant_release_script = self._client.register_script(REENTRANT_RELEASE)
        self._extend_script = self._client.register_script(EXTEND_LOCK)
        self._extend_reentrant_script = self._client.register_script(EXTEND_REENTRANT_LOCK)
        self._read_acquire_script = self._client.register_script(READ_ACQUIRE)
        self._read_release_script = self._client.register_script(READ_RELEASE)
        self._write_acquire_script = self._client.register_script(WRITE_ACQUIRE)
        self._write_release_script = self._client.register_script(WRITE_RELEASE)

    def _make_key(self, name: str) -> str:
        base = f"{self._prefix}:{name}" if self._prefix else name
        if self._is_cluster:
            return f"{{{base}}}"
        return base
