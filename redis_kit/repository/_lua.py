"""Lua scripts for Repository optimistic locking."""

# Atomic version check + full hash write + history append
# KEYS[1] = entity key
# KEYS[2] = history key
# ARGV[1] = expected version (string)
# ARGV[2] = max_history (-1 means unlimited)
# ARGV[3], ARGV[4], ... = field1, value1, field2, value2, ... (flattened hash pairs)
# Returns: 0 on version conflict, 1 on success
OPTIMISTIC_LOCK_SET = """
local key = KEYS[1]
local history_key = KEYS[2]
local expected_version = ARGV[1]
local max_history = tonumber(ARGV[2])
local current = redis.call("hget", key, "version")
if current ~= false and current ~= expected_version then
    return 0
end
local old_data = redis.call("hgetall", key)
local field_args = {}
for i = 3, #ARGV, 2 do
    table.insert(field_args, ARGV[i])
    table.insert(field_args, ARGV[i + 1])
end
if #field_args > 0 then
    redis.call("hset", key, unpack(field_args))
end
if #old_data > 0 then
    local obj = {}
    for i = 1, #old_data, 2 do
        obj[old_data[i]] = old_data[i + 1]
    end
    redis.call("lpush", history_key, cjson.encode(obj))
    if max_history > 0 then
        redis.call("ltrim", history_key, 0, max_history - 1)
    end
end
return 1
"""

# Atomic version check + partial field update + history append
# KEYS[1] = entity key
# KEYS[2] = history key
# ARGV[1] = expected version (string)
# ARGV[2] = max_history (-1 means unlimited)
# ARGV[3], ARGV[4], ... = field1, value1, field2, value2, ... (flattened hash pairs)
# Returns: 0 on version conflict or key missing, 1 on success
OPTIMISTIC_LOCK_PARTIAL_SET = """
local key = KEYS[1]
local history_key = KEYS[2]
local expected_version = ARGV[1]
local max_history = tonumber(ARGV[2])
local current = redis.call("hget", key, "version")
if current == false or current ~= expected_version then
    return 0
end
local old_data = redis.call("hgetall", key)
local field_args = {}
for i = 3, #ARGV, 2 do
    table.insert(field_args, ARGV[i])
    table.insert(field_args, ARGV[i + 1])
end
if #field_args > 0 then
    redis.call("hset", key, unpack(field_args))
end
if #old_data > 0 then
    local obj = {}
    for i = 1, #old_data, 2 do
        obj[old_data[i]] = old_data[i + 1]
    end
    redis.call("lpush", history_key, cjson.encode(obj))
    if max_history > 0 then
        redis.call("ltrim", history_key, 0, max_history - 1)
    end
end
return 1
"""
