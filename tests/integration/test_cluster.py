from redis_kit.cache.cache import Cache
from redis_kit.config import ClusterConfig
from redis_kit.connection import ConnectionManager
from redis_kit.counter.counter import Counter
from redis_kit.lock.lock import Lock
from tests.integration.conftest import CLUSTER_NODES, skip_no_cluster


@skip_no_cluster
class TestClusterIntegration:
    def test_connection_manager(self):
        nodes = [tuple(n.split(":")) for n in CLUSTER_NODES.split(",")]
        nodes = [(h, int(p)) for h, p in nodes]
        config = ClusterConfig(startup_nodes=nodes)
        conn = ConnectionManager(config=config)
        assert conn.topology == "cluster"
        assert conn.is_cluster is True
        client = conn.sync_client
        client.set("cluster_test", "value")
        assert client.get("cluster_test") == b"value"
        client.delete("cluster_test")
        conn.close()

    def test_cache_cluster_mode(self):
        nodes = [tuple(n.split(":")) for n in CLUSTER_NODES.split(",")]
        nodes = [(h, int(p)) for h, p in nodes]
        config = ClusterConfig(startup_nodes=nodes)
        conn = ConnectionManager(config=config)
        cache = Cache(conn.sync_client, prefix="inttest:cluster", ttl_jitter=0, is_cluster=True)
        cache.set("a", 1, ttl=60)
        cache.set("b", 2, ttl=60)
        assert cache.get("a") == 1
        result = cache.get_many(["a", "b", "c"])
        assert result == {"a": 1, "b": 2, "c": None}
        cache.set_many({"x": 10, "y": 20}, ttl=60)
        assert cache.get("x") == 10
        conn.close()

    def test_lock_cluster_hash_tag(self):
        nodes = [tuple(n.split(":")) for n in CLUSTER_NODES.split(",")]
        nodes = [(h, int(p)) for h, p in nodes]
        config = ClusterConfig(startup_nodes=nodes)
        conn = ConnectionManager(config=config)
        lock = Lock(conn.sync_client, prefix="inttest:lock", is_cluster=True)
        with lock("resource", timeout=10):
            pass
        conn.close()

    def test_counter_on_cluster(self):
        nodes = [tuple(n.split(":")) for n in CLUSTER_NODES.split(",")]
        nodes = [(h, int(p)) for h, p in nodes]
        config = ClusterConfig(startup_nodes=nodes)
        conn = ConnectionManager(config=config)
        c = Counter(conn.sync_client, prefix="inttest:counter")
        c.incr("views")
        assert c.get("views") == 1
        conn.close()
