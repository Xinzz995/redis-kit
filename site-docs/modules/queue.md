# 消息队列

包含 PubSub、延迟队列（DelayQueue）和可靠队列（ReliableQueue）。

## PubSub

```python
from redis_kit import PubSub

pubsub = PubSub(conn.sync_client, prefix="myapp")
pubsub.publish("events", {"type": "user_created", "id": 1})

def handler(message):
    print(message)

pubsub.subscribe("events", handler)
pubsub.listen()
```

### 优雅停止

`listen()` 支持优雅停止和可配置的轮询超时：

```python
import threading

pubsub = PubSub(conn.sync_client, prefix="myapp")
pubsub.subscribe("events", handler)

# 在后台线程中运行
thread = threading.Thread(target=pubsub.listen, kwargs={"timeout": 1.0})
thread.start()

# 需要停止时
pubsub.stop()   # 信号 listen() 在当前轮询周期后退出
thread.join()

# 或者直接关闭（同时停止监听并释放资源）
pubsub.close()
```

### 异步处理器

`AsyncPubSub` 同时支持同步和异步处理器，异步处理器会自动被 `await`：

```python
from redis_kit import AsyncPubSub

async_pubsub = AsyncPubSub(conn.async_client, prefix="myapp")

async def async_handler(message):
    await save_to_db(message)

await async_pubsub.subscribe("events", async_handler)
await async_pubsub.listen(timeout=1.0)
```

### 模式订阅

```python
pubsub.psubscribe("events.*", handler)  # 匹配 events.order、events.user 等
```

## 延迟队列（Delay Queue）

基于 Sorted Set 的延迟执行队列。

```python
from redis_kit import DelayQueue

dq = DelayQueue(conn.sync_client, "order:timeout")
dq.put({"order_id": 123}, delay=1800)  # Execute in 30 minutes
messages = dq.poll(count=10)            # Get ready messages
```

## 可靠队列（Reliable Queue）

基于 List 的队列，使用 LMOVE + ack/nack 机制。

```python
from redis_kit import ReliableQueue

rq = ReliableQueue(conn.sync_client, "tasks")
rq.put({"task": "send_email", "to": "user@example.com"})

msg = rq.get(timeout=5)
try:
    process(msg.data)
    msg.ack()
except Exception:
    msg.nack()  # Return to queue
```

!!! tip "建议考虑 Redis Streams"
    对于新项目，建议使用 [Redis Streams](streams.md) 代替 ReliableQueue。Streams 提供消费者组、消息持久化和死信恢复等功能。
