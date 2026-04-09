from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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
    import redis.asyncio


class AsyncLock:
    """Async Redis distributed lock with async context manager support."""

    def __init__(self, client: redis.asyncio.Redis, prefix: str = "") -> None:
        self._client = client
        self._prefix = prefix
        self._release_script = self._client.register_script(RELEASE_LOCK)
        self._reentrant_acquire_script = self._client.register_script(REENTRANT_ACQUIRE)
        self._reentrant_release_script = self._client.register_script(REENTRANT_RELEASE)
        self._extend_script = self._client.register_script(EXTEND_LOCK)
        self._extend_reentrant_script = self._client.register_script(EXTEND_REENTRANT_LOCK)

    def _make_key(self, name: str) -> str:
        return f"{self._prefix}:{name}" if self._prefix else name

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
            owner = f"task:{id(task)}" if task else owner
            acquired = await self._acquire_reentrant(key, owner, timeout, blocking_timeout)
        else:
            acquired = await self._acquire_basic(key, owner, timeout, blocking_timeout)

        if not acquired:
            raise LockAcquireError(f"Failed to acquire lock '{name}'")

        try:
            if auto_renew:
                renew_task = asyncio.create_task(self._watchdog(key, owner, timeout, reentrant))
            yield
        finally:
            if renew_task is not None:
                renew_task.cancel()
            if reentrant:
                await self._release_reentrant(key, owner, name)
            else:
                await self._release_basic(key, owner, name)

    async def _acquire_basic(self, key: str, owner: str, timeout: int, blocking_timeout: float | None) -> bool:
        if blocking_timeout is not None:
            import time

            deadline = time.monotonic() + blocking_timeout
            while time.monotonic() < deadline:
                if await self._client.set(key, owner, nx=True, ex=timeout):
                    return True
                await asyncio.sleep(0.05)
            return False
        return bool(await self._client.set(key, owner, nx=True, ex=timeout))

    async def _release_basic(self, key: str, owner: str, name: str) -> None:
        result = await self._release_script(keys=[key], args=[owner])
        if not result:
            raise LockReleaseError(f"Failed to release lock '{name}': not owner")

    async def _acquire_reentrant(self, key: str, owner: str, timeout: int, blocking_timeout: float | None) -> bool:
        if blocking_timeout is not None:
            import time

            deadline = time.monotonic() + blocking_timeout
            while time.monotonic() < deadline:
                if await self._reentrant_acquire_script(keys=[key], args=[owner, timeout]):
                    return True
                await asyncio.sleep(0.05)
            return False
        return bool(await self._reentrant_acquire_script(keys=[key], args=[owner, timeout]))

    async def _release_reentrant(self, key: str, owner: str, name: str) -> None:
        result = await self._reentrant_release_script(keys=[key], args=[owner])
        if not result:
            raise LockReleaseError(f"Failed to release reentrant lock '{name}': not owner")

    async def _watchdog(self, key: str, owner: str, timeout: int, reentrant: bool) -> None:
        interval = timeout / 3
        script = self._extend_reentrant_script if reentrant else self._extend_script
        while True:
            await asyncio.sleep(interval)
            result = await script(keys=[key], args=[owner, timeout])
            if not result:
                break

    @asynccontextmanager
    async def read(self, name: str, timeout: int = 10) -> AsyncIterator[None]:
        """Acquire a read lock (shared). Multiple readers allowed."""
        key = self._make_key(name) + ":rwlock"
        await self._client.hincrby(key, "readers", 1)
        await self._client.expire(key, timeout)
        try:
            yield
        finally:
            await self._client.hincrby(key, "readers", -1)

    @asynccontextmanager
    async def write(self, name: str, timeout: int = 10, blocking_timeout: float = 5.0) -> AsyncIterator[None]:
        """Acquire a write lock (exclusive). Waits for readers to finish."""
        import time

        key = self._make_key(name) + ":rwlock"
        owner = uuid.uuid4().hex
        deadline = time.monotonic() + blocking_timeout

        while time.monotonic() < deadline:
            if await self._client.set(key + ":writer", owner, nx=True, ex=timeout):
                break
            await asyncio.sleep(0.05)
        else:
            raise LockAcquireError(f"Failed to acquire write lock '{name}'")

        while time.monotonic() < deadline:
            readers = await self._client.hget(key, "readers")
            if readers is None or int(readers) <= 0:
                break
            await asyncio.sleep(0.05)
        else:
            await self._client.delete(key + ":writer")
            raise LockAcquireError(f"Write lock '{name}': readers did not drain in time")

        try:
            yield
        finally:
            await self._client.delete(key + ":writer")
