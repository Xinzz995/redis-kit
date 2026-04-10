# Distributed Lock

Redis distributed lock based on Lua script atomic operations.

## Basic Lock

```python
from redis_kit import Lock

lock = Lock(conn.sync_client, prefix="myapp:lock")

with lock("resource-1", timeout=10):
    do_critical_work()
```

## Reentrant Lock

```python
with lock("resource", timeout=10, reentrant=True):
    with lock("resource", timeout=10, reentrant=True):
        ...  # No deadlock
```

## Read-Write Lock

```python
with lock.read("resource"):     # Multiple readers allowed
    data = read_shared_state()

with lock.write("resource"):    # Exclusive writer
    update_shared_state()
```

## Watchdog Auto-Renewal

```python
with lock("resource", timeout=30, auto_renew=True):
    do_long_running_work()  # Lock auto-extends every 10s
```

## Cluster Mode

```python
lock = Lock(conn.sync_client, prefix="myapp:lock", is_cluster=conn.is_cluster)
# Keys automatically wrapped in {hash_tag} for Lua script slot safety
```

## Exception Safety

All lock context managers (`__call__`, `read()`, `write()`) guarantee they will never mask your original exception. If the lock release fails (e.g., lock TTL expired) while your code also raised an exception, the original exception propagates normally, and the release failure is logged as a warning.

```python
try:
    with lock("resource", timeout=5):
        raise ValueError("business logic error")
except ValueError:
    # ValueError propagates normally, even if lock release fails
    pass

# Read-write locks are also exception-safe
try:
    with lock.write("resource", timeout=5):
        raise ValueError("write operation error")
except ValueError:
    pass  # Original exception propagates normally
```

On clean exit (no exception), a failed release will raise `LockReleaseError` as expected.

!!! note "Reader-preference policy"
    The read-write lock uses a reader-preference strategy. Under high contention, continuous readers may starve writers. Keep this in mind for write-heavy workloads.

## Async Usage

```python
from redis_kit import AsyncLock

async with AsyncLock(conn.async_client, prefix="lock")("resource", timeout=10):
    await do_async_work()
```
