# Serialization & Compression

## Serializers

| Serializer | Format | Use Case |
|------------|--------|----------|
| `JsonSerializer` | JSON | Default, human-readable, cross-language |
| `PickleSerializer` | Pickle | Python objects, trusted environments only |
| `MsgpackSerializer` | MessagePack | Compact binary, fast (requires `redis-py-kit[msgpack]`) |

```python
from redis_kit import Cache, JsonSerializer, PickleSerializer
from redis_kit.serializers import MsgpackSerializer

cache = Cache(conn.sync_client, serializer=MsgpackSerializer())
```

## Compressors

| Compressor | Dependencies | Characteristics |
|------------|-------------|----------------|
| `ZlibCompressor` | None (stdlib) | Good compression, moderate speed |
| `ZstdCompressor` | `redis-py-kit[zstd]` | Best compression ratio + speed |
| `Lz4Compressor` | `redis-py-kit[lz4]` | Fastest, moderate compression |

```python
from redis_kit import ZlibCompressor
from redis_kit.compressors import ZstdCompressor

cache = Cache(conn.sync_client, compressor=ZstdCompressor())
```

## Combining

```python
cache = Cache(
    conn.sync_client,
    prefix="myapp",
    serializer=MsgpackSerializer(),
    compressor=ZstdCompressor(),
)
```

Data pipeline: `value → serializer.dumps() → compressor.compress() → Redis`
