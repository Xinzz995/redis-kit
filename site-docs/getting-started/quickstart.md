# 快速开始

## 连接

```python
from redis_kit import ConnectionManager

# 通过 URL 连接
conn = ConnectionManager(url="redis://localhost:6379/0")

# 通过配置对象连接
from redis_kit import ConnectionConfig
conn = ConnectionManager(config=ConnectionConfig(host="localhost", port=6379, db=0))
```

## 缓存

```python
from redis_kit import Cache

cache = Cache(conn.sync_client, prefix="myapp:cache")

cache.set("user:1", {"name": "Alice"}, ttl="2h30m")
user = cache.get("user:1")

# Cache-aside 模式
user = cache.remember("user:1", factory=load_from_db, ttl=3600)
```

## 分布式锁

```python
from redis_kit import Lock

lock = Lock(conn.sync_client, prefix="myapp:lock")

with lock("resource-1", timeout=10):
    do_critical_work()
```

## 异步用法

每个模块都有对应的异步版本：

```python
from redis_kit import AsyncCache, AsyncLock

cache = AsyncCache(conn.async_client, prefix="myapp:cache")
await cache.set("key", "value", ttl=3600)
```
