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

支持字符串格式的 TTL：`"2h30m"`、`"1d"`、`"30s"`。负值会抛出 `ValueError`。
TTL 字符串必须整体合法，像 `"1hfoo"` 这类带尾随垃圾内容的值也会抛出 `ValueError`。

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
@cached(conn.async_client, key="product:{pid}", ttl=3600)
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

## 降级策略（FallbackPolicy）

当 Redis 连接失败时，可配置降级策略而非直接抛异常。

```python
from redis_kit import Cache, FallbackPolicy

# 策略 1: 静默降级，返回 None
policy = FallbackPolicy(on_connection_error="return_none")
cache = Cache(conn.sync_client, prefix="myapp", fallback_policy=policy)

# 策略 2: 自定义回调
def my_fallback(command, key, error):
    return {"from": "local_cache"}

policy = FallbackPolicy(on_connection_error="callback", fallback=my_fallback)
cache = Cache(conn.sync_client, prefix="myapp", fallback_policy=policy)
```

详细说明参见 [异常处理 - 降级策略](../configuration/exceptions.md)。

## Hooks（可观测性）

Cache 的所有操作（get、set、delete、get_many、set_many、delete_pattern）都支持 Hook 生命周期：`before` → `after`（成功时）/ `error`（失败时）。单个 Hook 异常不会中断缓存操作，仅记录错误日志。

```python
from redis_kit import Cache
from redis_kit.observability import OpenTelemetryHook, MetricsCollector

cache = Cache(
    conn.sync_client,
    prefix="myapp",
    hooks=[OpenTelemetryHook(), MetricsCollector()],
)
```

## TTL 抖动（防雪崩）

```python
cache = Cache(conn.sync_client, prefix="myapp", ttl_jitter=0.1)  # +/- 10% random TTL
```
