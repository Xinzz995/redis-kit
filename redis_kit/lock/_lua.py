"""Lua scripts for atomic lock operations."""

# Release lock only if caller owns it
RELEASE_LOCK = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

# Reentrant lock: increment count if same owner, else fail
REENTRANT_ACQUIRE = """
local key = KEYS[1]
local owner = ARGV[1]
local timeout = tonumber(ARGV[2])
local current = redis.call("hget", key, "owner")
if current == false then
    redis.call("hset", key, "owner", owner)
    redis.call("hset", key, "count", 1)
    redis.call("expire", key, timeout)
    return 1
elseif current == owner then
    redis.call("hincrby", key, "count", 1)
    redis.call("expire", key, timeout)
    return 1
else
    return 0
end
"""

# Reentrant release: decrement count, delete if zero
REENTRANT_RELEASE = """
local key = KEYS[1]
local owner = ARGV[1]
local current = redis.call("hget", key, "owner")
if current == owner then
    local count = redis.call("hincrby", key, "count", -1)
    if count <= 0 then
        redis.call("del", key)
    end
    return 1
else
    return 0
end
"""

# Watchdog: extend TTL if owner matches
EXTEND_LOCK = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
else
    return 0
end
"""

EXTEND_REENTRANT_LOCK = """
local current = redis.call("hget", KEYS[1], "owner")
if current == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
else
    return 0
end
"""
