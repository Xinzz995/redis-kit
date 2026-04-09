"""Lua scripts for rate limiter algorithms."""

TOKEN_BUCKET_SCRIPT = """
local tokens_key = KEYS[1]
local ts_key = KEYS[2]
local rate = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local last_tokens = tonumber(redis.call("get", tokens_key))
if last_tokens == nil then
    last_tokens = capacity
end

local last_ts = tonumber(redis.call("get", ts_key))
if last_ts == nil then
    last_ts = now
end

local delta = math.max(0, now - last_ts)
local filled = math.min(capacity, last_tokens + delta * rate)
local allowed = filled >= cost
local new_tokens = filled
local retry_after = 0
local reset_at = now + (capacity - filled) / rate

if allowed then
    new_tokens = filled - cost
else
    retry_after = (cost - filled) / rate
end

redis.call("setex", tokens_key, ttl, new_tokens)
redis.call("setex", ts_key, ttl, now)

local ra = math.floor(retry_after * 1000)
local rst = math.floor(reset_at * 1000)
return {allowed and 1 or 0, capacity, math.floor(new_tokens), ra, rst}
"""

SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_ms = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])

redis.call("zremrangebyscore", key, "-inf", now - window_ms)

local count = redis.call("zcard", key)

local allowed = count < limit
local remaining = math.max(0, limit - count - 1)
local retry_after = 0
local reset_at = now + window_ms

if allowed then
    redis.call("zadd", key, now, member)
    redis.call("pexpire", key, ttl)
else
    remaining = 0
    local oldest = redis.call("zrange", key, 0, 0, "WITHSCORES")
    if #oldest > 0 then
        retry_after = tonumber(oldest[2]) + window_ms - now
        reset_at = tonumber(oldest[2]) + window_ms
    end
end

return {allowed and 1 or 0, limit, remaining, math.floor(retry_after), math.floor(reset_at)}
"""
