# redis-kit 设计规格文档

## 1. 概述

redis-kit 是一个综合性的企业级 Python Redis 工具库。提供缓存、分布式锁、消息队列、布隆过滤器、计数器/ID 生成器和 Session 管理，同时支持同步和异步 API。

- **定位**：内部使用 + 开源 PyPI 包
- **Python**：>= 3.11
- **Redis 驱动**：redis-py >= 7.4.0
- **v1 范围**：仅支持 Standalone 模式（Sentinel/Cluster 延迟到 v2）

## 2. 架构

独立模块 + 依赖注入共享连接（方案 B）。

```
redis_kit/
├── __init__.py                # 公共 API 导出
├── connection.py              # ConnectionManager（同步/异步视图）
├── config.py                  # 冻结数据类配置
├── serializers/
│   ├── __init__.py
│   ├── base.py                # Serializer 协议
│   ├── json.py                # JsonSerializer
│   ├── msgpack.py             # MsgpackSerializer
│   └── pickle.py              # PickleSerializer
├── compressors/
│   ├── __init__.py
│   ├── base.py                # Compressor 协议
│   ├── zstd.py                # ZstdCompressor
│   ├── lz4.py                 # Lz4Compressor
│   └── zlib.py                # ZlibCompressor
├── cache/
│   ├── __init__.py
│   ├── _logic.py              # 共享非 IO 逻辑（key 构建、校验）
│   ├── cache.py               # Cache（同步）
│   ├── async_cache.py         # AsyncCache
│   └── decorator.py           # @cached 装饰器（同步 + 异步）
├── lock/
│   ├── __init__.py
│   ├── lock.py                # Lock（同步）
│   └── async_lock.py          # AsyncLock
├── queue/
│   ├── __init__.py
│   ├── queue.py               # Queue / DelayQueue / ReliableQueue（同步）
│   └── async_queue.py         # 异步版本
├── bloom/
│   ├── __init__.py
│   ├── bloom.py               # BloomFilter（同步）
│   └── async_bloom.py         # AsyncBloomFilter
├── counter/
│   ├── __init__.py
│   ├── counter.py             # Counter + IDGenerator（同步）
│   └── async_counter.py       # 异步版本
├── session/
│   ├── __init__.py
│   ├── session.py             # SessionManager（同步）
│   └── async_session.py       # AsyncSessionManager
├── hooks.py                   # CommandHook 协议 + CompositeHook
├── observability/
│   ├── __init__.py
│   ├── otel.py                # OpenTelemetry 集成
│   └── metrics.py             # 指标收集
└── exceptions.py              # 异常体系 + FallbackPolicy
```

### 设计原则

- 每个模块职责单一，通过 ConnectionManager 接口通信
- 模块独立导入：`from redis_kit.cache import Cache`
- 无全局状态、无单例 — 所有状态通过构造函数注入
- 非 IO 逻辑（key 构建、序列化、校验）通过 `_logic.py` 共享，减少同步/异步代码重复
- IO 逻辑分别为同步和异步编写，每个类保持小体量（目标 < 150 行）

## 3. 连接管理

### ConnectionManager

中心化的连接生命周期管理器。提供同步/异步视图，灵感来自 Lettuce。

```python
from redis_kit import ConnectionManager

# 通过 URL 创建
conn = ConnectionManager(url="redis://localhost:6379/0")

# 或通过配置对象创建
conn = ConnectionManager(config=ConnectionConfig(
    host="localhost",
    port=6379,
    db=0,
    max_connections=20,
    socket_timeout=5.0,
    decode_responses=False,
))

# 同步/异步视图（API 糖，底层连接池是分开的）
conn.sync_client    # -> redis.Redis
conn.async_client   # -> redis.asyncio.Redis

# 生命周期
conn.close()         # 关闭同步资源
await conn.aclose()  # 关闭异步资源
```

### 关键设计决策

- **Event Loop 隔离**：异步客户端按 event loop 缓存（WeakKeyDictionary），防止跨 loop 复用。借鉴自老代码库 — 这是正确性保证，不是可选项。
- **延迟初始化**：连接池在首次访问时创建，而非构造时创建。
- **线程安全**：sync_client 通过连接池保证线程安全。文档中明确标注。
- **v2 扩展点**：构造函数将接受 `topology` 参数（standalone/sentinel/cluster），无需更改接口。

### 配置

冻结数据类，按职责拆分：

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ConnectionConfig:
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

@dataclass(frozen=True)
class NamespaceConfig:
    prefix: str = ""
    separator: str = ":"
```

## 4. 序列化

### Serializer 协议

```python
from typing import Protocol, Any

class Serializer(Protocol):
    def dumps(self, value: Any) -> bytes: ...
    def loads(self, data: bytes) -> Any: ...
```

统一 bytes 输入输出。ConnectionManager 层负责 encode/decode。

### 内置序列化器

| 序列化器 | 格式 | 适用场景 |
|---------|------|---------|
| JsonSerializer | JSON | 默认，可读性好，跨语言互通 |
| MsgpackSerializer | MessagePack | 紧凑二进制，速度快 |
| PickleSerializer | Pickle | Python 原生对象，仅限可信环境 |

### 压缩器协议（独立层）

灵感来自 django-redis：序列化器和压缩器分离，可自由组合。

```python
class Compressor(Protocol):
    def compress(self, data: bytes) -> bytes: ...
    def decompress(self, data: bytes) -> bytes: ...
```

内置：ZstdCompressor、Lz4Compressor、ZlibCompressor。全部可选。

数据管道：`value -> serializer.dumps() -> compressor.compress() -> Redis`

```python
cache = Cache(
    conn,
    serializer=JsonSerializer(),
    compressor=ZstdCompressor(),  # 可选，None = 不压缩
)
```

## 5. 缓存模块

### 核心 API

```python
from redis_kit.cache import Cache, AsyncCache

cache = Cache(conn, prefix="myapp:cache", serializer=JsonSerializer())

# 基本操作
cache.set("user:1", {"name": "Alice"}, ttl=3600)
value = cache.get("user:1")
cache.delete("user:1")

# TTL 管理（灵感来自 django-redis）
cache.ttl("user:1")                    # 剩余秒数
cache.pttl("user:1")                   # 剩余毫秒数
cache.persist("user:1")                # 移除过期时间
cache.expire("user:1", 600)            # 重设 TTL
cache.expire_at("user:1", datetime)    # 指定过期时间点

# Cache-aside 模式
value = cache.remember("user:1", factory=load_user, ttl=3600)

# 批量操作
values = cache.get_many(["user:1", "user:2", "user:3"])
cache.set_many({"user:1": data1, "user:2": data2}, ttl=3600)

# 模式操作（基于 SCAN，永远不用 KEYS）
cache.delete_pattern("user:*")
for key in cache.iter_keys("user:*"):
    ...

# 缓存空值（防穿透）
cache.set("user:999", None, ttl=60)  # 缓存空值防止穿透
```

### 绑定操作（灵感来自 Spring Data）

```python
user_cache = cache.bind("user:1")
user_cache.set({"name": "Alice"}, ttl=3600)
user_cache.get()
user_cache.ttl()
user_cache.expire(600)
```

### @cached 装饰器

```python
from redis_kit.cache import cached

@cached(
    conn,
    key="user:{user_id}",                              # 字符串模板
    # key=lambda user_id: f"user:{user_id}",           # 或 callable
    ttl="2h30m",                                        # 字符串 / 整数 / callable
    # ttl=lambda user_id: 3600 if user_id < 100 else 300,
    lock=True,                                          # 防击穿：缓存未命中时加分布式锁
    bypass=lambda user_id, force=False: force,          # 条件性跳过缓存
    serializer=JsonSerializer(),
)
def get_user(user_id: int, force: bool = False) -> dict:
    return db.query_user(user_id)

# 异步版本：同一个装饰器，自动检测异步函数
@cached(conn, key="product:{pid}", ttl=3600)
async def get_product(pid: int) -> dict:
    return await db.query_product(pid)
```

### 缓存防护策略

| 策略 | 问题 | 解决方案 |
|------|------|---------|
| 穿透防护 | 查询不存在的数据始终打到数据库 | 缓存空值（短 TTL）+ 布隆过滤器预检 |
| 击穿防护 | 热点 key 过期，并发请求涌入数据库 | 缓存未命中时加分布式锁（singleflight） |
| 雪崩防护 | 大量 key 同时过期 | TTL 随机化（jitter）+ 错开过期时间 |

TTL jitter 内置且默认开启：

```python
cache = Cache(conn, ttl_jitter=0.1)  # +/- 10% 随机 TTL 偏差
```

### 缓存钩子（灵感来自老代码库）

```python
class CacheHook(Protocol):
    def on_hit(self, key: str, latency_ms: float) -> None: ...
    def on_miss(self, key: str) -> None: ...
    def on_set(self, key: str, ttl: int | None) -> None: ...
    def on_delete(self, key: str) -> None: ...
    def on_error(self, key: str, error: Exception) -> None: ...
```

## 6. 分布式锁模块

### 核心 API

对齐 `threading.Lock` 接口（灵感来自 Pottery）。

```python
from redis_kit.lock import Lock, AsyncLock

lock = Lock(conn, prefix="myapp:lock")

# 基本用法 — 上下文管理器
with lock("resource-1", timeout=10, blocking_timeout=5):
    do_critical_work()

# 异步
async with AsyncLock(conn)("resource-1", timeout=10):
    await do_async_work()
```

### 功能特性

**可重入锁**：
```python
with lock("resource", reentrant=True):
    with lock("resource", reentrant=True):  # 同一线程/协程，不会死锁
        ...
```

**读写锁**：
```python
with lock.read("resource"):    # 允许多个读者
    data = read_shared_state()

with lock.write("resource"):   # 排他写入
    update_shared_state()
```

**自动续期（看门狗）**：

在临界区执行期间自动延长锁的 TTL。防止长时间操作导致锁过期。使用后台线程/任务，每 `timeout / 3` 间隔续期一次。

```python
with lock("resource", timeout=30, auto_renew=True):
    do_long_running_work()  # 锁每 10 秒自动续期
```

### 实现方案

- 基础锁：Redis `SET NX EX` + Lua 脚本原子释放
- 可重入：通过 Redis hash 跟踪线程/任务 ID（持有者 + 计数）
- 读写锁：Redis hash 记录读者数量 + 排他写者标志，Lua 脚本保证原子性
- 看门狗：`threading.Timer`（同步）/ `asyncio.Task`（异步）定期续期

## 7. 队列模块

### 发布订阅（PubSub）

```python
from redis_kit.queue import PubSub, AsyncPubSub

pubsub = PubSub(conn, prefix="myapp:pubsub")

# 发布
pubsub.publish("events", {"type": "user_created", "id": 1})

# 订阅
def handler(message):
    print(message)

pubsub.subscribe("events", handler)
pubsub.listen()  # 阻塞监听

# 模式订阅
pubsub.psubscribe("events:*", handler)
```

PubSub 自动管理专用连接（灵感来自 Lettuce），与命令连接分离。

### 延迟队列

```python
from redis_kit.queue import DelayQueue, AsyncDelayQueue

dq = DelayQueue(conn, "order:timeout")

# 带延迟入队
dq.put({"order_id": 123}, delay=1800)  # 30 分钟后执行

# 轮询就绪消息
messages = dq.poll(count=10)
```

实现方案：Redis Sorted Set，score = 执行时间戳。

### 可靠队列

```python
from redis_kit.queue import ReliableQueue

rq = ReliableQueue(conn, "tasks")

# 生产者
rq.put({"task": "send_email", "to": "user@example.com"})

# 消费者 + 确认机制
message = rq.get(timeout=5)
try:
    process(message.data)
    message.ack()
except Exception:
    message.nack()  # 退回队列
```

实现方案：Redis List + 处理中列表（RPOPLPUSH 模式）。未确认的消息在可配置超时后自动退回队列。

## 8. 布隆过滤器模块

```python
from redis_kit.bloom import BloomFilter, AsyncBloomFilter

bf = BloomFilter(conn, "user:emails", expected_items=100_000, false_positive_rate=0.01)

bf.add("alice@example.com")
bf.exists("alice@example.com")   # True
bf.exists("unknown@example.com") # False（大概率）

# 批量操作
bf.add_many(["a@x.com", "b@x.com", "c@x.com"])
results = bf.exists_many(["a@x.com", "d@x.com"])  # [True, False]
```

实现方案：多个哈希函数 + Redis 位操作（SETBIT/GETBIT）。Lua 脚本保证多位操作的原子性。

如果 Redis Stack（RedisBloom 模块）可用，自动检测并委托给 `BF.ADD` / `BF.EXISTS` 以获得更好的性能。

## 9. 计数器与 ID 生成器模块

### 计数器

API 对齐 `collections.Counter` 直觉（灵感来自 Pottery）。

```python
from redis_kit.counter import Counter, AsyncCounter

counter = Counter(conn, prefix="myapp:counter")

# 基本操作
counter.incr("page_views")
counter.incr("page_views", 5)
counter.decr("page_views")
value = counter.get("page_views")

# 绑定操作（灵感来自 Spring Data）
pv = counter.bind("page_views")
pv.incr()
pv.get()
pv.reset()
```

### ID 生成器

```python
from redis_kit.counter import IDGenerator, AsyncIDGenerator

id_gen = IDGenerator(conn, "order_id")

new_id = id_gen.next()         # 原子递增，返回 int
new_id = id_gen.next_str()     # "000000001" — 零填充字符串

# 带前缀的 ID
id_gen = IDGenerator(conn, "order_id", prefix="ORD", padding=8)
new_id = id_gen.next_str()     # "ORD00000001"
```

实现方案：Redis `INCR`（原子操作）。IDGenerator 是 Counter 的薄封装，附加格式化逻辑。

## 10. Session 模块

```python
from redis_kit.session import SessionManager, AsyncSessionManager

sessions = SessionManager(conn, prefix="session", ttl=1800)

# 创建 session
session_id = sessions.create({"user_id": 1, "role": "admin"})

# 读取
data = sessions.get(session_id)

# 更新（部分更新）
sessions.update(session_id, {"last_active": "2026-04-05T12:00:00"})

# 删除
sessions.delete(session_id)

# 刷新 TTL（活跃时续期）
sessions.refresh(session_id)
```

实现方案：每个 session 对应一个 Redis Hash。Session ID 默认使用 `uuid4` 生成，支持自定义生成器。

## 11. 异常处理

### 异常体系

```python
class RedisKitError(Exception): ...

# 连接
class RedisConnectionError(RedisKitError): ...
class ConnectionPoolExhaustedError(RedisConnectionError): ...

# 序列化
class SerializationError(RedisKitError): ...

# 锁
class LockError(RedisKitError): ...
class LockAcquireError(LockError): ...
class LockReleaseError(LockError): ...

# 缓存
class CacheError(RedisKitError): ...

# 队列
class QueueError(RedisKitError): ...
class QueueEmptyError(QueueError): ...

# 布隆过滤器
class BloomFilterError(RedisKitError): ...

# Session
class SessionError(RedisKitError): ...
class SessionNotFoundError(SessionError): ...
```

所有异常包装原始 `redis.RedisError`，附带上下文信息（操作、key、模块）。灵感来自 Spring Data 的异常翻译层。

### 降级策略

```python
from redis_kit.exceptions import FallbackPolicy

policy = FallbackPolicy(
    on_connection_error="return_none",   # "raise" | "return_none" | "callback"
    fallback=None,                       # "callback" 模式的回调函数
    log_on_fallback=True,                # 降级时记录日志（灵感来自 django-redis）
    logger=None,                         # 自定义 logger，默认 "redis_kit"
)

cache = Cache(conn, fallback_policy=policy)
```

默认：`raise`（快速失败）。用户主动选择降级。

## 12. 钩子与可观测性

### CommandHook 协议

```python
class CommandHook(Protocol):
    def before(self, command: str, key: str, args: tuple) -> None: ...
    def after(self, command: str, key: str, result: Any, duration_ms: float) -> None: ...
    def on_error(self, command: str, key: str, error: Exception) -> None: ...

class CompositeHook:
    """链式组合多个钩子。灵感来自老代码库的 Composite 模式。"""
    def __init__(self, *hooks: CommandHook): ...
```

### OpenTelemetry 集成

可选依赖：`pip install redis-kit[otel]`

```python
from redis_kit.observability import OpenTelemetryHook

hook = OpenTelemetryHook(service_name="myapp")
cache = Cache(conn, hooks=[hook])
```

自动为每个 Redis 操作创建 span，附带属性：command、key、duration、status。

### 指标收集

```python
from redis_kit.observability import MetricsCollector

metrics = MetricsCollector()
cache = Cache(conn, hooks=[metrics])

# 访问收集的指标
metrics.get_hit_rate("myapp:cache")
metrics.get_latency_percentiles("myapp:cache", p=[50, 95, 99])
```

## 13. Key 前缀系统

模块级透明 key 前缀（灵感来自 ioredis）：

```python
cache = Cache(conn, prefix="myapp:cache")
cache.set("user:1", data)  # 实际 Redis key："myapp:cache:user:1"
cache.get("user:1")        # 自动加前缀

lock = Lock(conn, prefix="myapp:lock")
with lock("resource"):     # 实际 key："myapp:lock:resource"
    ...
```

前缀透明应用，用户无需处理完整 key。分隔符默认 `:`，可通过 `NamespaceConfig` 配置。

## 14. 同步/异步策略

同步和异步各写一份。保持每个模块足够小，使重复代码可控。

非 IO 共享逻辑提取到各模块的 `_logic.py`：
- Key 构建和前缀处理
- 参数校验
- 序列化/压缩管道
- TTL 解析（字符串 "2h30m" -> 秒数）

IO 代码（实际 Redis 调用）在同步和异步类中分别编写。每个类目标 < 150 行。

```python
# 缓存模块结构示例
class _CacheLogic:
    """纯逻辑：无 IO，无 async。"""
    def _build_key(self, key: str) -> str: ...
    def _serialize(self, value: Any) -> bytes: ...
    def _deserialize(self, data: bytes) -> Any: ...
    def _parse_ttl(self, ttl: str | int | Callable) -> int: ...
    def _apply_jitter(self, ttl: int) -> int: ...

class Cache(_CacheLogic):
    def get(self, key: str) -> Any: ...       # 同步 IO
    def set(self, key: str, value: Any, ttl=None) -> None: ...

class AsyncCache(_CacheLogic):
    async def get(self, key: str) -> Any: ... # 异步 IO
    async def set(self, key: str, value: Any, ttl=None) -> None: ...
```

## 15. 依赖

### 必须
- `redis >= 7.4.0`

### 可选（extras）
- `redis-kit[msgpack]` -> `msgpack`
- `redis-kit[lz4]` -> `lz4`
- `redis-kit[zstd]` -> `zstandard`
- `redis-kit[otel]` -> `opentelemetry-api`, `opentelemetry-sdk`
- `redis-kit[all]` -> 以上全部

## 16. 公共 API（顶层导出）

```python
from redis_kit import (
    # 连接
    ConnectionManager,
    ConnectionConfig,

    # 缓存
    Cache, AsyncCache, cached,

    # 锁
    Lock, AsyncLock,

    # 队列
    PubSub, AsyncPubSub,
    DelayQueue, AsyncDelayQueue,
    ReliableQueue, AsyncReliableQueue,

    # 布隆过滤器
    BloomFilter, AsyncBloomFilter,

    # 计数器
    Counter, AsyncCounter,
    IDGenerator, AsyncIDGenerator,

    # Session
    SessionManager, AsyncSessionManager,

    # 序列化器
    JsonSerializer, MsgpackSerializer, PickleSerializer,

    # 压缩器
    ZstdCompressor, Lz4Compressor, ZlibCompressor,

    # 异常
    RedisKitError, FallbackPolicy,
)
```

## 17. v1 不包含的内容

- Sentinel / Cluster 拓扑支持（v2）
- Repository 模式（版本控制、审计、软删除）
- 限流器（令牌桶、滑动窗口）
- 自动 Pipeline 合并
- 多级缓存（本地 + Redis）
- 一致性哈希 / 分片
- Redis Streams 消费者组

## 18. 设计参考来源

| 来源 | 借鉴内容 |
|------|---------|
| Pottery | API 对齐 Python 标准库（Lock ~ threading.Lock，Counter ~ collections.Counter） |
| cashews | TTL 字符串格式 "2h30m"，多种缓存策略 |
| aiocache | Backend/Serializer/Plugin 三层分离 |
| django-redis | 压缩器独立为一层，TTL 操作集，基于 SCAN 的迭代 |
| Spring Data Redis | 绑定操作（.bind(key)），异常翻译层 |
| Lettuce | 连接的同步/异步视图 |
| ioredis | 透明 key 前缀 |
| BadrElfarri/rediskit | 装饰器中支持 callable 的 key/TTL/bypass |
| 老代码库 | CacheHook 设计，Event Loop 隔离，冻结配置 |
