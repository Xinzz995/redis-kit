import os

import pytest
import redis

STANDALONE_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
SENTINEL_HOST = os.environ.get("REDIS_SENTINEL_HOST", "localhost")
SENTINEL_PORT = int(os.environ.get("REDIS_SENTINEL_PORT", "26379"))
CLUSTER_NODES = os.environ.get("REDIS_CLUSTER_NODES", "localhost:7001,localhost:7002,localhost:7003")


def is_redis_available(url: str) -> bool:
    try:
        client = redis.Redis.from_url(url, socket_timeout=2)
        client.ping()
        client.close()
        return True
    except Exception:
        return False


skip_no_redis = pytest.mark.skipif(
    not is_redis_available(STANDALONE_URL),
    reason="Redis standalone not available",
)


def is_sentinel_available() -> bool:
    try:
        s = redis.sentinel.Sentinel([(SENTINEL_HOST, SENTINEL_PORT)], socket_timeout=2)
        s.discover_master("mymaster")
        return True
    except Exception:
        return False


skip_no_sentinel = pytest.mark.skipif(
    not is_sentinel_available(),
    reason="Redis Sentinel not available",
)


def is_cluster_available() -> bool:
    try:
        from redis.cluster import ClusterNode, RedisCluster

        nodes_str = CLUSTER_NODES.split(",")
        nodes = [ClusterNode(h.split(":")[0], int(h.split(":")[1])) for h in nodes_str]
        client = RedisCluster(startup_nodes=nodes, socket_timeout=2)
        client.ping()
        client.close()
        return True
    except Exception:
        return False


skip_no_cluster = pytest.mark.skipif(
    not is_cluster_available(),
    reason="Redis Cluster not available",
)


@pytest.fixture
def standalone_client():
    client = redis.Redis.from_url(STANDALONE_URL, decode_responses=False)
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def sentinel_client():
    s = redis.sentinel.Sentinel([(SENTINEL_HOST, SENTINEL_PORT)], socket_timeout=5)
    client = s.master_for("mymaster", decode_responses=False)
    yield client
    client.flushdb()


@pytest.fixture
def cluster_client():
    from redis.cluster import ClusterNode, RedisCluster

    nodes_str = CLUSTER_NODES.split(",")
    nodes = [ClusterNode(h.split(":")[0], int(h.split(":")[1])) for h in nodes_str]
    client = RedisCluster(startup_nodes=nodes, decode_responses=False)
    yield client
    client.flushdb()
    client.close()
