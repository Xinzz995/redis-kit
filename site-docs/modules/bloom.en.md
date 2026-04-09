# Bloom Filter

A probabilistic data structure for membership testing.

## Usage

```python
from redis_kit import BloomFilter

bf = BloomFilter(conn.sync_client, "emails", expected_items=100_000, false_positive_rate=0.01)

bf.add("alice@example.com")
bf.exists("alice@example.com")   # True
bf.exists("unknown@example.com") # False (probably)
```

## Batch Operations

```python
bf.add_many(["a@x.com", "b@x.com", "c@x.com"])
results = bf.exists_many(["a@x.com", "d@x.com"])  # [True, False]
```

## How It Works

- Uses multiple SHA-256 hash functions to map elements to positions in a bit array
- Pipeline-based SETBIT/GETBIT operations for improved performance
- Automatically calculates optimal bit array size and hash function count based on `expected_items` and `false_positive_rate`
