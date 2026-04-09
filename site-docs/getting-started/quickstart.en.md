# Quick Start

## Connection

```python
from redis_kit import ConnectionManager

# Connect via URL
conn = ConnectionManager(url="redis://localhost:6379/0")

# Connect via config object
from redis_kit import ConnectionConfig
conn = ConnectionManager(config=ConnectionConfig(host="localhost", port=6379, db=0))
```

## Cache

```python
from redis_kit import Cache

cache = Cache(conn.sync_client, prefix="myapp:cache")

cache.set("user:1", {"name": "Alice"}, ttl="2h30m")
user = cache.get("user:1")

# Cache-aside pattern
user = cache.remember("user:1", factory=load_from_db, ttl=3600)
```

## Distributed Lock

```python
from redis_kit import Lock

lock = Lock(conn.sync_client, prefix="myapp:lock")

with lock("resource-1", timeout=10):
    do_critical_work()
```

## Async Usage

Every module has a corresponding async version:

```python
from redis_kit import AsyncCache, AsyncLock

cache = AsyncCache(conn.async_client, prefix="myapp:cache")
await cache.set("key", "value", ttl=3600)
```
