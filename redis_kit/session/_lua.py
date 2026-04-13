"""Lua scripts for session operations."""

from __future__ import annotations

# Atomically update session fields only if the key already exists.
# Returns 1 on success, 0 if the session key does not exist.
# KEYS[1]: session key
# ARGV[1]: TTL in seconds
# ARGV[2..N]: interleaved field/value pairs to HSET
UPDATE_SCRIPT = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
if redis.call("exists", key) == 0 then
    return 0
end
local field_args = {}
for i = 2, #ARGV do
    table.insert(field_args, ARGV[i])
end
if #field_args > 0 then
    redis.call("hset", key, unpack(field_args))
end
redis.call("expire", key, ttl)
return 1
"""
