# Cache

Redis cache with serialization, compression, TTL jitter, and fallback policy support.

## Basic Usage

```python
from redis_kit import Cache, ConnectionManager

conn = ConnectionManager(url="redis://localhost:6379/0")
cache = Cache(conn.sync_client, prefix="myapp:cache")

cache.set("user:1", {"name": "Alice"}, ttl="2h30m")
user = cache.get("user:1")
cache.delete("user:1")
```

## TTL Management

```python
cache.set("key", "value", ttl=3600)
cache.ttl("key")          # Remaining seconds
cache.pttl("key")         # Remaining milliseconds
cache.persist("key")      # Remove expiration
cache.expire("key", 600)  # Reset TTL
```

Supports string-format TTL: `"2h30m"`, `"1d"`, `"30s"`. Negative values raise `ValueError`.

## Cache-Aside Pattern

```python
user = cache.remember("user:1", factory=load_from_db, ttl=3600)
```

## Batch Operations

```python
cache.set_many({"a": 1, "b": 2, "c": 3}, ttl=3600)
values = cache.get_many(["a", "b", "c"])
```

## Pattern-Based Operations (SCAN-based)

```python
cache.delete_pattern("user:*")
for key in cache.iter_keys("user:*"):
    print(key)
```

## Bound Operations

```python
user_cache = cache.bind("user:1")
user_cache.set({"name": "Alice"}, ttl=3600)
user_cache.get()
user_cache.ttl()
```

## @cached Decorator

```python
from redis_kit import cached

@cached(conn.sync_client, key="user:{user_id}", ttl="1h")
def get_user(user_id: int) -> dict:
    return db.query_user(user_id)

# Async (auto-detected)
@cached(conn.async_client, key="product:{pid}", ttl=3600)
async def get_product(pid: int) -> dict:
    return await db.query_product(pid)
```

### Callable Key/TTL/Bypass

```python
@cached(
    conn.sync_client,
    key=lambda uid: f"user:{uid}",
    ttl=lambda uid: 3600 if uid < 100 else 300,
    bypass=lambda uid, force=False: force,
)
def get_user(uid: int, force: bool = False) -> dict:
    ...
```

### Cache Invalidation

```python
@cached(conn.sync_client, key="user:{user_id}", ttl="1h")
def get_user(user_id: int) -> dict:
    return db.query_user(user_id)

# Invalidate cache for specific arguments
get_user.invalidate(user_id=1)

# Async version
@cached(conn.async_client, key="product:{pid}", ttl=3600)
async def get_product(pid: int) -> dict:
    return await db.query_product(pid)

await get_product.invalidate(pid=42)
```

## Cache Penetration Protection (None Caching)

```python
cache.set("user:999", None, ttl=60)  # Cache None to prevent penetration
```

## Fallback Policy

Configure degradation strategies for Redis connection failures instead of raising exceptions.

```python
from redis_kit import Cache, FallbackPolicy

# Strategy 1: Silent degradation, return None
policy = FallbackPolicy(on_connection_error="return_none")
cache = Cache(conn.sync_client, prefix="myapp", fallback_policy=policy)

# Strategy 2: Custom callback
def my_fallback(command, key, error):
    return {"from": "local_cache"}

policy = FallbackPolicy(on_connection_error="callback", fallback=my_fallback)
cache = Cache(conn.sync_client, prefix="myapp", fallback_policy=policy)
```

See [Exception Handling - Fallback Policy](../configuration/exceptions.md#fallback-policy) for details.

## Hooks (Observability)

All Cache operations (get, set, delete, get_many, set_many, delete_pattern) support the full hook lifecycle: `before` → `after` (on success) / `error` (on failure). A failing hook will not break the cache operation — errors are logged instead.

```python
from redis_kit import Cache
from redis_kit.observability import OpenTelemetryHook, MetricsCollector

cache = Cache(
    conn.sync_client,
    prefix="myapp",
    hooks=[OpenTelemetryHook(), MetricsCollector()],
)
```

## TTL Jitter (Stampede Prevention)

```python
cache = Cache(conn.sync_client, prefix="myapp", ttl_jitter=0.1)  # +/- 10% random TTL
```
