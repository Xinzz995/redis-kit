# Repository

Dataclass entity storage with versioning, soft delete, audit, and history.

## Define Entity

```python
from dataclasses import dataclass
from redis_kit import BaseModel

@dataclass
class AppConfig(BaseModel):
    name: str = ""
    value: str = ""
    env: str = "production"
```

`BaseModel` provides: `id`, `version`, `created_at`, `updated_at`, `deleted`, `deleted_at`.

## CRUD

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

## Optimistic Locking

```python
stale = repo.find(config.id)    # version=2
updated.value = "10"
repo.save(updated)               # version 2 → 3

stale.value = "20"
repo.save(stale)                  # OptimisticLockError! (expected 2, actual 3)
```

## Soft Delete

```python
repo.delete(config.id)                       # deleted=True, deleted_at set
repo.find(config.id)                         # None
repo.find_including_deleted(config.id)       # Still accessible
repo.restore(config.id)                      # Recovered
repo.hard_delete(config.id)                  # Permanently removed
```

## Version History

```python
history = repo.get_history(config.id)  # [v2, v1] — all previous versions
for version in history:
    print(f"v{version.version}: {version.value}")
```

## Async

```python
from redis_kit import AsyncRepository

repo = AsyncRepository(conn.async_client, AppConfig, prefix="config")
config = await repo.save(AppConfig(name="key", value="val"))
found = await repo.find(config.id)
```
