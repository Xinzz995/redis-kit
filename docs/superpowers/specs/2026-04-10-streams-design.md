# redis-py-kit Redis Streams 消费者组设计

## 1. 概述

为 redis-py-kit 添加 Redis Streams 消费者组模块，作为 ReliableQueue 的高级替代。提供 StreamProducer + StreamConsumer 分离式 API，支持自动/手动 ACK，死信消息认领。

### 设计参考

| 来源 | 借鉴内容 |
|------|---------|
| walrus | `consumer(name)` 工厂；`pending()`/`autoclaim()` 一等公民 |
| Spring | 三层 receive（standalone / manual-ack / auto-ack）；`Consumer(group, name)` 值对象 |
| redis-py | 原生 XADD/XREADGROUP/XACK/XPENDING/XAUTOCLAIM 命令映射 |

## 2. 文件结构

```
redis_kit/stream/
├── __init__.py             # 导出所有公共类
├── message.py              # StreamMessage 数据类
├── producer.py             # StreamProducer (sync)
├── async_producer.py       # AsyncStreamProducer
├── consumer.py             # StreamConsumer (sync)
└── async_consumer.py       # AsyncStreamConsumer
```

## 3. StreamMessage

```python
@dataclass
class StreamMessage:
    id: str                    # Redis Stream message ID
    data: dict[str, str]       # 消息字段
    stream: str                # Stream 名称
    _consumer: Any = None      # 关联的消费者（用于 ack）

    def ack(self) -> None:
        if self._consumer is None:
            raise StreamError("Cannot ack: message not associated with a consumer")
        self._consumer._ack(self.id)
```

## 4. StreamProducer

```python
class StreamProducer:
    def __init__(self, client, stream: str, prefix: str = "", maxlen: int | None = None) -> None: ...

    def add(self, data: dict[str, str], msg_id: str = "*") -> str:
        """XADD，返回消息 ID。使用实例 maxlen 截断。"""

    def len(self) -> int:
        """XLEN。"""

    def trim(self, maxlen: int, approximate: bool = True) -> int:
        """XTRIM。"""
```

## 5. StreamConsumer

```python
class StreamConsumer:
    def __init__(
        self, client, stream: str, group: str, consumer_name: str,
        prefix: str = "", auto_ack: bool = True,
    ) -> None: ...

    def ensure_group(self, start_id: str = "0") -> None:
        """XGROUP CREATE（幂等）。"""

    def listen(self, count: int = 10, block: int = 5000) -> Iterator[StreamMessage]:
        """XREADGROUP，迭代消息。auto_ack 模式下迭代后自动 ACK。"""

    def pending(self, count: int = 10, min_idle_ms: int = 0) -> list[dict]:
        """XPENDING RANGE，查看未确认消息摘要。"""

    def claim_stale(self, min_idle_ms: int = 60000, count: int = 10) -> list[StreamMessage]:
        """XAUTOCLAIM，认领超时消息。"""

    def _ack(self, msg_id: str) -> None:
        """XACK。"""

    def destroy_group(self) -> None:
        """XGROUP DESTROY。"""
```

### listen() 行为

- `auto_ack=True`：每条消息迭代完毕后自动调用 XACK
- `auto_ack=False`：用户必须手动调用 `message.ack()`，不 ack 的消息下次 listen 不会重新投递（需要通过 `claim_stale` 认领）
- `block=5000`：默认阻塞 5 秒等待新消息，返回空则退出迭代器
- 使用 `>` 作为 XREADGROUP 的 ID，只读取新消息

### claim_stale() 行为

- 使用 XAUTOCLAIM 命令
- 认领 `min_idle_ms` 毫秒内未被 ACK 的消息
- 返回 StreamMessage 列表，可 ack

## 6. 异步变体

`AsyncStreamProducer` 和 `AsyncStreamConsumer` 完全对称：

```python
async for message in consumer.listen(count=10, block=5000):
    await process(message.data)
    # auto_ack 模式自动确认
```

`AsyncStreamConsumer.listen()` 返回 `AsyncIterator[StreamMessage]`。

## 7. 异常

```python
class StreamError(RedisKitError):
    """Stream operation failed."""
```

## 8. Key 前缀

与其他模块一致：`{prefix}:{stream}` 作为实际 Redis key。

## 9. 公共 API 导出

```python
from redis_kit import (
    StreamProducer, AsyncStreamProducer,
    StreamConsumer, AsyncStreamConsumer,
    StreamMessage,
)
```

## 10. 用户使用示例

```python
from redis_kit import ConnectionManager, StreamProducer, StreamConsumer

conn = ConnectionManager(url="redis://localhost:6379/0")

# 生产者
producer = StreamProducer(conn.sync_client, stream="orders", maxlen=10000)
msg_id = producer.add({"order_id": "123", "status": "created"})

# 消费者 — 自动 ACK
consumer = StreamConsumer(
    conn.sync_client, stream="orders",
    group="order-processor", consumer_name="worker-1",
    auto_ack=True,
)
consumer.ensure_group()

for message in consumer.listen(count=10, block=5000):
    print(f"Processing {message.id}: {message.data}")

# 手动 ACK 模式
consumer = StreamConsumer(
    conn.sync_client, stream="orders",
    group="order-processor", consumer_name="worker-2",
    auto_ack=False,
)
consumer.ensure_group()

for message in consumer.listen(count=10, block=5000):
    try:
        process(message.data)
        message.ack()
    except Exception:
        pass  # 不 ack，通过 claim_stale 后续处理

# 死信处理
stale = consumer.claim_stale(min_idle_ms=60000, count=10)
for msg in stale:
    handle_dead_letter(msg)
    msg.ack()
```

## 11. 影响面

| 文件 | 改动 |
|------|------|
| `redis_kit/stream/` | 新模块 |
| `redis_kit/exceptions.py` | 新增 `StreamError` |
| `redis_kit/__init__.py` | 导出新类型 |
| 其他模块 | 零改动 |
