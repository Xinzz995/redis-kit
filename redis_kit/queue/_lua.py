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

# Atomic put with server-side time
# KEYS[1] = sorted set key
# ARGV[1] = delay in seconds, ARGV[2] = payload
PUT_SCRIPT = """
local time = redis.call("TIME")
local now = tonumber(time[1]) + tonumber(time[2]) / 1000000
local score = now + tonumber(ARGV[1])
redis.call("zadd", KEYS[1], score, ARGV[2])
return 1
"""

# Atomic poll with server-side time: get and remove due items
# KEYS[1] = sorted set key
# ARGV[1] = max count
POLL_SCRIPT = """
local key = KEYS[1]
local count = tonumber(ARGV[1])
local time = redis.call("TIME")
local now = tonumber(time[1]) + tonumber(time[2]) / 1000000
local results = redis.call("zrangebyscore", key, "-inf", now, "LIMIT", 0, count)
for i, v in ipairs(results) do
    redis.call("zrem", key, v)
end
return results
"""
