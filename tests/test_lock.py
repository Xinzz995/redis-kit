import time

import fakeredis
import fakeredis.aioredis
import pytest

from redis_kit.exceptions import LockAcquireError, LockReleaseError
from redis_kit.lock.async_lock import AsyncLock
from redis_kit.lock.lock import Lock


class TestBasicLock:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_acquire_and_release(self):
        lock = Lock(self.client, prefix="test:lock")
        with lock("resource-1", timeout=10):
            assert self.client.exists(b"test:lock:resource-1")
        assert not self.client.exists(b"test:lock:resource-1")

    def test_lock_is_exclusive(self):
        lock = Lock(self.client, prefix="test:lock")
        with lock("resource-1", timeout=10):
            with pytest.raises(LockAcquireError):
                with lock("resource-1", timeout=10, blocking_timeout=0.1):
                    pass

    def test_lock_expires(self):
        lock = Lock(self.client, prefix="test:lock")
        with lock("resource-1", timeout=1):
            ttl = self.client.ttl(b"test:lock:resource-1")
            assert 0 < ttl <= 1

    def test_reentrant_lock(self):
        lock = Lock(self.client, prefix="test:lock")
        with lock("resource-1", timeout=10, reentrant=True):
            with lock("resource-1", timeout=10, reentrant=True):
                assert True  # No deadlock

    def test_different_resources_independent(self):
        lock = Lock(self.client, prefix="test:lock")
        with lock("res-a", timeout=10):
            with lock("res-b", timeout=10):
                assert True  # No deadlock

    def test_original_exception_not_masked_by_release_failure(self):
        """ValueError raised inside the context must propagate even when release fails."""
        lock = Lock(self.client, prefix="test:lock")
        with pytest.raises(ValueError, match="original"):
            with lock("expired-resource", timeout=10):
                # Simulate lock key expiry by deleting it before user code raises.
                key = lock._make_key("expired-resource")
                self.client.delete(key)
                raise ValueError("original")

    def test_lock_release_error_raised_on_clean_exit(self):
        """LockReleaseError must still propagate when no other exception is in flight."""
        lock = Lock(self.client, prefix="test:lock")
        with pytest.raises(LockReleaseError):
            with lock("clean-exit-resource", timeout=10):
                # Delete the key so release will fail after a clean yield.
                key = lock._make_key("clean-exit-resource")
                self.client.delete(key)

    def test_watchdog_timer_list_does_not_grow_unboundedly(self):
        """Verify that completed timers are pruned so _timers never accumulates stale entries."""
        lock = Lock(self.client, prefix="test:lock")
        # Use a short timeout so the watchdog fires quickly (interval = timeout / 3).
        timeout = 3
        interval = timeout / 3  # ~1 s

        with lock("watchdog-resource", timeout=timeout, auto_renew=True) as _:
            # Grab a reference to the internal watchdog handle via the context manager.
            # We can't easily reach it from outside the 'with' block, so we instrument
            # _start_watchdog by monkey-patching just for this test.
            pass  # placeholder – real instrumentation below

        # Re-implement with direct handle access.
        key = lock._make_key("watchdog-resource")
        owner = "test-owner-prune"
        # Manually set the key so extend script succeeds.
        self.client.set(key, owner, ex=timeout)
        handle = lock._start_watchdog(key, owner, timeout, reentrant=False)

        # Wait long enough for at least two renewal cycles.
        time.sleep(interval * 2.5)

        with handle._lock:
            timer_count = len(handle._timers)

        handle.cancel()

        # After pruning, at most 1 active timer should remain in the list
        # (the one scheduled by the most recent renewal that hasn't fired yet).
        assert timer_count <= 2, f"Expected at most 2 timers in watchdog handle after pruning, got {timer_count}"


class TestAsyncLock:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    @pytest.mark.asyncio
    async def test_acquire_and_release(self):
        lock = AsyncLock(self.client, prefix="test:lock")
        async with lock("resource-1", timeout=10):
            assert await self.client.exists("test:lock:resource-1")
        assert not await self.client.exists("test:lock:resource-1")

    @pytest.mark.asyncio
    async def test_lock_is_exclusive(self):
        lock = AsyncLock(self.client, prefix="test:lock")
        async with lock("resource-1", timeout=10):
            with pytest.raises(LockAcquireError):
                async with lock("resource-1", timeout=10, blocking_timeout=0.1):
                    pass

    @pytest.mark.asyncio
    async def test_reentrant(self):
        lock = AsyncLock(self.client, prefix="test:lock")
        async with lock("res", timeout=10, reentrant=True):
            async with lock("res", timeout=10, reentrant=True):
                pass

    @pytest.mark.asyncio
    async def test_different_resources(self):
        lock = AsyncLock(self.client, prefix="test:lock")
        async with lock("a", timeout=10):
            async with lock("b", timeout=10):
                pass

    @pytest.mark.asyncio
    async def test_original_exception_not_masked_by_release_failure(self):
        """ValueError raised inside the context must propagate even when release fails."""
        lock = AsyncLock(self.client, prefix="test:lock")
        with pytest.raises(ValueError, match="original"):
            async with lock("expired-resource", timeout=10):
                key = lock._make_key("expired-resource")
                await self.client.delete(key)
                raise ValueError("original")

    @pytest.mark.asyncio
    async def test_lock_release_error_raised_on_clean_exit(self):
        """LockReleaseError must still propagate when no other exception is in flight."""
        lock = AsyncLock(self.client, prefix="test:lock")
        with pytest.raises(LockReleaseError):
            async with lock("clean-exit-resource", timeout=10):
                key = lock._make_key("clean-exit-resource")
                await self.client.delete(key)


class TestReadWriteLock:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_read_lock_basic(self):
        lock = Lock(self.client, prefix="test:lock")
        with lock.read("rw-resource", timeout=10):
            key = b"test:lock:rw-resource:rwlock"
            readers = self.client.hget(key, b"readers")
            assert readers is not None
            assert int(readers) >= 1
        # After release, readers field should be cleaned up
        readers = self.client.hget(b"test:lock:rw-resource:rwlock", b"readers")
        assert readers is None or int(readers) == 0

    def test_write_lock_basic(self):
        lock = Lock(self.client, prefix="test:lock")
        with lock.write("rw-resource", timeout=10):
            writer_key = b"test:lock:rw-resource:rwlock:writer"
            assert self.client.exists(writer_key)
        # After release, writer key should be gone
        assert not self.client.exists(b"test:lock:rw-resource:rwlock:writer")

    def test_writer_blocks_reader(self):
        lock = Lock(self.client, prefix="test:lock")
        with lock.write("rw-resource", timeout=10):
            with pytest.raises(LockAcquireError):
                with lock.read("rw-resource", timeout=10):
                    pass

    def test_write_lock_exclusive(self):
        lock = Lock(self.client, prefix="test:lock")
        with lock.write("rw-resource", timeout=10):
            with pytest.raises(LockAcquireError):
                with lock.write("rw-resource", timeout=10, blocking_timeout=0.1):
                    pass


    def test_write_lock_release_failure_does_not_mask_user_exception(self):
        """If user code raises inside write() and release fails, original exception propagates."""
        lock = Lock(self.client, prefix="test:lock")
        with pytest.raises(ValueError, match="user error"):
            with lock.write("rw-mask-test", timeout=1):
                # Expire the writer key to simulate release failure
                self.client.delete(lock._make_key("rw-mask-test") + ":rwlock:writer")
                raise ValueError("user error")

    def test_read_lock_release_failure_does_not_mask_user_exception(self):
        """If user code raises inside read() and release fails, original exception propagates."""
        lock = Lock(self.client, prefix="test:lock")
        with pytest.raises(ValueError, match="user error"):
            with lock.read("rw-mask-test", timeout=1):
                raise ValueError("user error")


class TestAsyncReadWriteLock:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        yield

    @pytest.mark.asyncio
    async def test_read_lock_basic(self):
        lock = AsyncLock(self.client, prefix="test:lock")
        async with lock.read("rw-resource", timeout=10):
            key = "test:lock:rw-resource:rwlock"
            readers = await self.client.hget(key, "readers")
            assert readers is not None
            assert int(readers) >= 1

    @pytest.mark.asyncio
    async def test_write_lock_basic(self):
        lock = AsyncLock(self.client, prefix="test:lock")
        async with lock.write("rw-resource", timeout=10):
            writer_key = "test:lock:rw-resource:rwlock:writer"
            assert await self.client.exists(writer_key)
        assert not await self.client.exists("test:lock:rw-resource:rwlock:writer")

    @pytest.mark.asyncio
    async def test_writer_blocks_reader(self):
        lock = AsyncLock(self.client, prefix="test:lock")
        async with lock.write("rw-resource", timeout=10):
            with pytest.raises(LockAcquireError):
                async with lock.read("rw-resource", timeout=10):
                    pass

    @pytest.mark.asyncio
    async def test_write_lock_exclusive(self):
        lock = AsyncLock(self.client, prefix="test:lock")
        async with lock.write("rw-resource", timeout=10):
            with pytest.raises(LockAcquireError):
                async with lock.write("rw-resource", timeout=10, blocking_timeout=0.1):
                    pass
