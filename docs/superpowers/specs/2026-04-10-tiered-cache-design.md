# redis-py-kit 多级缓存模块设计

## 1. 概述

为 redis-py-kit 添加多级缓存 `TieredCache`，在现有 Redis `Cache` 前加一层内置 LRU 本地缓存。读取路径：L1(本地) → L2(Redis)，写入路径：写 L2 + 写 L1。本地缓存通过 TTL 自然过期保持最终一致性。

### 设计参考

| 来源 | 借鉴内容 |
|------|---------|
| cashews | `_empty` 哨兵缓存"已知不存在"，避免重复穿透 L2 |
| cacheme | 读回填（L2 命中后写入 L1）|
| node-cache-manager | Write-through 所有层；get_many 批量查 L1 再补查 L2 |
| aiocache | OrderedDict LRU 本地缓存实现参考 |

## 2. 文件结构

```
redis_kit/cache/
├── local.py             # CREATE: LRUCache — 线程安全 LRU + TTL
├── tiered.py            # CREATE: TieredCache (sync)
├── async_tiered.py      # CREATE: AsyncTieredCache
```

## 3. LRUCache — 内置本地缓存

基于 `OrderedDict` 实现，线程安全，支持 TTL 和 maxsize 淘汰。零外部依赖。

```python
import threading
import time
from collections import OrderedDict

_MISS = object()  # 复用 cache/_logic.py 的哨兵

class LRUCache:
    """Thread-safe LRU cache with per-entry TTL."""

    def __init__(self, maxsize: int = 1000, ttl: float = 30.0) -> None:
        self._maxsize = maxsize
        self._default_ttl = ttl
        self._data: OrderedDict[str, tuple[Any, float]] = OrderedDict()  # key -> (value, expire_at)
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        """获取值。过期或不存在返回 _MISS 哨兵。"""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return _MISS
            value, expire_at = entry
            if time.monotonic() > expire_at:
                del self._data[key]
                return _MISS
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """写入值。超过 maxsize 时淘汰最旧条目。"""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expire_at = time.monotonic() + effective_ttl
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = (value, expire_at)
            while len(self._data) > self._maxsize:
                self._data.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    @property
    def size(self) -> int:
        return len(self._data)
```

### 设计决策

- **线程安全**：`threading.Lock` 保护所有读写。LRU 操作是 O(1)，锁持有时间极短。
- **惰性过期**：不用后台线程扫描，在 `get` 时检查过期。简单可靠。
- **`_MISS` 哨兵**：区分"缓存未命中"和"缓存了 None 值"，复用现有 `cache/_logic.py` 的模式。

## 4. 负缓存（Negative Cache）

借鉴 cashews 的 `_empty_in_redis` 模式。当 L2 也查不到数据时，在 L1 缓存一个特殊标记，避免短时间内反复穿透到 Redis。

```python
_NEGATIVE = object()  # 负缓存标记

class TieredCache:
    def __init__(self, ..., negative_ttl: float = 5.0):
        self._negative_ttl = negative_ttl  # 负缓存 TTL，默认 5 秒

    def get(self, key: str) -> Any:
        # 1. 查 L1
        local_val = self._l1.get(key)
        if local_val is _NEGATIVE:
            return None  # 已知不存在，跳过 L2
        if local_val is not _MISS:
            return local_val  # L1 命中

        # 2. 查 L2
        value = self._l2.get(key)
        if value is not None:
            self._l1.set(key, value)  # 读回填
            return value

        # 3. 都没有 → 写负缓存
        self._l1.set(key, _NEGATIVE, ttl=self._negative_ttl)
        return None
```

## 5. TieredCache — L1 + L2 包装

```python
class TieredCache:
    """Two-tier cache: L1 (local LRU) → L2 (Redis Cache)."""

    def __init__(
        self,
        cache: Cache,
        local_maxsize: int = 1000,
        local_ttl: float = 30.0,
        negative_ttl: float = 5.0,
    ) -> None:
        self._l1 = LRUCache(maxsize=local_maxsize, ttl=local_ttl)
        self._l2 = cache
        self._negative_ttl = negative_ttl
```

### 读取方法

| 方法 | 行为 |
|------|------|
| `get(key)` | L1 → L2 → 负缓存 → None |
| `get_many(keys)` | 批量查 L1，miss 的 key 查 L2，回填 L1，合并返回 |
| `remember(key, factory, ttl)` | L1 → L2 → factory → 写 L2 + L1 |

### 写入方法

| 方法 | 行为 |
|------|------|
| `set(key, value, ttl)` | 写 L2 + 写 L1（write-through） |
| `set_many(mapping, ttl)` | 逐个 write-through |
| `delete(key)` | 删 L1 + 删 L2 |
| `delete_pattern(pattern)` | 委托 L2 + 清空 L1（无法精确匹配本地 key） |

### 委托方法（直接转发到 L2）

`ttl(key)`, `pttl(key)`, `persist(key)`, `expire(key, seconds)`, `expire_at(key, when)`, `iter_keys(pattern)`

### 本地缓存管理

```python
def invalidate_local(self, key: str) -> None:
    """手动清除某个 key 的本地缓存。"""
    self._l1.delete(key)

def clear_local(self) -> None:
    """清空所有本地缓存。"""
    self._l1.clear()

@property
def local_size(self) -> int:
    """当前本地缓存条目数。"""
    return self._l1.size
```

## 6. AsyncTieredCache

与 `TieredCache` 完全对称的异步版本。`LRUCache` 本身是同步的（内存操作极快），在异步版本中也直接同步调用，不需要 `await`。

```python
class AsyncTieredCache:
    def __init__(
        self,
        cache: AsyncCache,
        local_maxsize: int = 1000,
        local_ttl: float = 30.0,
        negative_ttl: float = 5.0,
    ) -> None:
        self._l1 = LRUCache(maxsize=local_maxsize, ttl=local_ttl)
        self._l2 = cache
        self._negative_ttl = negative_ttl

    async def get(self, key: str) -> Any:
        local_val = self._l1.get(key)
        if local_val is _NEGATIVE:
            return None
        if local_val is not _MISS:
            return local_val
        value = await self._l2.get(key)
        if value is not None:
            self._l1.set(key, value)
            return value
        self._l1.set(key, _NEGATIVE, ttl=self._negative_ttl)
        return None
```

## 7. 公共 API 导出

```python
from redis_kit import TieredCache, AsyncTieredCache
from redis_kit.cache import LRUCache  # 高级用户可单独使用
```

## 8. 用户使用示例

```python
from redis_kit import ConnectionManager, Cache
from redis_kit.cache import TieredCache

conn = ConnectionManager(url="redis://localhost:6379/0")
redis_cache = Cache(conn.sync_client, prefix="myapp:cache", ttl_jitter=0.1)

# 包装成多级缓存
cache = TieredCache(
    redis_cache,
    local_maxsize=2000,
    local_ttl=30.0,
    negative_ttl=5.0,
)

# 使用方式与 Cache 完全一致
cache.set("user:1", {"name": "Alice"}, ttl=3600)
user = cache.get("user:1")     # 第一次：L1 miss → L2 hit → 回填 L1
user = cache.get("user:1")     # 第二次：L1 hit，不访问 Redis

# 批量操作
data = cache.get_many(["user:1", "user:2", "user:3"])

# 缓存穿透保护
result = cache.get("nonexistent")  # L1 miss → L2 miss → 写负缓存
result = cache.get("nonexistent")  # L1 hit (negative) → 直接返回 None

# 手动管理
cache.invalidate_local("user:1")
cache.clear_local()
print(f"Local cache size: {cache.local_size}")
```

## 9. 测试策略

- LRUCache 单元测试：LRU 淘汰、TTL 过期、线程安全、maxsize 限制
- TieredCache 测试：L1→L2 回填、write-through、负缓存、delete、get_many 优化
- AsyncTieredCache 测试：异步版本对称性验证

## 10. 影响面

| 文件 | 改动 |
|------|------|
| `redis_kit/cache/local.py` | 新建 LRUCache |
| `redis_kit/cache/tiered.py` | 新建 TieredCache |
| `redis_kit/cache/async_tiered.py` | 新建 AsyncTieredCache |
| `redis_kit/cache/__init__.py` | 导出新类 |
| `redis_kit/__init__.py` | 导出 TieredCache, AsyncTieredCache |
| 其他模块 | 零改动 |
