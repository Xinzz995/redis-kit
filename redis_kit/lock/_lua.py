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

# Read lock: atomically increment readers and set expire
READ_ACQUIRE = """
local key = KEYS[1]
local timeout = tonumber(ARGV[1])
local writer = redis.call("get", key .. ":writer")
if writer then
    return 0
end
redis.call("hincrby", key, "readers", 1)
redis.call("expire", key, timeout)
return 1
"""

READ_RELEASE = """
local key = KEYS[1]
local count = redis.call("hincrby", key, "readers", -1)
if count <= 0 then
    redis.call("hdel", key, "readers")
end
return 1
"""

WRITE_ACQUIRE = """
local key = KEYS[1]
local owner = ARGV[1]
local timeout = tonumber(ARGV[2])
local writer = redis.call("get", key .. ":writer")
if writer then
    return 0
end
local readers = redis.call("hget", key, "readers")
if readers and tonumber(readers) > 0 then
    return 0
end
redis.call("set", key .. ":writer", owner, "EX", timeout, "NX")
return 1
"""
