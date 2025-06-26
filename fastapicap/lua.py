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
