# Tiered Cache

Two-tier cache: L1 (local LRU) + L2 (Redis). Zero external dependencies.

## Usage

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

## Read Path

1. Check L1 (local) -- instant, no network
2. If miss, check L2 (Redis)
3. If L2 hit, **backfill L1** automatically
4. If both miss, write **negative cache** to L1 (prevents repeated L2 misses)

## Write Path

**Write-through**: `set()` writes both L1 and L2 simultaneously.

```python
cache.set("user:1", data, ttl=3600)   # L1 + L2
user = cache.get("user:1")             # L1 hit
```

## Batch Operations

`get_many` queries L1 first, only missed keys go to L2:

```python
data = cache.get_many(["user:1", "user:2", "user:3"])
```

## Local Cache Management

```python
cache.invalidate_local("user:1")   # Clear one key from L1
cache.clear_local()                 # Clear all L1
print(cache.local_size)             # Current L1 entry count
```

## Async

```python
from redis_kit.cache import AsyncTieredCache

cache = AsyncTieredCache(async_redis_cache, local_maxsize=2000, local_ttl=30.0)
value = await cache.get("key")
```
