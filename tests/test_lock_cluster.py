import fakeredis

from redis_kit.lock.lock import Lock


class TestLockClusterMode:
    def setup_method(self):
        self.client = fakeredis.FakeRedis(decode_responses=False)

    def teardown_method(self):
        self.client.flushall()
        self.client.close()

    def test_is_cluster_flag(self):
        lock = Lock(self.client, prefix="test:lock", is_cluster=True)
        assert lock._is_cluster is True

    def test_cluster_key_has_hash_tag(self):
        lock = Lock(self.client, prefix="test:lock", is_cluster=True)
        key = lock._make_key("resource-1")
        assert key == "{test:lock:resource-1}"

    def test_standalone_key_no_hash_tag(self):
        lock = Lock(self.client, prefix="test:lock", is_cluster=False)
        key = lock._make_key("resource-1")
        assert key == "test:lock:resource-1"

    def test_cluster_lock_acquire_release(self):
        lock = Lock(self.client, prefix="test:lock", is_cluster=True)
        with lock("resource-1", timeout=10):
            assert self.client.exists(b"{test:lock:resource-1}")
        assert not self.client.exists(b"{test:lock:resource-1}")

    def test_cluster_reentrant_lock(self):
        lock = Lock(self.client, prefix="test:lock", is_cluster=True)
        with lock("resource-1", timeout=10, reentrant=True):
            with lock("resource-1", timeout=10, reentrant=True):
                assert True
