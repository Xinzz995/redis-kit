from redis_kit.cache.cache import Cache
from redis_kit.config import SentinelConfig
from redis_kit.connection import ConnectionManager
from redis_kit.lock.lock import Lock
from tests.integration.conftest import SENTINEL_HOST, SENTINEL_PORT, skip_no_sentinel


@skip_no_sentinel
class TestSentinelIntegration:
    def test_connection_manager(self):
        config = SentinelConfig(
            sentinels=[(SENTINEL_HOST, SENTINEL_PORT)],
            service_name="mymaster",
        )
        conn = ConnectionManager(config=config)
        assert conn.topology == "sentinel"
        assert conn.is_sentinel is True
        client = conn.sync_client
        client.set("sentinel_test", "value")
        assert client.get("sentinel_test") == b"value"
        client.delete("sentinel_test")
        conn.close()

    def test_cache_via_sentinel(self):
        config = SentinelConfig(
            sentinels=[(SENTINEL_HOST, SENTINEL_PORT)],
            service_name="mymaster",
        )
        conn = ConnectionManager(config=config)
        cache = Cache(conn.sync_client, prefix="inttest:sentinel:cache", ttl_jitter=0)
        cache.set("key", {"data": "test"}, ttl=60)
        assert cache.get("key") == {"data": "test"}
        cache.delete("key")
        conn.close()

    def test_lock_via_sentinel(self):
        config = SentinelConfig(
            sentinels=[(SENTINEL_HOST, SENTINEL_PORT)],
            service_name="mymaster",
        )
        conn = ConnectionManager(config=config)
        lock = Lock(conn.sync_client, prefix="inttest:sentinel:lock")
        with lock("resource", timeout=10):
            pass  # Acquired and released
        conn.close()
