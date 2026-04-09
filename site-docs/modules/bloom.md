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

## 工作原理

- 使用多个 SHA-256 哈希函数将元素映射到位数组中的位置
- 基于 Pipeline 的 SETBIT/GETBIT 操作以提升性能
- 根据 `expected_items` 和 `false_positive_rate` 自动计算最优位数组大小和哈希函数数量
