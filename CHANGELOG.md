# Changelog

## [0.6.1] - 2026-04-10

### Improved
- Async unit tests for all modules — coverage 73% → 82%
- Integration tests with real Redis (Standalone 15 + Sentinel 3 + Cluster 4)
- docker-compose for local testing (Standalone + Sentinel + Cluster)
- CI: separate integration test jobs for each topology
- Added pytest-cov to dev dependencies

## [0.6.0] - 2026-04-10

### Added
- **Repository** module — structured entity storage with enterprise features:
  - `BaseModel` — dataclass base with audit metadata (id, version, created_at, updated_at, deleted, deleted_at)
  - `Repository` / `AsyncRepository` — full CRUD with Redis Hash storage
  - **Optimistic locking** — Lua-scripted version check, `OptimisticLockError` on conflict
  - **Soft delete** — `delete()` marks as deleted, `restore()` recovers, `hard_delete()` removes permanently
  - **Audit fields** — `created_at`/`updated_at` auto-populated on save
  - **Version history** — `get_history()` returns all previous versions (Redis List)
  - `find_all()`, `find_including_deleted()` for querying
  - `RepositoryError`, `EntityNotFoundError`, `OptimisticLockError` exceptions
- 22 new tests (266 total)

## [0.5.0] - 2026-04-10

### Added
- **Redis Streams** module — consumer group abstraction replacing ReliableQueue:
  - `StreamProducer` / `AsyncStreamProducer` — XADD, XLEN, XTRIM
  - `StreamConsumer` / `AsyncStreamConsumer` — XREADGROUP with auto/manual ACK, consumer group management
  - `StreamMessage` — message dataclass with `.ack()` support
  - `ensure_group()` — idempotent consumer group creation (XGROUP CREATE)
  - `claim_stale()` — dead letter handling via XAUTOCLAIM
  - `pending()` — view unacknowledged messages via XPENDING
  - `StreamError` exception
- 14 new tests (244 total)

## [0.4.0] - 2026-04-10

### Added
- **Tiered Cache** module — L1 (local LRU) + L2 (Redis) two-tier cache:
  - `LRUCache` — thread-safe, per-entry TTL, LRU eviction, zero dependencies
  - `TieredCache` / `AsyncTieredCache` — transparent L1→L2 read-through with backfill
  - Negative caching — short-TTL `_NEGATIVE` marker prevents repeated L2 miss penetration
  - `get_many` optimization — batch L1 lookup, only missed keys go to L2
  - Write-through — `set`/`set_many` write both L1 and L2
  - `invalidate_local()` / `clear_local()` / `local_size` for local cache management
- 30 new tests (230 total)

## [0.3.0] - 2026-04-10

### Added
- **Rate Limiter** module with two algorithms:
  - `TokenBucketLimiter` / `AsyncTokenBucketLimiter` — smooth traffic with burst tolerance, Lua-scripted atomic operations
  - `SlidingWindowLimiter` / `AsyncSlidingWindowLimiter` — exact counting with Redis Sorted Set + Lua script
- `@rate_limit` decorator with DSL parsing (e.g. `"100/minute"`)
- `RateLimitResult` dataclass (allowed, limit, remaining, retry_after, reset_at) — maps to HTTP rate limit headers
- `RateLimitExceeded` exception with result context
- 30 new tests (200 total)

## [0.2.0] - 2026-04-10

### Added
- **Sentinel support**: `SentinelConfig` — automatic failover, upstream modules unaware
- **Cluster support**: `ClusterConfig` — data sharding, multi-key operations auto-degrade
- `ConnectionManager.topology`, `.is_cluster`, `.is_sentinel` properties
- `Cache`/`AsyncCache` `is_cluster` parameter — `get_many`/`set_many` auto-degrade to individual operations
- `Lock`/`AsyncLock` `is_cluster` parameter — keys wrapped in `{hash_tag}` for Lua script slot safety
- `TopologyConstraintError` exception
- `group_keys_by_slot()` utility for Cluster multi-key operations
- 22 new tests (170 total)

## [0.1.1] - 2026-04-10

### Fixed
- R/W lock now uses Lua scripts for atomic read-acquire/release operations
- `ReliableQueue._ack()` uses direct `lrem` with raw payload instead of O(N) scan
- `BloomFilter` and `IDGenerator` now accept configurable key prefix (default unchanged)

## [0.1.0] - 2026-04-09

### Added
- **Cache** module: `Cache`, `AsyncCache`, `BoundCache`, `@cached` decorator
  - TTL string format parsing ("2h30m")
  - TTL jitter for avalanche protection
  - Batch operations (`get_many`, `set_many`)
  - SCAN-based pattern operations (`delete_pattern`, `iter_keys`)
  - Cache-aside pattern (`remember`)
  - None value caching (anti-penetration)
- **Lock** module: `Lock`, `AsyncLock`
  - Basic distributed lock (SET NX EX + Lua release)
  - Reentrant lock (Hash-based owner + count)
  - Read-write lock
  - Watchdog auto-renewal
- **Queue** module: `PubSub`, `AsyncPubSub`, `DelayQueue`, `AsyncDelayQueue`, `ReliableQueue`, `AsyncReliableQueue`
  - DelayQueue via Sorted Set + Lua poll
  - ReliableQueue via LMOVE + ack/nack
- **BloomFilter** module: `BloomFilter`, `AsyncBloomFilter`
  - SHA-256 multi-hash, pipeline-based bit operations
- **Counter** module: `Counter`, `AsyncCounter`, `IDGenerator`, `AsyncIDGenerator`
  - BoundCounter for single-key operations
  - Zero-padded ID generation
- **Session** module: `SessionManager`, `AsyncSessionManager`
  - Redis Hash per session, CRUD, TTL refresh
- **Observability**: `MetricsCollector`, `OpenTelemetryHook` (optional)
- **Serializers**: `JsonSerializer`, `PickleSerializer`, `MsgpackSerializer` (optional)
- **Compressors**: `ZlibCompressor`, `ZstdCompressor` (optional), `Lz4Compressor` (optional)
- **ConnectionManager**: Sync/async views, lazy init, event loop isolation
- **Exception hierarchy**: `RedisKitError` base + module-specific exceptions
- **FallbackPolicy**: Configurable degradation ("raise" / "return_none" / "callback")
- **CommandHook** protocol + `CompositeHook` for extensible observability
