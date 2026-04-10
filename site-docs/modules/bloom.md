# 布隆过滤器

用于成员检测的概率型数据结构。

## 用法

```python
from redis_kit import BloomFilter

bf = BloomFilter(conn.sync_client, "emails", expected_items=100_000, false_positive_rate=0.01)

bf.add("alice@example.com")
bf.exists("alice@example.com")   # True
bf.exists("unknown@example.com") # False (probably)
```

## 批量操作

```python
bf.add_many(["a@x.com", "b@x.com", "c@x.com"])
results = bf.exists_many(["a@x.com", "d@x.com"])  # [True, False]
```

## 重置

```python
bf.reset()  # 删除底层 Redis key，清空过滤器
```

## 工作原理

- 使用 Double Hashing 技术（基于 MD5 的两个基础哈希派生 k 个偏移量），性能优于逐次 SHA-256
- 基于 Pipeline 的 SETBIT/GETBIT 操作以提升性能
- `exists_many` 使用单次 Pipeline 批量检查，而非 N 次独立调用
- 根据 `expected_items` 和 `false_positive_rate` 自动计算最优位数组大小和哈希函数数量
