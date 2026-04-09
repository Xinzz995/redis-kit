# Changelog

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
