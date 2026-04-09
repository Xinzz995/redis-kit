# 多级缓存

两级缓存架构：L1（本地 LRU）+ L2（Redis），无需额外外部依赖。

## 用法

```python
from redis_kit import Cache, ConnectionManager
from redis_kit.cache import TieredCache

conn = ConnectionManager(url="redis://localhost:6379/0")
redis_cache = Cache(conn.sync_client, prefix="myapp:cache")

cache = TieredCache(
    redis_cache,
    local_maxsize=2000,   # L1 max entries
    local_ttl=30.0,       # L1 TTL (seconds)
    negative_ttl=5.0,     # Cache misses for 5s
)
```

## 读取路径

1. 检查 L1（本地缓存）—— 即时响应，无网络开销
2. 若未命中，检查 L2（Redis）
3. 若 L2 命中，**自动回填 L1**
4. 若两级均未命中，将**空值缓存（Negative Cache）**写入 L1（防止重复穿透 L2）

## 写入路径

**写穿透（Write-through）**：`set()` 同时写入 L1 和 L2。

```python
cache.set("user:1", data, ttl=3600)   # L1 + L2
user = cache.get("user:1")             # L1 hit
```

## 批量操作

`get_many` 先查询 L1，仅将未命中的 key 发往 L2：

```python
data = cache.get_many(["user:1", "user:2", "user:3"])
```

## 本地缓存管理

```python
cache.invalidate_local("user:1")   # Clear one key from L1
cache.clear_local()                 # Clear all L1
print(cache.local_size)             # Current L1 entry count
```

## 异步用法

```python
from redis_kit.cache import AsyncTieredCache

cache = AsyncTieredCache(async_redis_cache, local_maxsize=2000, local_ttl=30.0)
value = await cache.get("key")
```
