# 序列化与压缩

## 序列化器

| 序列化器 | 格式 | 适用场景 |
|----------|------|----------|
| `JsonSerializer` | JSON | 默认，可读性好，跨语言兼容 |
| `PickleSerializer` | Pickle | Python 对象，仅限可信环境 |
| `MsgpackSerializer` | MessagePack | 紧凑二进制，速度快（需要 `redis-py-kit[msgpack]`） |

```python
from redis_kit import Cache, JsonSerializer, PickleSerializer
from redis_kit.serializers import MsgpackSerializer

cache = Cache(conn.sync_client, serializer=MsgpackSerializer())
```

## 压缩器

| 压缩器 | 依赖 | 特点 |
|--------|------|------|
| `ZlibCompressor` | 无（标准库） | 压缩率好，速度适中 |
| `ZstdCompressor` | `redis-py-kit[zstd]` | 最佳压缩率 + 速度 |
| `Lz4Compressor` | `redis-py-kit[lz4]` | 速度最快，压缩率适中 |

```python
from redis_kit import ZlibCompressor
from redis_kit.compressors import ZstdCompressor

cache = Cache(conn.sync_client, compressor=ZstdCompressor())
```

## 组合使用

```python
cache = Cache(
    conn.sync_client,
    prefix="myapp",
    serializer=MsgpackSerializer(),
    compressor=ZstdCompressor(),
)
```

数据流水线：`value → serializer.dumps() → compressor.compress() → Redis`
