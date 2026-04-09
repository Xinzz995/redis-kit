from redis_kit.cache.cache import Cache
from redis_kit.lock.lock import Lock
from tests.integration.conftest import skip_no_sentinel


@skip_no_sentinel
class TestSentinelIntegration:
    """Test modules against Redis Sentinel master (via direct port mapping).

    On Docker Desktop, Sentinel's discover_master returns container-internal IPs
    that are not reachable from the host. We connect directly to the master's
    mapped port (6380) to verify modules work against a real Redis instance.
    """

    def test_basic_operations(self, sentinel_master_client):
        sentinel_master_client.set("sentinel_test", "value")
        assert sentinel_master_client.get("sentinel_test") == b"value"
        sentinel_master_client.delete("sentinel_test")

    def test_cache_operations(self, sentinel_master_client):
        cache = Cache(sentinel_master_client, prefix="inttest:sentinel:cache", ttl_jitter=0)
        cache.set("key", {"data": "test"}, ttl=60)
        assert cache.get("key") == {"data": "test"}
        cache.delete("key")
        assert cache.get("key") is None

    def test_lock_operations(self, sentinel_master_client):
        lock = Lock(sentinel_master_client, prefix="inttest:sentinel:lock")
        with lock("resource", timeout=10):
            assert sentinel_master_client.exists("inttest:sentinel:lock:resource")
        assert not sentinel_master_client.exists("inttest:sentinel:lock:resource")
