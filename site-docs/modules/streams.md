# Redis Streams

Consumer group abstraction over Redis Streams.

## Producer

```python
from redis_kit import StreamProducer

producer = StreamProducer(conn.sync_client, stream="orders", maxlen=10000)
msg_id = producer.add({"order_id": "123", "status": "created"})
print(producer.len())
```

## Consumer — Auto ACK

```python
from redis_kit import StreamConsumer

consumer = StreamConsumer(
    conn.sync_client, stream="orders",
    group="processor", consumer_name="worker-1",
    auto_ack=True,
)
consumer.ensure_group()

for message in consumer.listen(count=10, block=5000):
    print(f"{message.id}: {message.data}")
    # Auto-ACK after each iteration
```

## Consumer — Manual ACK

```python
consumer = StreamConsumer(
    conn.sync_client, stream="orders",
    group="processor", consumer_name="worker-2",
    auto_ack=False,
)
consumer.ensure_group()

for message in consumer.listen(count=10, block=5000):
    try:
        process(message.data)
        message.ack()
    except Exception:
        pass  # Recover via claim_stale later
```

## Dead Letter Recovery

```python
stale = consumer.claim_stale(min_idle_ms=60000, count=10)
for msg in stale:
    handle_dead_letter(msg)
    msg.ack()
```

## Pending Messages

```python
pending = consumer.pending(count=10)
for entry in pending:
    print(f"{entry['id']} idle {entry['idle_ms']}ms, delivered {entry['delivery_count']} times")
```

## Async

```python
from redis_kit import AsyncStreamProducer, AsyncStreamConsumer

producer = AsyncStreamProducer(conn.async_client, stream="orders")
await producer.add({"order_id": "456"})

consumer = AsyncStreamConsumer(conn.async_client, stream="orders", group="g", consumer_name="w")
await consumer.ensure_group()

async for message in consumer.listen(count=10, block=5000):
    await process(message.data)
```
