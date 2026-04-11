# redis-py-kit

**企业级 Python Redis 工具库，支持同步/异步双模 API。**

[![PyPI](https://img.shields.io/pypi/v/redis-py-kit.svg)](https://pypi.org/project/redis-py-kit/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Status](https://img.shields.io/badge/status-Production%2FStable-brightgreen.svg)](https://pypi.org/project/redis-py-kit/)

## 功能特性

| 模块 | 说明 |
|------|------|
| [缓存](modules/cache.md) | Get/Set/Delete、TTL、批量操作、`@cached` 装饰器、TTL 抖动 |
| [多级缓存](modules/tiered-cache.md) | L1 本地 LRU + L2 Redis，读穿透，空值缓存（Negative Caching） |
| [分布式锁](modules/lock.md) | 基本锁、可重入锁、读写锁、看门狗自动续期 |
| [消息队列](modules/queue.md) | PubSub、延迟队列（DelayQueue）、可靠队列（ReliableQueue） |
| [Streams](modules/streams.md) | 消费者组、自动/手动 ACK、死信恢复 |
| [布隆过滤器](modules/bloom.md) | SHA-256 多哈希、Pipeline 位操作 |
| [计数器](modules/counter.md) | 原子 INCR/DECR、有界计数器（BoundCounter）、ID 生成器 |
| [Session](modules/session.md) | Redis Hash 会话存储、CRUD、TTL 刷新 |
| [限流器](modules/ratelimit.md) | 令牌桶、滑动窗口、`@rate_limit` 装饰器 |
| [Repository](modules/repository.md) | Dataclass 实体存储、版本控制、软删除、审计、历史记录 |
| [可观测性](modules/observability.md) | MetricsCollector、OpenTelemetry 集成 |

## 快速安装

```bash
pip install redis-py-kit
```

## 快速示例

```python
from redis_kit import ConnectionManager, Cache

conn = ConnectionManager(url="redis://localhost:6379/0")
cache = Cache(conn.sync_client, prefix="myapp:cache")

cache.set("user:1", {"name": "Alice"}, ttl="2h30m")
user = cache.get("user:1")
```
