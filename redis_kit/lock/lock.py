from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

from redis_kit.exceptions import LockAcquireError, LockReleaseError
from redis_kit.lock._lua import (
    EXTEND_LOCK,
    EXTEND_REENTRANT_LOCK,
    REENTRANT_ACQUIRE,
    REENTRANT_RELEASE,
    RELEASE_LOCK,
)

if TYPE_CHECKING:
    import redis


class Lock:
    """Redis distributed lock with context manager support."""

    def __init__(self, client: redis.Redis, prefix: str = "") -> None:
        self._client = client
        self._prefix = prefix
        self._release_script = self._client.register_script(RELEASE_LOCK)
        self._reentrant_acquire_script = self._client.register_script(REENTRANT_ACQUIRE)
        self._reentrant_release_script = self._client.register_script(REENTRANT_RELEASE)
        self._extend_script = self._client.register_script(EXTEND_LOCK)
        self._extend_reentrant_script = self._client.register_script(EXTEND_REENTRANT_LOCK)

    def _make_key(self, name: str) -> str:
        return f"{self._prefix}:{name}" if self._prefix else name

    @contextmanager
    def __call__(
        self,
        name: str,
        timeout: int = 10,
        blocking_timeout: float | None = None,
        reentrant: bool = False,
        auto_renew: bool = False,
    ) -> Iterator[None]:
        key = self._make_key(name)
        owner = f"{threading.current_thread().ident}:{uuid.uuid4().hex[:8]}"
        renew_timer: threading.Timer | None = None

        if reentrant:
            owner = f"thread:{threading.current_thread().ident}"
            acquired = self._acquire_reentrant(key, owner, timeout, blocking_timeout)
        else:
            acquired = self._acquire_basic(key, owner, timeout, blocking_timeout)

        if not acquired:
            raise LockAcquireError(f"Failed to acquire lock '{name}'")

        try:
            if auto_renew:
                renew_timer = self._start_watchdog(key, owner, timeout, reentrant)
            yield
        finally:
            if renew_timer is not None:
                renew_timer.cancel()
            if reentrant:
                self._release_reentrant(key, owner, name)
            else:
                self._release_basic(key, owner, name)

    def _acquire_basic(
        self, key: str, owner: str, timeout: int, blocking_timeout: float | None
    ) -> bool:
        if blocking_timeout is not None:
            import time

            deadline = time.monotonic() + blocking_timeout
            while time.monotonic() < deadline:
                if self._client.set(key, owner, nx=True, ex=timeout):
                    return True
                time.sleep(0.05)
            return False
        return bool(self._client.set(key, owner, nx=True, ex=timeout))

    def _release_basic(self, key: str, owner: str, name: str) -> None:
        result = self._release_script(keys=[key], args=[owner])
        if not result:
            raise LockReleaseError(f"Failed to release lock '{name}': not owner")

    def _acquire_reentrant(
        self, key: str, owner: str, timeout: int, blocking_timeout: float | None
    ) -> bool:
        if blocking_timeout is not None:
            import time

            deadline = time.monotonic() + blocking_timeout
            while time.monotonic() < deadline:
                if self._reentrant_acquire_script(keys=[key], args=[owner, timeout]):
                    return True
                time.sleep(0.05)
            return False
        return bool(self._reentrant_acquire_script(keys=[key], args=[owner, timeout]))

    def _release_reentrant(self, key: str, owner: str, name: str) -> None:
        result = self._reentrant_release_script(keys=[key], args=[owner])
        if not result:
            raise LockReleaseError(f"Failed to release reentrant lock '{name}': not owner")

    def _start_watchdog(
        self, key: str, owner: str, timeout: int, reentrant: bool
    ) -> threading.Timer:
        interval = timeout / 3

        def renew() -> None:
            script = self._extend_reentrant_script if reentrant else self._extend_script
            result = script(keys=[key], args=[owner, timeout])
            if result:
                timer = threading.Timer(interval, renew)
                timer.daemon = True
                timer.start()

        timer = threading.Timer(interval, renew)
        timer.daemon = True
        timer.start()
        return timer

    @contextmanager
    def read(self, name: str, timeout: int = 10) -> Iterator[None]:
        """Acquire a read lock (shared). Multiple readers allowed."""
        key = self._make_key(name) + ":rwlock"
        self._client.hincrby(key, "readers", 1)
        self._client.expire(key, timeout)
        try:
            yield
        finally:
            self._client.hincrby(key, "readers", -1)

    @contextmanager
    def write(self, name: str, timeout: int = 10, blocking_timeout: float = 5.0) -> Iterator[None]:
        """Acquire a write lock (exclusive). Waits for readers to finish."""
        import time

        key = self._make_key(name) + ":rwlock"
        owner = uuid.uuid4().hex
        deadline = time.monotonic() + blocking_timeout

        while time.monotonic() < deadline:
            if self._client.set(key + ":writer", owner, nx=True, ex=timeout):
                break
            time.sleep(0.05)
        else:
            raise LockAcquireError(f"Failed to acquire write lock '{name}'")

        while time.monotonic() < deadline:
            readers = self._client.hget(key, "readers")
            if readers is None or int(readers) <= 0:
                break
            time.sleep(0.05)
        else:
            self._client.delete(key + ":writer")
            raise LockAcquireError(f"Write lock '{name}': readers did not drain in time")

        try:
            yield
        finally:
            self._client.delete(key + ":writer")
