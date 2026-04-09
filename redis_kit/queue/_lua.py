"""Lua scripts for queue operations."""

from __future__ import annotations

# Atomic nack: remove from processing + re-enqueue
# KEYS[1] = processing list, KEYS[2] = queue list
# ARGV[1] = raw message to remove, ARGV[2] = new payload to re-enqueue
NACK_SCRIPT = """
redis.call("lrem", KEYS[1], 1, ARGV[1])
redis.call("lpush", KEYS[2], ARGV[2])
return 1
"""
