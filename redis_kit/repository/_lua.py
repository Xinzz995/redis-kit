"""Lua scripts for Repository optimistic locking."""

# Check version matches before allowing update
OPTIMISTIC_LOCK_CHECK = """
local key = KEYS[1]
local expected_version = ARGV[1]
local current = redis.call("hget", key, "version")
if current ~= false and current ~= expected_version then
    return 0
end
return 1
"""
