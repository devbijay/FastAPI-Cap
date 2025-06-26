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


