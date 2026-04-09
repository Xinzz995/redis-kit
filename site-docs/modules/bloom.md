# Bloom Filter

Probabilistic data structure for membership testing.

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

- Multiple SHA-256 hash functions map items to bit positions
- Pipeline-based SETBIT/GETBIT for performance
- Optimal bit array size and hash count auto-calculated from `expected_items` and `false_positive_rate`
