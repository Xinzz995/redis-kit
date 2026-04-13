from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from redis_kit.exceptions import LockAcquireError, LockReleaseError
from redis_kit.lock._base import LockBase

_logger = logging.getLogger("redis_kit")


class AsyncLock(LockBase):
    """Async Redis distributed lock with async context manager support."""

    async def _spin_acquire(self, attempt: Callable[[], Any], blocking_timeout: float | None) -> bool:
        """Spin-wait for a lock acquisition attempt, with optional timeout."""
        if blocking_timeout is not None:
            deadline = time.monotonic() + blocking_timeout
            while time.monotonic() < deadline:
                if await attempt():
                    return True
                await asyncio.sleep(0.05)
            return False
        return bool(await attempt())

    @asynccontextmanager
    async def __call__(
        self,
        name: str,
        timeout: int = 10,
        blocking_timeout: float | None = None,
        reentrant: bool = False,
        auto_renew: bool = False,
    ) -> AsyncIterator[None]:
        key = self._make_key(name)
        owner = uuid.uuid4().hex
        renew_task: asyncio.Task[None] | None = None

        if reentrant:
            task = asyncio.current_task()
            owner = f"task:{os.getpid()}:{id(task)}" if task else owner
            acquired = await self._spin_acquire(
                lambda: self._reentrant_acquire_script(keys=[key], args=[owner, timeout]),
                blocking_timeout,
            )
        else:
            acquired = await self._spin_acquire(
                lambda: self._client.set(key, owner, nx=True, ex=timeout),
                blocking_timeout,
            )

        if not acquired:
            raise LockAcquireError(f"Failed to acquire lock '{name}'")

        try:
            if auto_renew:
                renew_task = asyncio.create_task(self._watchdog(key, owner, timeout, reentrant))
            yield
        except BaseException:
            # An exception is already in flight — release the lock but don't mask it.
            if renew_task is not None:
                renew_task.cancel()
            try:
                if reentrant:
                    await self._release_reentrant(key, owner, name)
                else:
                    await self._release_basic(key, owner, name)
            except LockReleaseError:
                _logger.warning("Failed to release lock '%s' while handling another exception", name)
            raise
        else:
            # Normal (no-exception) path — release errors ARE propagated.
            if renew_task is not None:
                renew_task.cancel()
            if reentrant:
                await self._release_reentrant(key, owner, name)
            else:
                await self._release_basic(key, owner, name)

    async def _release_basic(self, key: str, owner: str, name: str) -> None:
        result = await self._release_script(keys=[key], args=[owner])
        if not result:
            raise LockReleaseError(f"Failed to release lock '{name}': not owner")

    async def _release_reentrant(self, key: str, owner: str, name: str) -> None:
        result = await self._reentrant_release_script(keys=[key], args=[owner])
        if not result:
            raise LockReleaseError(f"Failed to release reentrant lock '{name}': not owner")

    async def _release_write(self, writer_key: str, owner: str, name: str) -> None:
        result = await self._write_release_script(keys=[writer_key], args=[owner])
        if not result:
            raise LockReleaseError(f"Failed to release write lock '{name}': not owner")

    async def _watchdog(self, key: str, owner: str, timeout: int, reentrant: bool) -> None:
        interval = timeout / 3
        script = self._extend_reentrant_script if reentrant else self._extend_script
        while True:
            await asyncio.sleep(interval)
            result = await script(keys=[key], args=[owner, timeout])
            if not result:
                break

    @asynccontextmanager
    async def read(self, name: str, timeout: int = 10, blocking_timeout: float | None = None) -> AsyncIterator[None]:
        """Acquire a read lock (shared). Multiple readers allowed.

        Uses reader-preference policy: continuous readers may starve writers
        under high contention. Exception-safe (see ``__call__``).
        """
        key = self._make_key(name) + ":rwlock"
        writer_key = key + ":writer"
        acquired = await self._spin_acquire(
            lambda: self._read_acquire_script(keys=[key, writer_key], args=[timeout]),
            blocking_timeout,
        )
        if not acquired:
            raise LockAcquireError(f"Failed to acquire read lock '{name}': writer active")
        try:
            yield
        except BaseException:
            try:
                await self._read_release_script(keys=[key], args=[])
            except LockReleaseError:
                _logger.warning("Failed to release read lock '%s' while handling another exception", name)
            raise
        else:
            await self._read_release_script(keys=[key], args=[])

    @asynccontextmanager
    async def write(
        self, name: str, timeout: int = 10, blocking_timeout: float = 5.0, auto_renew: bool = False
    ) -> AsyncIterator[None]:
        """Acquire a write lock (exclusive). Waits for readers to finish.

        Exception-safe: release failures do not mask the original exception (see ``__call__``).
        """
        key = self._make_key(name) + ":rwlock"
        writer_key = key + ":writer"
        owner = uuid.uuid4().hex
        renew_task: asyncio.Task[None] | None = None

        acquired = await self._spin_acquire(
            lambda: self._write_acquire_script(keys=[key, writer_key], args=[owner, timeout]),
            blocking_timeout,
        )
        if not acquired:
            raise LockAcquireError(f"Failed to acquire write lock '{name}'")

        try:
            if auto_renew:
                renew_task = asyncio.create_task(self._watchdog(writer_key, owner, timeout, reentrant=False))
            yield
        except BaseException:
            if renew_task is not None:
                renew_task.cancel()
            try:
                await self._release_write(writer_key, owner, name)
            except LockReleaseError:
                _logger.warning("Failed to release write lock '%s' while handling another exception", name)
            raise
        else:
            if renew_task is not None:
                renew_task.cancel()
            await self._release_write(writer_key, owner, name)
