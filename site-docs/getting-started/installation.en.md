# Installation

## Basic Installation

```bash
pip install redis-py-kit
```

## Optional Dependencies

```bash
pip install redis-py-kit[msgpack]     # MessagePack serializer
pip install redis-py-kit[zstd]        # Zstandard compressor
pip install redis-py-kit[lz4]         # LZ4 compressor
pip install redis-py-kit[otel]        # OpenTelemetry integration
pip install redis-py-kit[all]         # All optional dependencies
```

## Requirements

- Python >= 3.11
- Redis >= 7.0
- redis-py >= 7.4.0
