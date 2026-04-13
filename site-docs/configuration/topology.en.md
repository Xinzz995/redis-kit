# Topology Support

Switch between Standalone, Sentinel, and Cluster modes by swapping the config object.

## Standalone (Default)

```python
from redis_kit import ConnectionManager, ConnectionConfig

conn = ConnectionManager(config=ConnectionConfig(host="localhost", port=6379))
# or
conn = ConnectionManager(url="redis://localhost:6379/0")
```

!!! warning "`url` is standalone-only"
    The `url` parameter is only supported with `ConnectionConfig` (standalone mode). Passing `url` with `SentinelConfig` or `ClusterConfig` raises `ValueError`.

## Sentinel

Automatic failover -- transparent to upper-layer modules.

```python
from redis_kit import ConnectionManager, SentinelConfig

conn = ConnectionManager(config=SentinelConfig(
    sentinels=[("sentinel1", 26379), ("sentinel2", 26379), ("sentinel3", 26379)],
    service_name="mymaster",
    password="secret",
))

cache = Cache(conn.sync_client, prefix="myapp:cache")
```

## Cluster

Data sharding across multiple master nodes.

```python
from redis_kit import ConnectionManager, ClusterConfig, Cache, Lock

conn = ConnectionManager(config=ClusterConfig(
    startup_nodes=[("node1", 6379), ("node2", 6379), ("node3", 6379)],
    password="secret",
    read_from_replicas=True,
))

cache = Cache(conn.sync_client, prefix="myapp:cache", is_cluster=conn.is_cluster)
lock = Lock(conn.sync_client, prefix="myapp:lock", is_cluster=conn.is_cluster)
```

### Cluster Adaptations

| Feature | Behavior |
|---------|----------|
| `get_many` / `set_many` | Automatically falls back to single-key operations |
| Lock keys | Wrapped in `{hash_tag}` for Lua script slot safety |
| `delete_pattern` / `iter_keys` | `scan_iter` executes across all nodes |

## Topology Detection

```python
conn.topology    # "standalone" | "sentinel" | "cluster"
conn.is_cluster  # bool
conn.is_sentinel # bool
```
