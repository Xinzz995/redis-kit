# Queue

PubSub, DelayQueue, and ReliableQueue.

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

## Delay Queue

Sorted Set-based queue with delayed execution.

```python
from redis_kit import DelayQueue

dq = DelayQueue(conn.sync_client, "order:timeout")
dq.put({"order_id": 123}, delay=1800)  # Execute in 30 minutes
messages = dq.poll(count=10)            # Get ready messages
```

## Reliable Queue

List-based queue with LMOVE + ack/nack.

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

!!! tip "Consider Redis Streams"
    For new projects, consider using [Redis Streams](streams.md) instead of ReliableQueue. Streams offer consumer groups, message persistence, and dead letter recovery.
