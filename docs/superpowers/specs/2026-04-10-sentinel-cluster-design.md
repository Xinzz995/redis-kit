# redis-py-kit v2: Sentinel & Cluster 拓扑支持设计

## 1. 概述

为 redis-py-kit 添加 Redis Sentinel 和 Cluster 拓扑支持。用户只需更换 Config 对象即可切换拓扑，所有下游模块（Cache、Lock、Queue 等）零修改或最小适配。

### 设计原则

- **Config 多态做拓扑判别**：传 `ConnectionConfig` = Standalone，传 `SentinelConfig` = Sentinel，传 `ClusterConfig` = Cluster（借鉴 Spring Data Redis）
- **Sentinel 是连接池级关注点**：返回普通 `redis.Redis` 对象，上层完全无感（借鉴 redis-py）
- **Cluster 多 key 操作自动降级**：按 slot 分组拆分，不静默失败（借鉴 cashews `_group_pairs_by_slot`）
- **Lock 用 hash tag 保证同 slot**：Lua 脚本在 Cluster 下正常工作（借鉴 redis-py Cluster Lua 约束）
- **向后兼容**：v1 的 `ConnectionConfig` 用法不变

### 参考来源

| 来源 | 借鉴内容 |
|------|---------|
| Spring Data Redis | typed config 多态做拓扑判别 |
| redis-py | Sentinel 返回普通 Redis 对象；Cluster pipeline 命令黑名单 |
| cashews | `group_keys_by_slot()` 按 slot 拆分多 key 操作 |
| django-redis | 连接工厂抽象，拓扑差异封装在工厂内 |
| Lettuce | `StatefulConnection` 统一命令接口 |

## 2. Config 层

### 现有（不变）

```python
@dataclass(frozen=True)
class ConnectionConfig:
    """Standalone Redis 配置。"""
    url: str | None = None
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    decode_responses: bool = False
    ssl: bool = False
```

### 新增

```python
@dataclass(frozen=True)
class SentinelConfig:
    """Redis Sentinel 配置。"""
    sentinels: list[tuple[str, int]]       # Sentinel 节点列表
    service_name: str                       # 主节点服务名
    db: int = 0
    password: str | None = None            # Redis 实例密码
    sentinel_password: str | None = None   # Sentinel 节点自身密码
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    decode_responses: bool = False
    ssl: bool = False

@dataclass(frozen=True)
class ClusterConfig:
    """Redis Cluster 配置。"""
    startup_nodes: list[tuple[str, int]]   # 启动节点列表（至少一个）
    password: str | None = None
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    decode_responses: bool = False
    ssl: bool = False
    read_from_replicas: bool = False       # 是否从副本读取
```

类型联合：`TopologyConfig = ConnectionConfig | SentinelConfig | ClusterConfig`

## 3. ConnectionManager 改动

### 构造函数

```python
class ConnectionManager:
    def __init__(
        self,
        url: str | None = None,
        config: ConnectionConfig | SentinelConfig | ClusterConfig | None = None,
    ) -> None:
        self._url = url
        self._config = config or ConnectionConfig()
        ...
```

### 拓扑属性

```python
@property
def is_cluster(self) -> bool:
    """是否为 Cluster 模式，供下游模块判断。"""
    return isinstance(self._config, ClusterConfig)

@property
def is_sentinel(self) -> bool:
    """是否为 Sentinel 模式。"""
    return isinstance(self._config, SentinelConfig)

@property
def topology(self) -> str:
    """返回当前拓扑类型字符串。"""
    if isinstance(self._config, ClusterConfig):
        return "cluster"
    if isinstance(self._config, SentinelConfig):
        return "sentinel"
    return "standalone"
```

### 构建逻辑分发

```python
def _build_sync_client(self) -> redis.Redis | redis.cluster.RedisCluster:
    if isinstance(self._config, SentinelConfig):
        return self._build_sentinel_sync()
    if isinstance(self._config, ClusterConfig):
        return self._build_cluster_sync()
    return self._build_standalone_sync()
```

同样适用于 `_build_async_client()`。

### Sentinel 构建

```python
def _build_sentinel_sync(self) -> redis.Redis:
    sentinel = redis.sentinel.Sentinel(
        self._config.sentinels,
        password=self._config.sentinel_password,
        socket_timeout=self._config.socket_timeout,
    )
    return sentinel.master_for(
        self._config.service_name,
        password=self._config.password,
        db=self._config.db,
        max_connections=self._config.max_connections,
        socket_timeout=self._config.socket_timeout,
        socket_connect_timeout=self._config.socket_connect_timeout,
        decode_responses=self._config.decode_responses,
    )

async def _build_sentinel_async(self) -> redis.asyncio.Redis:
    sentinel = redis.asyncio.sentinel.Sentinel(
        self._config.sentinels,
        password=self._config.sentinel_password,
        socket_timeout=self._config.socket_timeout,
    )
    return sentinel.master_for(
        self._config.service_name,
        password=self._config.password,
        db=self._config.db,
        max_connections=self._config.max_connections,
        socket_timeout=self._config.socket_timeout,
        socket_connect_timeout=self._config.socket_connect_timeout,
        decode_responses=self._config.decode_responses,
    )
```

关键点：`sentinel.master_for()` 返回的是普通 `redis.Redis` 对象，底层用 `SentinelConnectionPool` 自动处理故障转移。上游模块完全无感。

### Cluster 构建

```python
def _build_cluster_sync(self) -> redis.cluster.RedisCluster:
    from redis.cluster import ClusterNode, RedisCluster
    nodes = [ClusterNode(h, p) for h, p in self._config.startup_nodes]
    return RedisCluster(
        startup_nodes=nodes,
        password=self._config.password,
        max_connections=self._config.max_connections,
        socket_timeout=self._config.socket_timeout,
        socket_connect_timeout=self._config.socket_connect_timeout,
        decode_responses=self._config.decode_responses,
        ssl=self._config.ssl,
    )

def _build_cluster_async(self) -> redis.asyncio.RedisCluster:
    from redis.asyncio.cluster import ClusterNode, RedisCluster
    nodes = [ClusterNode(h, p) for h, p in self._config.startup_nodes]
    return RedisCluster(
        startup_nodes=nodes,
        password=self._config.password,
        max_connections=self._config.max_connections,
        socket_timeout=self._config.socket_timeout,
        socket_connect_timeout=self._config.socket_connect_timeout,
        decode_responses=self._config.decode_responses,
        ssl=self._config.ssl,
    )
```

### close / aclose

Cluster 的关闭方式不同，需要适配：

```python
def close(self) -> None:
    if self._sync_client is not None:
        if isinstance(self._sync_client, redis.cluster.RedisCluster):
            self._sync_client.close()
        else:
            self._sync_client.close()
        self._sync_client = None
```

实际上 `RedisCluster.close()` 和 `Redis.close()` 接口一致，无需特殊处理。

## 4. Cluster 多 key 操作适配

### 工具函数

新增 `redis_kit/cache/_cluster.py`：

```python
from collections import defaultdict


def group_keys_by_slot(client, keys: list[str]) -> dict[int, list[str]]:
    """按 CRC16 slot 分组 key，用于 Cluster 下拆分多 key 操作。"""
    groups: dict[int, list[str]] = defaultdict(list)
    for key in keys:
        slot = client.keyslot(key)
        groups[slot].append(key)
    return groups
```

### Cache 适配

在 `Cache` 和 `AsyncCache` 构造函数中接受 `is_cluster: bool = False` 参数：

```python
class Cache:
    def __init__(self, client, prefix="", ..., is_cluster: bool = False):
        self._is_cluster = is_cluster
        ...
```

#### get_many — Cluster 下按 slot 分组

```python
def get_many(self, keys: list[str]) -> dict[str, Any]:
    full_keys = [self._make_key(k) for k in keys]
    if self._is_cluster:
        raw_values = self._cluster_mget(full_keys)
    else:
        raw_values = self._client.mget(full_keys)
    result = {}
    for key, raw in zip(keys, raw_values):
        val = self._pipeline.decode(raw)
        result[key] = val if val is not _MISS else None
    return result

def _cluster_mget(self, keys: list[str]) -> list[bytes | None]:
    groups = group_keys_by_slot(self._client, keys)
    result_map = {}
    for slot_keys in groups.values():
        values = self._client.mget(slot_keys)
        for k, v in zip(slot_keys, values):
            result_map[k] = v
    return [result_map.get(k) for k in keys]
```

#### set_many — Cluster 下按 slot 分组

```python
def set_many(self, mapping: dict[str, Any], ttl=None) -> None:
    resolved_ttl = self._resolve_ttl(ttl)
    if self._is_cluster:
        for key, value in mapping.items():
            full_key = self._make_key(key)
            encoded = self._pipeline.encode(value)
            if resolved_ttl is not None and resolved_ttl > 0:
                self._client.setex(full_key, resolved_ttl, encoded)
            else:
                self._client.set(full_key, encoded)
    else:
        # 原有 pipeline 逻辑
        ...
```

#### delete_pattern / iter_keys — Cluster 下扫描所有节点

redis-py 的 `RedisCluster.scan_iter()` 已内置遍历所有节点，无需额外处理。现有代码兼容。

## 5. Lock 模块 — Hash Tag

Cluster 模式下，Lua 脚本操作的所有 key 必须在同一个 slot。通过 `{hash_tag}` 前缀实现：

```python
class Lock:
    def __init__(self, client, prefix="", is_cluster: bool = False):
        self._is_cluster = is_cluster
        ...

    def _make_key(self, name: str) -> str:
        base = f"{self._prefix}:{name}" if self._prefix else name
        if self._is_cluster:
            return f"{{{base}}}"   # Redis 只对 {} 内的部分计算 slot
        return base
```

这样可重入锁的 hash key `{myapp:lock:resource}` 和读写锁的 `{myapp:lock:resource}:rwlock` 都会基于 `myapp:lock:resource` 计算 slot，保证在同一个节点上。

## 6. 异常

新增：

```python
class TopologyConstraintError(RedisKitError):
    """Operation not supported under current topology (e.g., cross-slot in Cluster)."""
```

用于在 Cluster 模式下遇到不可降级的操作时抛出明确异常。

## 7. 公共 API 导出

新增导出到 `redis_kit/__init__.py`：

```python
from redis_kit.config import SentinelConfig, ClusterConfig
from redis_kit.exceptions import TopologyConstraintError

# __all__ 中新增
"SentinelConfig",
"ClusterConfig",
"TopologyConstraintError",
```

## 8. 影响面

### 需要修改的文件

| 文件 | 改动 |
|------|------|
| `config.py` | 新增 `SentinelConfig`, `ClusterConfig` |
| `connection.py` | 新增 `_build_sentinel_*`, `_build_cluster_*`, `is_cluster`, `is_sentinel`, `topology` |
| `exceptions.py` | 新增 `TopologyConstraintError` |
| `cache/_cluster.py` | 新增 `group_keys_by_slot()` |
| `cache/cache.py` | `get_many`/`set_many` Cluster 适配，构造函数新增 `is_cluster` |
| `cache/async_cache.py` | 同上 async 版本 |
| `lock/lock.py` | `_make_key` Cluster hash tag，构造函数新增 `is_cluster` |
| `lock/async_lock.py` | 同上 |
| `__init__.py` | 导出新类型 |

### 不需要修改的文件

counter、bloom、session、queue、serializers、compressors、hooks、observability、decorator — 全是单 key 操作或不涉及连接管理。

## 9. 测试策略

- Config 测试：`SentinelConfig` / `ClusterConfig` 冻结性、默认值
- ConnectionManager 测试：按 config 类型正确分发（用 mock/fakeredis）
- Cache Cluster 适配测试：`_cluster_mget` 分组正确性、`set_many` 降级
- Lock hash tag 测试：Cluster 模式下 key 格式正确
- 集成测试：标注为需要真实 Redis Sentinel/Cluster 环境，CI 可选跳过

## 10. 用户使用示例

```python
from redis_kit import ConnectionManager, Cache, Lock
from redis_kit import ConnectionConfig, SentinelConfig, ClusterConfig

# Standalone（不变）
conn = ConnectionManager(config=ConnectionConfig(host="localhost"))

# Sentinel — 自动故障转移，上层无感
conn = ConnectionManager(config=SentinelConfig(
    sentinels=[("sentinel1", 26379), ("sentinel2", 26379), ("sentinel3", 26379)],
    service_name="mymaster",
    password="secret",
))

# Cluster — 数据分片，多 key 操作自动降级
conn = ConnectionManager(config=ClusterConfig(
    startup_nodes=[("node1", 6379), ("node2", 6379), ("node3", 6379)],
    password="secret",
    read_from_replicas=True,
))

# 下游模块用法完全不变
cache = Cache(conn.sync_client, prefix="myapp:cache", is_cluster=conn.is_cluster)
lock = Lock(conn.sync_client, prefix="myapp:lock", is_cluster=conn.is_cluster)
```
