# 拓扑支持

通过更换 Config 对象即可在单机（Standalone）、哨兵（Sentinel）和集群（Cluster）之间切换。

## 单机模式（默认）

```python
from redis_kit import ConnectionManager, ConnectionConfig

conn = ConnectionManager(config=ConnectionConfig(host="localhost", port=6379))
# or
conn = ConnectionManager(url="redis://localhost:6379/0")
```

## 哨兵模式（Sentinel）

自动故障转移 —— 上层模块无感知。

```python
from redis_kit import ConnectionManager, SentinelConfig

conn = ConnectionManager(config=SentinelConfig(
    sentinels=[("sentinel1", 26379), ("sentinel2", 26379), ("sentinel3", 26379)],
    service_name="mymaster",
    password="secret",
))

cache = Cache(conn.sync_client, prefix="myapp:cache")
```

## 集群模式（Cluster）

跨多个主节点进行数据分片。

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

### 集群适配

| 功能 | 行为 |
|------|------|
| `get_many` / `set_many` | 自动降级为单条操作 |
| 锁的 Key | 使用 `{hash_tag}` 包裹，确保 Lua 脚本的 slot 安全 |
| `delete_pattern` / `iter_keys` | `scan_iter` 在所有节点上执行 |

## 拓扑检测

```python
conn.topology    # "standalone" | "sentinel" | "cluster"
conn.is_cluster  # bool
conn.is_sentinel # bool
```
