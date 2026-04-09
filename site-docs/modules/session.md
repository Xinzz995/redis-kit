# Session 管理

基于 Redis Hash 的会话管理。

## 用法

```python
from redis_kit import SessionManager

sessions = SessionManager(conn.sync_client, prefix="session", ttl=1800)

# 创建
session_id = sessions.create({"user_id": 1, "role": "admin"})

# 读取
data = sessions.get(session_id)

# 更新（部分更新）
sessions.update(session_id, {"last_active": "2026-04-10"})

# 刷新 TTL
sessions.refresh(session_id)

# 删除
sessions.delete(session_id)

# 检查是否存在
sessions.exists(session_id)
```

## 自定义 ID 生成器

```python
sessions = SessionManager(
    conn.sync_client,
    prefix="session",
    ttl=1800,
    id_generator=lambda: my_custom_id(),
)
```
