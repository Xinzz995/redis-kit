# 缓存

Redis 缓存，支持序列化、压缩、TTL 抖动和降级策略（FallbackPolicy）。

## 基本用法

```python
from redis_kit import Cache, ConnectionManager

conn = ConnectionManager(url="redis://localhost:6379/0")
cache = Cache(conn.sync_client, prefix="myapp:cache")

cache.set("user:1", {"name": "Alice"}, ttl="2h30m")
user = cache.get("user:1")
cache.delete("user:1")
```

## TTL 管理

```python
cache.set("key", "value", ttl=3600)
cache.ttl("key")          # Remaining seconds
cache.pttl("key")         # Remaining milliseconds
cache.persist("key")      # Remove expiration
cache.expire("key", 600)  # Reset TTL
```

支持字符串格式的 TTL：`"2h30m"`、`"1d"`、`"30s"`。

## Cache-Aside 模式

```python
user = cache.remember("user:1", factory=load_from_db, ttl=3600)
```

## 批量操作

```python
cache.set_many({"a": 1, "b": 2, "c": 3}, ttl=3600)
values = cache.get_many(["a", "b", "c"])
```

## 模式匹配操作（基于 SCAN）

```python
cache.delete_pattern("user:*")
for key in cache.iter_keys("user:*"):
    print(key)
```

## 绑定操作（Bound Operations）

```python
user_cache = cache.bind("user:1")
user_cache.set({"name": "Alice"}, ttl=3600)
user_cache.get()
user_cache.ttl()
```

## @cached 装饰器

```python
from redis_kit import cached

@cached(conn.sync_client, key="user:{user_id}", ttl="1h")
def get_user(user_id: int) -> dict:
    return db.query_user(user_id)

# Async (auto-detected)
@cached(conn.sync_client, key="product:{pid}", ttl=3600)
async def get_product(pid: int) -> dict:
    return await db.query_product(pid)
```

### 可调用的 Key/TTL/Bypass

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

### 缓存失效

```python
@cached(conn.sync_client, key="user:{user_id}", ttl="1h")
def get_user(user_id: int) -> dict:
    return db.query_user(user_id)

# 清除特定参数的缓存
get_user.invalidate(user_id=1)

# 异步版本
@cached(conn.async_client, key="product:{pid}", ttl=3600)
async def get_product(pid: int) -> dict:
    return await db.query_product(pid)

await get_product.invalidate(pid=42)
```

## 防穿透（None 缓存）

```python
cache.set("user:999", None, ttl=60)  # Cache None to prevent penetration
```

## TTL 抖动（防雪崩）

```python
cache = Cache(conn.sync_client, prefix="myapp", ttl_jitter=0.1)  # +/- 10% random TTL
```
