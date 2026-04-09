# Session Manager

Redis Hash-based session management.

## Usage

```python
from redis_kit import SessionManager

sessions = SessionManager(conn.sync_client, prefix="session", ttl=1800)

# Create
session_id = sessions.create({"user_id": 1, "role": "admin"})

# Read
data = sessions.get(session_id)

# Update (partial)
sessions.update(session_id, {"last_active": "2026-04-10"})

# Refresh TTL
sessions.refresh(session_id)

# Delete
sessions.delete(session_id)

# Check existence
sessions.exists(session_id)
```

## Custom ID Generator

```python
sessions = SessionManager(
    conn.sync_client,
    prefix="session",
    ttl=1800,
    id_generator=lambda: my_custom_id(),
)
```
