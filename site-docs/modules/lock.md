# 分布式锁

基于 Lua 脚本原子操作的 Redis 分布式锁。

## 基本锁

```python
from redis_kit import Lock

lock = Lock(conn.sync_client, prefix="myapp:lock")

with lock("resource-1", timeout=10):
    do_critical_work()
```

## 可重入锁

```python
with lock("resource", timeout=10, reentrant=True):
    with lock("resource", timeout=10, reentrant=True):
        ...  # No deadlock
```

## 读写锁

```python
with lock.read("resource"):     # Multiple readers allowed
    data = read_shared_state()

with lock.write("resource"):    # Exclusive writer
    update_shared_state()
```

## 看门狗自动续期

```python
with lock("resource", timeout=30, auto_renew=True):
    do_long_running_work()  # Lock auto-extends every 10s
```

## 集群模式

```python
lock = Lock(conn.sync_client, prefix="myapp:lock", is_cluster=conn.is_cluster)
# Keys automatically wrapped in {hash_tag} for Lua script slot safety
```

## 异常安全

锁的上下文管理器保证不会遮蔽你代码中抛出的原始异常。如果锁释放失败（例如锁已超时过期），而你的代码同时抛出了异常，原始异常将正常传播，释放失败仅记录警告日志。

```python
try:
    with lock("resource", timeout=5):
        raise ValueError("业务逻辑错误")
except ValueError:
    # ValueError 会正常传播，即使锁释放失败也不会被 LockReleaseError 遮蔽
    pass
```

在正常退出（无异常）时，如果锁释放失败则会抛出 `LockReleaseError`。

## 异步用法

```python
from redis_kit import AsyncLock

async with AsyncLock(conn.async_client, prefix="lock")("resource", timeout=10):
    await do_async_work()
```
