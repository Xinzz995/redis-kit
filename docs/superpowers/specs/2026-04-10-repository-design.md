# redis-py-kit Repository 模式设计

## 1. 概述

为 redis-py-kit 添加 Repository 模式，提供结构化实体的 CRUD + 版本控制 + 软删除 + 审计日志 + 版本历史回溯。基于 dataclass 定义实体，自动映射到 Redis Hash。

### 设计参考

| 来源 | 借鉴内容 |
|------|---------|
| Spring Data Redis | `@Version` 乐观锁（Lua 原子检查）、`@CreatedDate`/`@LastModifiedDate` 审计 |
| redis-om-python | Pydantic 模型映射 Redis Hash、自动 PK 生成 |
| walrus | Hash 存储 + Set 索引 |

## 2. 文件结构

```
redis_kit/repository/
├── __init__.py            # 导出
├── model.py               # BaseModel 基类
├── _lua.py                # 乐观锁 Lua 脚本
├── repository.py          # Repository (sync)
└── async_repository.py    # AsyncRepository
```

## 3. BaseModel

```python
@dataclass
class BaseModel:
    id: str = ""
    version: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted: bool = False
    deleted_at: datetime | None = None
```

用户继承定义实体，业务字段必须有默认值：

```python
@dataclass
class AppConfig(BaseModel):
    name: str = ""
    value: str = ""
    env: str = "production"
```

## 4. Repository API

```python
class Repository[T: BaseModel]:
    def __init__(self, client, model_class: type[T], prefix: str = "") -> None: ...

    def save(self, entity: T) -> T
    def find(self, entity_id: str) -> T | None
    def find_including_deleted(self, entity_id: str) -> T | None
    def delete(self, entity_id: str) -> None
    def hard_delete(self, entity_id: str) -> None
    def restore(self, entity_id: str) -> T
    def find_all(self) -> list[T]
    def get_history(self, entity_id: str) -> list[T]
```

### save() 行为

- **新建**（id 为空）：自动生成 uuid、设 version=1、填充 created_at
- **更新**（id 已存在）：乐观锁检查 version → 递增 version → 填充 updated_at → 旧版本存入 history list
- **乐观锁冲突**：抛 OptimisticLockError

### delete() / restore() 行为

- `delete()`：设 deleted=True + deleted_at，不从 Redis 删除
- `restore()`：设 deleted=False + 清除 deleted_at
- `hard_delete()`：真正从 Redis 移除（Hash + history list + 索引）
- `find()` 默认跳过 deleted=True 的实体

## 5. 存储结构

| Redis Key | 类型 | 用途 |
|-----------|------|------|
| `{prefix}:{id}` | Hash | 当前版本实体数据 |
| `{prefix}:{id}:history` | List | 历史版本（JSON 序列化） |
| `{prefix}:_index` | Set | 所有实体 ID 索引 |

## 6. 乐观锁 Lua 脚本

```lua
local key = KEYS[1]
local expected_version = ARGV[1]
local current = redis.call("hget", key, "version")
if current ~= false and current ~= expected_version then
    return 0  -- 版本冲突
end
return 1  -- 允许更新
```

## 7. 序列化

- 实体字段通过 `dataclasses.fields()` 提取
- 写入 Hash 时所有值转为字符串
- 读取时按字段类型注解还原（str、int、float、bool、datetime）
- history list 用 JSON 序列化完整快照

## 8. 异常

```python
class RepositoryError(RedisKitError): ...
class EntityNotFoundError(RepositoryError): ...
class OptimisticLockError(RepositoryError): ...
```

## 9. 公共 API 导出

```python
from redis_kit import Repository, AsyncRepository, BaseModel
from redis_kit.exceptions import RepositoryError, EntityNotFoundError, OptimisticLockError
```

## 10. 影响面

| 文件 | 改动 |
|------|------|
| `redis_kit/repository/` | 新模块 |
| `redis_kit/exceptions.py` | 新增 3 个异常 |
| `redis_kit/__init__.py` | 导出新类型 |
| 其他模块 | 零改动 |
