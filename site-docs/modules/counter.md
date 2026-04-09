# 计数器与 ID 生成器

## 计数器

```python
from redis_kit import Counter

counter = Counter(conn.sync_client, prefix="myapp:counter")

counter.incr("page_views")
counter.incr("page_views", 5)
counter.decr("page_views")
value = counter.get("page_views")
counter.reset("page_views")
```

### 有界计数器（Bound Counter）

```python
pv = counter.bind("page_views")
pv.incr()
pv.get()
pv.reset()
```

## ID 生成器

```python
from redis_kit import IDGenerator

id_gen = IDGenerator(conn.sync_client, "order_id", prefix="ORD", padding=8)
new_id = id_gen.next_str()  # "ORD00000001"
new_id = id_gen.next()      # 2 (raw int)
```
