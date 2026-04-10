# Tiered Cache

Two-level cache architecture: L1 (local LRU) + L2 (Redis), with no additional external dependencies.

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

1. Check L1 (local cache) -- instant response, no network overhead
2. If miss, check L2 (Redis)
3. If L2 hit, **auto-backfill L1**
4. If both levels miss, write a **negative cache** entry to L1 (prevents repeated L2 penetration)

## Write Path

**Write-through**: `set()` writes to both L1 and L2.

```python
cache.set("user:1", data, ttl=3600)   # L1 + L2
user = cache.get("user:1")             # L1 hit
```

## Batch Operations

`get_many` queries L1 first, only sending missed keys to L2:

```python
data = cache.get_many(["user:1", "user:2", "user:3"])
```

## Local Cache Management

```python
cache.invalidate_local("user:1")   # Clear one key from L1
cache.clear_local()                 # Clear all L1
print(cache.local_size)             # Current L1 entry count
```

## Bound Operations

```python
user = cache.bind("user:1")
user.set(data, ttl=3600)
user.get()
user.delete()
```

## Async Usage

```python
from redis_kit.cache import AsyncTieredCache

cache = AsyncTieredCache(async_redis_cache, local_maxsize=2000, local_ttl=30.0)
value = await cache.get("key")

# Bound operations
user = cache.bind("user:1")
await user.set(data, ttl=3600)
await user.get()
```
