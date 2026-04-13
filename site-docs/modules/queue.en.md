# Message Queue

Includes PubSub, DelayQueue, and ReliableQueue.

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

### Graceful Shutdown

`listen()` supports graceful shutdown and configurable poll timeout:

```python
import threading

pubsub = PubSub(conn.sync_client, prefix="myapp")
pubsub.subscribe("events", handler)

# Run in a background thread
thread = threading.Thread(target=pubsub.listen, kwargs={"timeout": 1.0})
thread.start()

# When you need to stop
pubsub.stop()   # Signal listen() to exit after current poll cycle
thread.join()

# Or close directly (stops listening and releases resources)
pubsub.close()
```

### Async Handlers

`AsyncPubSub` supports both sync and async handlers. Async handlers are automatically awaited:

```python
from redis_kit import AsyncPubSub

async_pubsub = AsyncPubSub(conn.async_client, prefix="myapp")

async def async_handler(message):
    await save_to_db(message)

await async_pubsub.subscribe("events", async_handler)
await async_pubsub.listen(timeout=1.0)
```

### Pattern Subscription

```python
pubsub.psubscribe("events.*", handler)  # Matches events.order, events.user, etc.
```

## Delay Queue

Delayed execution queue based on Sorted Set.

```python
from redis_kit import DelayQueue

dq = DelayQueue(conn.sync_client, "order:timeout")
dq.put({"order_id": 123}, delay=1800)  # Execute in 30 minutes
messages = dq.poll(count=10)            # Get ready messages
```

## Reliable Queue

List-based queue with LMOVE + ack/nack mechanism.

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

# Recover messages from crashed consumers
recovered = rq.recover_stale(max_items=100)
```

!!! tip "Consider Redis Streams"
    For new projects, consider using [Redis Streams](streams.md) instead of ReliableQueue. Streams provide consumer groups, message persistence, and dead-letter recovery.
