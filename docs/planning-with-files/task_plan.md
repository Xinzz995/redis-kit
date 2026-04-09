# Task Plan

> 详细实施步骤见：`docs/superpowers/plans/2026-04-05-redis-kit-v1.md`

## Phase 1: 基础设施
| Task | 描述 | 状态 |
|------|------|------|
| 1 | Project Scaffolding & Dev Tooling | done |
| 2 | Config (ConnectionConfig, NamespaceConfig) | done |
| 3 | Exceptions (异常体系 + FallbackPolicy) | done |
| 4 | Serializers (Protocol + Json/Pickle/Msgpack) | done |
| 5 | Compressors (Protocol + Zlib/Zstd/Lz4) | done |
| 6 | Hooks (CommandHook Protocol + CompositeHook) | done |
| 7 | ConnectionManager (同步/异步视图, event loop 隔离) | done |

## Phase 2: 独立模块
| Task | 描述 | 状态 |
|------|------|------|
| 8 | Counter (Counter + BoundCounter + IDGenerator) | done |
| 9 | BloomFilter (SHA-256 哈希, pipeline 位操作) | done |
| 10 | SessionManager (Redis Hash, CRUD + refresh) | done |

## Phase 3: 依赖模块
| Task | 描述 | 状态 |
|------|------|------|
| 11 | Lock (基础锁 + 可重入 + 读写锁 + 看门狗) | done |
| 12 | Cache (Cache + BoundCache + _logic.py) | done |
| 13 | @cached Decorator (callable key/ttl/bypass, 自动检测同步/异步) | done |
| 14 | Queue (PubSub + DelayQueue + ReliableQueue) | done |

## Phase 4: 可观测性
| Task | 描述 | 状态 |
|------|------|------|
| 15 | Observability (MetricsCollector + OpenTelemetryHook) | done |

## Phase 5: 集成与发布
| Task | 描述 | 状态 |
|------|------|------|
| 16 | Public API exports (__init__.py) | done |
