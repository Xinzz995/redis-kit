# 安装

## 基本安装

```bash
pip install redis-py-kit
```

## 可选依赖

```bash
pip install redis-py-kit[msgpack]     # MessagePack serializer
pip install redis-py-kit[zstd]        # Zstandard compressor
pip install redis-py-kit[lz4]         # LZ4 compressor
pip install redis-py-kit[otel]        # OpenTelemetry integration
pip install redis-py-kit[all]         # All optional dependencies
```

## 环境要求

- Python >= 3.11
- Redis >= 7.0
- redis-py >= 7.4.0
