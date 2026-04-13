# Changelog

## [1.0.4] - 2026-04-14

### 修复
- **Cache**: `set_many` 每个 key 独立 TTL jitter，防止批量写入同时过期导致 cache stampede
- **Cache**: `_NONE_MARKER` 使用不可打印字符前后缀（`\x00`），消除与用户数据碰撞风险
- **Cache**: `delete()` 现在遵循 `FallbackPolicy` 降级策略，与 `get()`/`set()` 行为一致
- **Cache**: `_get_many_raw` 空列表短路返回，避免无意义的 Redis 往返
- **FallbackPolicy**: `on_connection_error` 添加运行时值域校验，拼写错误立即抛出 `ValueError`
- **Lock**: 可重入锁 owner 加入 `os.getpid()` 防止跨进程 ID 碰撞
- **Repository**: 历史写入合并到 Lua 脚本（`cjson.encode` + `lpush`），保证 save/delete/restore 的历史记录原子性
- **Repository**: `find_all()` 在 Cluster 模式下降级为逐个 `hgetall`，避免跨 slot pipeline 失败
- **Repository**: `_NONE_SENTINEL` 使用不可打印字符前后缀，消除碰撞风险
- **Bloom**: 哈希函数从 MD5 切换到 SHA-256，兼容 FIPS 环境
- **Serializers**: 所有序列化器（JSON/Pickle/Msgpack）统一 wrap 底层异常为 `SerializationError`
- **Connection**: `url` 与 `SentinelConfig`/`ClusterConfig` 同时使用时抛出 `ValueError`
- **SlidingWindowBase**: 添加 `limit`/`window` 正值校验，与 `TokenBucketBase` 一致

### 新增
- **Cache**: `@cached` 装饰器新增 `on_error` 参数（`"raise"` / `"execute"`），支持 Redis 故障时跳过缓存直接执行
- **Lock**: `read()` 新增 `blocking_timeout` 参数，支持重试等待（与 `write()` API 对称）
- **Lock**: `write()` 新增 `auto_renew` 参数，支持写锁自动续期
- **Queue**: `ReliableQueue`/`AsyncReliableQueue` 新增 `recover_stale()` 方法，恢复崩溃消费者遗留的消息
- **Observability**: `MetricsCollector.error_count()` 支持按命令过滤（`error_count(command="GET")`）

### 重构
- **Lock**: 提取 `_spin_acquire` 统一 4 处自旋等待模式，消除代码重复
- **Repository**: `_max_history_arg()` 上移至 `RepositoryBase`，消除 sync/async 子类重复
- **Serializers**: 提取 `wrap_serialization` 辅助函数统一异常包装模式
- **Stream**: `claim_stale` 解码逻辑提取为 `StreamConsumerBase._parse_autoclaim_messages`
- **Cache**: `set_many` TTL 解析优化为解析一次 + 每 key 独立 jitter
- **LRUCache**: 过期条目清理改用 `itertools.islice` 步进采样，避免全量 keys 拷贝
- **类型安全**: `@cached.on_error`、`@rate_limit.algorithm` 改为 `Literal` 类型；`FallbackPolicy._VALID_POLICIES` 添加 `ClassVar`
- **CI**: 添加全量可选依赖测试 job，覆盖 msgpack/lz4/zstd/otel 相关测试

### 杂项
- 移除误提交的 `__pycache__` 二进制文件
- Lua 脚本添加同步维护注释和 `cjson` 兼容性说明
- `@cached` 装饰器 `on_error="execute"` 降级路径添加 `logger.debug` 日志
- `BaseModel` docstring 引导使用 `dataclasses.replace()` 更新实体
- Stream `listen()` 文档说明 `auto_ack` 为「处理后 ACK」语义
- 文档站（中英双语）同步更新所有变更

### 统计
- 463 tests，0 failures

## [1.0.3] - 2026-04-13

### 修复
- **Cache**: `AsyncCache._handle_fallback` 现在正确 `await` 异步回调函数，而非静默丢弃协程
- **Cache**: `parse_ttl("0s")` 现在返回 0，与 `parse_ttl(0)` 行为一致
- **Connection**: `ConnectionManager._from_clients()` 不再创建并泄漏未关闭的事件循环
- **PubSub**: `listen()`/`stop()` 使用 `threading.Event` 替代裸布尔值，确保线程安全信号传递
- **Repository**: `save()` 新建实体时使用 `pipeline(transaction=True)` 确保 `hset` + `sadd` 原子性
- **Serializers**: `PickleSerializer` 实例化时发出安全警告日志，提醒不可反序列化不受信任的数据

### 新增
- **Cache**: `@cached` 装饰器新增 `compressor` 参数，与 `Cache` 编码格式兼容
- **Repository**: 新增 `is_cluster` 参数，`find_all()` 在 Cluster 模式下降级为逐个 `hgetall`，避免 CROSSSLOT 错误
- **Repository**: 新增 `max_history` 参数，通过 `ltrim` 限制版本历史列表增长

### 重构
- **Cache**: 提取 `CacheBase` 基类至 `redis_kit/cache/_base.py`，消除 `Cache`/`AsyncCache` 约 90 行重复代码
- **Exceptions**: `FallbackPolicy` 迁移至独立的 `redis_kit/policy.py`（`redis_kit.exceptions` 保留向后兼容 re-export）

### 杂项
- 添加 PEP 561 `py.typed` 标记文件
- `.gitignore` 补充 `.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`

### 统计
- 463 tests，0 failures

## [1.0.2] - 2026-04-11

### 修复
- **Cache**: `parse_ttl()` 拒绝带尾随垃圾的 TTL 字符串，而非部分解析
- **RateLimit**: `parse_rate_dsl()` 要求完整匹配 DSL，拒绝尾随内容
- **RateLimit**: `@rate_limit` 校验 `algorithm` 参数，未知值抛出 `ValueError`
- **Repository**: `delete()` 和 `restore()` 现在记录操作前的实体状态到历史

### 文档
- 同步 README 和中英文模块文档，说明严格的 TTL/DSL 校验行为
- 明确 Repository 历史记录包含 `save()`、`delete()`、`restore()` 前的状态

### 测试
- 新增 TTL 尾随垃圾拒绝、限流 DSL/algorithm 校验、Repository delete/restore 历史的回归测试
- 453 tests，0 failures

## [1.0.1] - 2026-04-11

### 修复
- **Stream**: `StreamMessage.async_ack()` 在同步消费者上调用时抛出清晰的 `StreamError`，而非泄漏 `AttributeError`
- **Queue**: `AsyncPubSub.listen()` 正确 `await` 异步可调用对象（`async __call__`），不再丢弃未等待的协程
- **Cache**: `delete_pattern()` 在集群模式下逐个删除 key，避免跨 slot 的多 key `DELETE` 失败

### 文档
- **Cache**: 异步 `@cached` 示例统一使用 `conn.async_client`
- **RateLimit**: 异步 `@rate_limit` 示例统一使用 `conn.async_client`

### 测试
- 新增 sync/async Stream ACK 误用、异步 PubSub 处理器、集群安全缓存模式删除的回归测试
- 448 tests，0 failures

## [1.0.0] - 2026-04-11

**首个稳定版本。** 4 轮代码审查，444 个测试，11 个模块，可用于生产。

### 变更
- `Development Status` 从 `Beta` 升级为 `Production/Stable`
- `CommandHook`、`Serializer`、`Compressor` 协议从包根导出（`from redis_kit import CommandHook`）

### 修复
- **Lock**: `write()` 检查 `WRITE_RELEASE` 返回值，owner 不匹配时抛出 `LockReleaseError` — 此前静默忽略
- **Cache**: `get_many()` 和 `set_many()` 在连接错误时应用 `FallbackPolicy` — 此前总是重新抛出，与 `get()`/`set()` 不一致
- **Cache**: `@cached` 装饰器文档明确无 fallback/hooks 支持，`bypass` 为强制刷新语义
- **Connection**: `close()` 文档说明 TOCTOU 约束（不可在其他线程使用 `sync_client` 时调用）

### 重构
- Session `_UPDATE_SCRIPT` Lua 脚本提取至共享的 `redis_kit/session/_lua.py` — 防止 sync/async 静默分歧
- `_NEGATIVE` 哨兵值集中到 `redis_kit/cache/_logic.py` — 此前在 `tiered.py` 和 `async_tiered.py` 中重复
- Repository `_to_hash`/`_from_hash` 提取至共享的 `redis_kit/repository/_hash.py`
- Cache `get_many` 委托给 `_get_many_raw`，统一 hooks/fallback

### 统计
- 444 tests，0 failures
- 68 个源文件，11 个模块
- 4 轮代码审查（0 个 Critical 问题遗留）

## [0.7.2] - 2026-04-11

### 修复
- **Cache**: `parse_ttl()` 拒绝负数 TTL，抛出 `ValueError` — 此前静默创建永久 key
- **Cache**: `_notify_hooks()` 用 `try/except` 包裹每个 hook 调用 — 异常 hook 不再中断缓存操作
- **Cache**: `TieredCache.get_many()` 正确区分缓存的 `None` 值和 cache miss
- **Cache**: `AsyncTieredCache` 新增 `iter_keys()` 方法 — 恢复 sync/async API 对等
- **Connection**: `ConnectionManager.close()` 获取 `_sync_lock` — 修复并发 `sync_client` 访问的竞态
- **Exceptions**: `FallbackPolicy(on_connection_error="callback")` 在构造时校验 `fallback` 非 `None`
- **Lock**: `read()` 和 `write()` 上下文管理器改用 `except/else` — 释放失败不再遮蔽原始异常
- **PubSub**: `AsyncPubSub.listen()` 检测并 `await` 异步处理器 — 此前静默丢弃未等待的协程
- **Queue**: `DelayQueue.put()` 和 `poll()` 使用 Redis 服务端 `TIME` — 消除分布式时钟漂移
- **Repository**: `restore()` 使用乐观锁，递增 `version`，更新 `updated_at`

### 移除
- 死文件 `redis_kit/cache/_cluster.py`（空文件，从未导入）
- 死函数 `resolve_callable()`（从未使用）
- `Repository._from_hash()` 中的死代码分支

### 统计
- 430 tests（从 414 增加），0 failures
- 24 files changed，+400 -68 lines

## [0.7.1] - 2026-04-11

### 修复（Critical）
- **Repository**: `save()` 的 history lpush 移到乐观锁检查之后 — 防止版本冲突时污染历史
- **PubSub**: `except Exception: pass` 替换为 `_logger.exception()` — 错误不再被静默吞没
- **RateLimit**: `@rate_limit` 装饰器类型提示更新，接受同步和异步 Redis 客户端
- **Cache**: `hooks.before()` 和 `hooks.on_error()` 在所有操作中调用 — 此前是死代码
- **Cache**: `FallbackPolicy` 完整实现三种策略：`"raise"`、`"return_none"`、`"callback"`
- **OTel**: `ContextVar` 替换为 span 栈（`ContextVar[list[Span]]`）— 修复并发异步 span 泄漏

### 修复（Important）
- **Repository**: `_from_hash` 处理 `dataclasses.MISSING` 默认字段不再崩溃
- **Repository**: `get_type_hints` 捕获 `(NameError, AttributeError)` 而非宽泛的 `Exception`
- **Repository**: `datetime.now()` 替换为 `datetime.now(tz=UTC)` 确保时区安全
- **Session**: `update()` 使用 Lua 脚本实现原子 EXISTS+HSET+EXPIRE
- **Session**: `refresh()` 简化为单次 `expire()` 调用，消除 TOCTOU 竞态
- **Stream**: `ensure_group()` 捕获 `ResponseError` 而非宽泛的 `Exception`
- **TieredCache**: `get()` 使用 `_get_raw()` 区分缓存的 `None` 和 cache miss
- **Lock**: 看门狗定时器列表在 `renew()` 中清理，防止内存泄漏
- **Repository**: `delete()` 使用 Lua 乐观锁 — 防止并发版本冲突

### 改进
- **RateLimit**: Lua 脚本使用 `redis.call("TIME")` 替代客户端 `time.time()` — 消除分布式时钟漂移
- **Lock**: `LockReleaseError` 不再在上下文管理器中遮蔽原始异常
- **Connection**: `aclose()` 关闭所有 event loop 的异步客户端
- **PubSub**: `listen()` 重构为 `get_message()` 轮询，新增 `stop()` 方法和 `timeout` 参数
- **Stream**: `StreamMessage._consumer` 类型标注为 `StreamConsumer | AsyncStreamConsumer | None`
- **Cache**: `delete()` 成功时调用 `after` hook
- **Connection**: `aclose()` 客户端关闭失败时记录 debug 日志

### 统计
- 414 tests（从 336 增加），0 failures
- 36 files changed，+2199 -312 lines

## [0.7.0] - 2026-04-10

### 修复（Critical）
- **Lock**: 读写锁通过 Lua 脚本完全原子化，修复 `write()` 竞态条件
- **Lock**: Lua 脚本在 `KEYS[]` 中声明所有访问的 key，符合 Redis Cluster 规范
- **Lock**: 看门狗定时器链正确跟踪和取消
- **Cache**: `remember()` 正确缓存工厂返回的 `None` 值
- **Repository**: 乐观锁改为单个 Lua 脚本中的原子 check-and-write
- **PubSub**: 模式订阅处理器查找修复 — 使用 `message["pattern"]`
- **Stream**: 新增 `StreamMessage.async_ack()` 用于异步消费者手动 ACK
- **Queue**: `ReliableQueue._nack()` 通过 Lua 实现原子操作，保留原始 msg_id
- **Session**: `create()` 使用 pipeline 实现原子 hset+expire
- **Connection**: `ClusterConfig.read_from_replicas` 传递给 RedisCluster

### 修复（Important）
- **Cache**: `apply_jitter` 最小值钳制为 1，防止 TTL=0 错误
- **Cache**: `@cached` 装饰器对 TTL=0 降级为 `SET`
- **Cache**: `AsyncCache` 完整支持 hook（与同步 `Cache` 对等）
- **Cache**: `delete_pattern` 使用批量 `DELETE` 替代逐 key 调用
- **Cache**: `TieredCache.get_many()` 对 L2 miss 应用负缓存
- **Cache**: 统一 `_MISS` 哨兵值到 `_logic.py` 和 `local.py`
- **Observability**: `MetricsCollector` 线程安全，使用有界 `deque`
- **Observability**: `OpenTelemetryHook` 在 `before()` 创建 span，在 `after()`/`on_error()` 结束
- **Hooks**: `CompositeHook` 隔离各 hook 异常
- **Connection**: `from_url` 路径传递 `ssl` 配置
- **Connection**: `assert isinstance` 替换为 `raise TypeError`（兼容 `python -O`）
- **Config**: `SentinelConfig.sentinels` / `ClusterConfig.startup_nodes` 改为不可变 `tuple`
- **Repository**: `_from_hash` 使用 `typing.get_type_hints()` 实现健壮的类型解析
- **Repository**: 软删除递增 `version` 和 `updated_at`
- **Queue**: `DelayQueue.put()` 使用唯一 member ID 防止去重
- **PubSub**: `listen()` 循环中的逐消息错误隔离
- **RateLimit**: `TokenBucketLimiter` 校验 `rate > 0` 和 `capacity > 0`
- **Session**: `update()` 使用 pipeline 修复 TOCTOU 竞态，刷新 TTL
- **Bloom**: 新增 `reset()` 方法
- **Exports**: 所有 20 个异常从顶层 `__init__.py` 导出

### 改进
- **Cache**: 移除死代码 `group_keys_by_slot`
- **Cache**: `Cache.set()` hook 测量实际耗时而非硬编码 0
- **Cache**: `LRUCache.size` 属性线程安全
- **Cache**: `TieredCache` / `AsyncTieredCache` 支持 `bind()` 方法
- **Cache**: `@cached` 装饰器支持 `.invalidate()` 缓存失效
- **Bloom**: 从 SHA-256 切换为 double hashing（基于 MD5，~3.5x 更快）
- **Bloom**: `exists_many` 使用单次 pipeline 替代 N 次往返
- **Repository**: `find_all()` 使用 pipeline 替代 N+1 查询
- **Repository**: `restore()` 对未删除实体抛出 `RepositoryError`（而非 `EntityNotFoundError`）
- **Session**: 值使用 JSON 序列化（保留类型）替代 `str()`
- **Counter**: `decr()` 文档说明值可低于零
- **Queue**: `DelayQueue` Lua poll 脚本提取至共享 `queue/_lua.py`
- 新增 13 个异步测试

### 统计
- 336 tests（从 299 增加），0 failures
- 42 files changed，+906 -143 lines

## [0.6.1] - 2026-04-10

### 改进
- 全模块异步单元测试 — 覆盖率 73% → 82%
- 真实 Redis 集成测试（Standalone 15 + Sentinel 3 + Cluster 4）
- docker-compose 本地测试环境（Standalone + Sentinel + Cluster）
- CI: 各拓扑独立集成测试 job
- 添加 pytest-cov 到开发依赖

## [0.6.0] - 2026-04-10

### 新增
- **Repository** 模块 — 结构化实体存储：
  - `BaseModel` — dataclass 基类，含审计元数据（id、version、created_at、updated_at、deleted、deleted_at）
  - `Repository` / `AsyncRepository` — 完整 CRUD，Redis Hash 存储
  - **乐观锁** — Lua 脚本版本检查，冲突时抛出 `OptimisticLockError`
  - **软删除** — `delete()` 标记删除，`restore()` 恢复，`hard_delete()` 永久删除
  - **审计字段** — `created_at`/`updated_at` 保存时自动填充
  - **版本历史** — `get_history()` 返回所有历史版本（Redis List）
  - `find_all()`、`find_including_deleted()` 查询方法
  - `RepositoryError`、`EntityNotFoundError`、`OptimisticLockError` 异常
- 新增 22 个测试（共 266 个）

## [0.5.0] - 2026-04-10

### 新增
- **Redis Streams** 模块 — 消费者组抽象：
  - `StreamProducer` / `AsyncStreamProducer` — XADD、XLEN、XTRIM
  - `StreamConsumer` / `AsyncStreamConsumer` — XREADGROUP，自动/手动 ACK，消费者组管理
  - `StreamMessage` — 消息 dataclass，支持 `.ack()`
  - `ensure_group()` — 幂等创建消费者组（XGROUP CREATE）
  - `claim_stale()` — 死信恢复（XAUTOCLAIM）
  - `pending()` — 查看未确认消息（XPENDING）
  - `StreamError` 异常
- 新增 14 个测试（共 244 个）

## [0.4.0] - 2026-04-10

### 新增
- **多级缓存** 模块 — L1（本地 LRU）+ L2（Redis）两级缓存：
  - `LRUCache` — 线程安全，逐条 TTL，LRU 驱逐，零依赖
  - `TieredCache` / `AsyncTieredCache` — 透明 L1→L2 读穿透回填
  - 负缓存 — 短 TTL `_NEGATIVE` 标记防止重复 L2 miss 穿透
  - `get_many` 优化 — 批量 L1 查找，仅 miss 的 key 查询 L2
  - 写穿透 — `set`/`set_many` 同时写 L1 和 L2
  - `invalidate_local()` / `clear_local()` / `local_size` 本地缓存管理
- 新增 30 个测试（共 230 个）

## [0.3.0] - 2026-04-10

### 新增
- **限流器** 模块，两种算法：
  - `TokenBucketLimiter` / `AsyncTokenBucketLimiter` — 平滑流量，允许突发，Lua 脚本原子操作
  - `SlidingWindowLimiter` / `AsyncSlidingWindowLimiter` — 精确计数，Redis Sorted Set + Lua 脚本
- `@rate_limit` 装饰器，DSL 解析（如 `"100/minute"`）
- `RateLimitResult` dataclass（allowed、limit、remaining、retry_after、reset_at）— 映射 HTTP 限流头
- `RateLimitExceeded` 异常，携带 result 上下文
- 新增 30 个测试（共 200 个）

## [0.2.0] - 2026-04-10

### 新增
- **Sentinel 支持**: `SentinelConfig` — 自动故障转移，上层模块无感知
- **Cluster 支持**: `ClusterConfig` — 数据分片，多 key 操作自动降级
- `ConnectionManager.topology`、`.is_cluster`、`.is_sentinel` 属性
- `Cache`/`AsyncCache` `is_cluster` 参数 — `get_many`/`set_many` 自动降级为单条操作
- `Lock`/`AsyncLock` `is_cluster` 参数 — key 使用 `{hash_tag}` 包裹确保 Lua 脚本 slot 安全
- `TopologyConstraintError` 异常
- `group_keys_by_slot()` 工具函数
- 新增 22 个测试（共 170 个）

## [0.1.1] - 2026-04-10

### 修复
- 读写锁使用 Lua 脚本实现原子 acquire/release 操作
- `ReliableQueue._ack()` 使用直接 `lrem` 替代 O(N) 扫描
- `BloomFilter` 和 `IDGenerator` 支持可配置的 key 前缀

## [0.1.0] - 2026-04-09

### 新增
- **Cache** 模块: `Cache`、`AsyncCache`、`BoundCache`、`@cached` 装饰器
  - TTL 字符串格式解析（"2h30m"）
  - TTL 抖动防雪崩
  - 批量操作（`get_many`、`set_many`）
  - 基于 SCAN 的模式操作（`delete_pattern`、`iter_keys`）
  - Cache-Aside 模式（`remember`）
  - None 值缓存（防穿透）
- **Lock** 模块: `Lock`、`AsyncLock`
  - 基本分布式锁（SET NX EX + Lua 释放）
  - 可重入锁（Hash 结构 owner + count）
  - 读写锁
  - 看门狗自动续期
- **Queue** 模块: `PubSub`、`AsyncPubSub`、`DelayQueue`、`AsyncDelayQueue`、`ReliableQueue`、`AsyncReliableQueue`
  - 延迟队列基于 Sorted Set + Lua poll
  - 可靠队列基于 LMOVE + ack/nack
- **BloomFilter** 模块: `BloomFilter`、`AsyncBloomFilter`
  - SHA-256 多哈希，Pipeline 位操作
- **Counter** 模块: `Counter`、`AsyncCounter`、`IDGenerator`、`AsyncIDGenerator`
  - BoundCounter 单 key 操作
  - 零填充 ID 生成
- **Session** 模块: `SessionManager`、`AsyncSessionManager`
  - Redis Hash 会话存储，CRUD，TTL 刷新
- **可观测性**: `MetricsCollector`、`OpenTelemetryHook`（可选）
- **序列化器**: `JsonSerializer`、`PickleSerializer`、`MsgpackSerializer`（可选）
- **压缩器**: `ZlibCompressor`、`ZstdCompressor`（可选）、`Lz4Compressor`（可选）
- **ConnectionManager**: 同步/异步视图，惰性初始化，事件循环隔离
- **异常层次结构**: `RedisKitError` 基类 + 模块特定异常
- **FallbackPolicy**: 可配置降级策略（"raise" / "return_none" / "callback"）
- **CommandHook** 协议 + `CompositeHook` 可扩展可观测性
