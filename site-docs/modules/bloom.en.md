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

## Reset

```python
bf.reset()  # Delete the underlying Redis key, clearing the filter
```

## How It Works

- Uses double hashing technique (two MD5-based hashes to derive k offsets), faster than per-iteration SHA-256
- Pipeline-based SETBIT/GETBIT operations for improved performance
- `exists_many` uses a single pipeline batch check instead of N independent calls
- Automatically calculates optimal bit array size and hash function count based on `expected_items` and `false_positive_rate`
