FIXED_WINDOW = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local expire_time = tonumber(ARGV[2])
local current = redis.call("INCR", key)

if current == 1 then
    redis.call("PEXPIRE", key, expire_time)
end

if current > limit then
    return redis.call("PTTL", key)
else
    return 0
end
"""

SLIDING_WINDOW = """-- KEYS[1]: The key for the current window
-- KEYS[2]: The key for the previous window
-- ARGV[1]: The current window timestamp (window start, in ms)
-- ARGV[2]: The window size in ms
-- ARGV[3]: The max allowed requests

local curr_key = KEYS[1]
local prev_key = KEYS[2]
local curr_window = tonumber(ARGV[1])
local window_size = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

-- Increment the current window counter
local curr_count = redis.call("INCR", curr_key)
if curr_count == 1 then
    redis.call("PEXPIRE", curr_key, window_size * 2)
end

-- Get the previous window count
local prev_count = tonumber(redis.call("GET", prev_key) or "0")

-- Calculate how far we are into the window
local now = redis.call("TIME")
local now_ms = now[1] * 1000 + math.floor(now[2] / 1000)
local elapsed = now_ms - curr_window
local weight = elapsed / window_size
if weight > 1 then weight = 1 end
if weight < 0 then weight = 0 end

-- Weighted sum
local total = curr_count + prev_count * (1 - weight)

if total > limit then
    -- Return time to next window
    return window_size - elapsed
else
    return 0
end
"""


TOKEN_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call("HMGET", key, "tokens", "last_refill")
local tokens = tonumber(bucket[1])
local last_refill = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    last_refill = now
end

local delta = math.max(0, now - last_refill)
local refill = 0
if refill_rate > 0 then
    refill = delta * refill_rate
end
tokens = math.min(capacity, tokens + refill)
last_refill = now

local allowed = 0
local retry_after = 0

if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
else
    allowed = 0
    retry_after = math.ceil((1 - tokens) / refill_rate)
end

-- Cap the expire time to Redis max
local expire_time = math.ceil(capacity / refill_rate)
if expire_time > 2147483647 then
    expire_time = 2147483647
end

redis.call("HMSET", key, "tokens", tokens, "last_refill", last_refill)
redis.call("PEXPIRE", key, expire_time)

return allowed == 1 and 0 or retry_after
"""

LEAKY_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local leak_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

local bucket = redis.call("HMGET", key, "level", "last_leak")
local level = tonumber(bucket[1]) or 0
local last_leak =tonumber(bucket[2]) or now

if level == nil then
    level = 0
    last_leak = now
end

local delta = math.max(0, now - last_leak)
local leaked = delta * leak_rate
level = math.max(0, level - leaked)
last_leak = now

local allowed = 0
local retry_after = 0

if (level + 1) <= capacity then
    allowed = 1
    level = level + 1
else
    allowed = 0
    retry_after = math.ceil((level - capacity + 1) / leak_rate)
    if retry_after < 1 then
        retry_after = 1
    end
end

local expire_time = math.ceil(capacity / leak_rate)
if expire_time > 2147483647 then
    expire_time = 2147483647
end

redis.call("HMSET", key, "level", level, "last_leak", last_leak)
redis.call("PEXPIRE", key, expire_time)

return allowed == 1 and 0 or retry_after
"""

GCRA_LUA = """
-- GCRA (Generic Cell Rate Algorithm) Lua script for Redis
-- KEYS[1] = key
-- ARGV[1] = burst (max tokens, integer)
-- ARGV[2] = rate (tokens per millisecond, float)
-- ARGV[3] = period (interval between tokens, in ms, float)
-- ARGV[4] = now (current time in ms, integer)

local key = KEYS[1]
local burst = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local period = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

-- Theoretical Arrival Time (TAT)
local tat = redis.call("GET", key)
if tat then
    tat = tonumber(tat)
else
    tat = now
end

-- The minimum spacing between requests
local increment = period

-- The earliest time this request can be allowed
local new_tat = math.max(tat, now) + increment

-- Allow if the request would not exceed the burst
if new_tat - now <= burst * period then
    -- Allowed: update TAT and set expiry
    redis.call("SET", key, new_tat, "PX", math.ceil(burst * period))
    return {1, 0}  -- allowed, no retry-after
else
    -- Not allowed: calculate retry-after
    local retry_after = new_tat - (burst * period) - now
    return {0, retry_after}
end
"""


SLIDING_LOG_LUA = """
-- KEYS[1]: Redis key for the sorted set
-- ARGV[1]: now (ms)
-- ARGV[2]: window (ms)
-- ARGV[3]: limit

local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local min_time = now - window

-- Remove old entries
redis.call('ZREMRANGEBYSCORE', key, 0, min_time)

-- Count current entries
local count = redis.call('ZCARD', key)

if count < limit then
    -- Add this request
    redis.call('ZADD', key, now, now)
    -- Set expiry to window size
    redis.call('PEXPIRE', key, window)
    return 1
else
    -- Get the earliest timestamp in the window
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')[2]
    local retry_after = window - (now - tonumber(oldest))
    return math.ceil(retry_after)
end
"""