"""Lua scripts for Repository optimistic locking."""

# Atomic version check + full hash write + return old data for history
# KEYS[1] = entity key
# ARGV[1] = expected version (string)
# ARGV[2], ARGV[3], ... = field1, value1, field2, value2, ... (flattened hash pairs)
# Returns: 0 on version conflict, or the old hash data as a flat list [field1, val1, ...]
OPTIMISTIC_LOCK_SET = """
local key = KEYS[1]
local expected_version = ARGV[1]
local current = redis.call("hget", key, "version")
if current ~= false and current ~= expected_version then
    return 0
end
local old_data = redis.call("hgetall", key)
local field_args = {}
for i = 2, #ARGV, 2 do
    table.insert(field_args, ARGV[i])
    table.insert(field_args, ARGV[i + 1])
end
if #field_args > 0 then
    redis.call("hset", key, unpack(field_args))
end
return old_data
"""

# Atomic version check + partial field update (for soft delete)
# KEYS[1] = entity key
# ARGV[1] = expected version (string)
# ARGV[2], ARGV[3], ... = field1, value1, field2, value2, ... (flattened hash pairs)
OPTIMISTIC_LOCK_PARTIAL_SET = """
local key = KEYS[1]
local expected_version = ARGV[1]
local current = redis.call("hget", key, "version")
if current == false or current ~= expected_version then
    return 0
end
local field_args = {}
for i = 2, #ARGV, 2 do
    table.insert(field_args, ARGV[i])
    table.insert(field_args, ARGV[i + 1])
end
if #field_args > 0 then
    redis.call("hset", key, unpack(field_args))
end
return 1
"""
