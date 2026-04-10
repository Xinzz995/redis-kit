# Repository

Dataclass 实体存储，支持版本控制、软删除、审计和历史记录。

## 定义实体

```python
from dataclasses import dataclass
from redis_kit import BaseModel

@dataclass
class AppConfig(BaseModel):
    name: str = ""
    value: str = ""
    env: str = "production"
```

`BaseModel` 提供以下字段：`id`、`version`、`created_at`、`updated_at`、`deleted`、`deleted_at`。

## CRUD 操作

```python
from redis_kit import Repository

repo = Repository(conn.sync_client, AppConfig, prefix="config")

# Create — auto ID, version=1, created_at
config = repo.save(AppConfig(name="max_retries", value="3"))

# Read
found = repo.find(config.id)

# Update — auto version increment, updated_at
found.value = "5"
updated = repo.save(found)  # version 1 → 2

# List all
all_configs = repo.find_all()
```

## 乐观锁（Optimistic Locking）

```python
stale = repo.find(config.id)    # version=2
updated.value = "10"
repo.save(updated)               # version 2 → 3

stale.value = "20"
repo.save(stale)                  # OptimisticLockError! (expected 2, actual 3)
```

## 软删除

```python
repo.delete(config.id)                       # deleted=True, version+1
repo.find(config.id)                         # None
repo.find_including_deleted(config.id)       # Still accessible
restored = repo.restore(config.id)           # Recovered, version+1
repo.hard_delete(config.id)                  # Permanently removed
```

`delete()` 和 `restore()` 都使用乐观锁保证原子性，并自动递增 `version`、更新 `updated_at`。

## 版本历史

```python
history = repo.get_history(config.id)  # [v2, v1] — all previous versions
for version in history:
    print(f"v{version.version}: {version.value}")
```

## 异步用法

```python
from redis_kit import AsyncRepository

repo = AsyncRepository(conn.async_client, AppConfig, prefix="config")
config = await repo.save(AppConfig(name="key", value="val"))
found = await repo.find(config.id)
```
