import fakeredis
import pytest

from redis_kit.exceptions import LockAcquireError
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
