# Findings

## 2026-04-05: 设计阶段研究结论

### 架构决策
- 最终方案: 方案 B（独立模块 + 共享连接 DI）
- 否决方案: 方案 A（Facade）过耦合；方案 C（Provider）不必要间接层

### 技术要点
- 同步/异步策略: 小类 + 共享 `_logic.py`
- 序列化/压缩: 独立两层 Protocol
- 异常处理: 具体异常 + FallbackPolicy
- 连接管理: 延迟初始化 + WeakKeyDictionary event loop 隔离

## 2026-04-09: Code Review 发现

### 已修复
1. Redis 7 兼容性: rpoplpush → lmove/blmove
2. _NONE_MARKER 兼容 decode_responses=True
3. AsyncCache.remember() 支持 async factory
4. @cached lock=True 未实现 → 移除
5. @cached 增加 prefix 参数
6. CompositeHook/MetricsCollector 导出
7. AsyncPubSub.listen() 补充
8. TTL=0 真值性 bug 修复

## 2026-04-10: Sentinel/Cluster 调研
- Spring Data Redis: typed config 多态做拓扑判别
- redis-py: Sentinel 是连接池级关注点
- cashews: group_keys_by_slot 按 slot 拆分多 key 操作
- Cluster pipeline 命令黑名单

## 2026-04-10: 限流器调研
- limits: Lua 原子操作 + List 时间戳滑动窗口
- redis-cell: 5 字段返回值映射 HTTP 头
- Spring: 令牌桶 Lua 双 key + TTL 自清理
- slowapi: DSL 字符串格式

## 2026-04-10: 多级缓存调研
- cashews: _empty 哨兵防穿透
- cacheme: 读回填 + single-flight
- node-cache-manager: write-through + refreshThreshold

## 2026-04-10: Repository 调研
- Spring Data Redis: @Version 乐观锁 + @CreatedDate 审计
- redis-om-python: Pydantic 模型映射 Hash
- Python 生态无库同时提供版本+软删除+审计

## 2026-04-10: 集成测试发现
- Docker Desktop for Windows 不支持 network_mode: host
- Redis Cluster 集成测试只能在 Linux CI 运行
- Sentinel discover_master 返回容器内 IP，本地需直连 master 端口

## 2026-04-10: v0.7.0 Code Review 发现

### 已修复（全部）
- Lock write() 非原子竞态 + Lua KEYS 未声明 + Watchdog 泄漏
- Repository 乐观锁 TOCTOU + _from_hash 类型解析 + 软删除版本化
- PubSub pmessage handler 查找用错 key + listen 无错误隔离
- Stream 异步 ACK 不可用
- ReliableQueue nack 非原子 + 丢失 msg_id
- Session create/update 非原子
- Cache remember(None) + apply_jitter 可返回 0 + @cached 无 TTL 守护
- MetricsCollector 无界 list + 非线程安全
- OTel span 即创即关 duration=0
- CompositeHook 异常不隔离
- BloomFilter 缺 reset() + SHA-256 性能 + exists_many N 次 RTT
- Repository find_all N+1 + restore 异常类型
- Session str() 丢失类型
- @cached 无 invalidation 机制

### fakeredis 限制
- XAUTOCLAIM 不支持，claim_stale 测试标记为 skip
- XPENDING IDLE 过滤用严格小于，需 sleep(0.01) workaround

## 2026-04-11: v0.7.1 Code Review 发现

### 已修复（全部 15 项）
- Repository save() 历史写入在乐观锁之前 — 版本冲突污染 history
- Repository _from_hash 中 f.default 可能是 MISSING — 用户子类字段崩溃
- Repository except Exception 静默降级 — int 字段可能保持字符串
- Repository datetime.now() 无时区 — 违反编码规范
- Repository delete() 无乐观锁 — 并发版本号错误
- Cache hooks.before()/on_error() 从未调用 — dead code
- Cache FallbackPolicy 存储未使用 — API 承诺未兑现
- PubSub except Exception: pass 吞异常 — 无日志
- OTel ContextVar 并发覆盖 — span 泄漏
- Session update() TOCTOU — 数据短暂可见
- Session refresh() 两步操作 — 竞态
- Stream ensure_group 宽泛异常 — 应捕获 ResponseError
- TieredCache 无法区分 None 和 miss
- Lock watchdog timer 列表无限增长
- rate_limit 装饰器 async 类型不匹配
