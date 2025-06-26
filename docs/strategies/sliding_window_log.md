# 🪟 Sliding Window (Log-based) Rate Limiting

## 1. What is Sliding Window (Log-based) Rate Limiting?

- **Concept:**  
  The Sliding Window (Log-based) algorithm is the most accurate form of sliding window rate limiting. It stores a timestamp for every request in a Redis sorted set. When a new request arrives, it removes all timestamps outside the current window, counts the remaining ones, and allows or blocks the request based on the configured limit. This ensures the window truly "slides" over time, providing precise and fair rate limiting.

- **Example:**  
  If you set a limit of 10 requests per minute, the limiter will only allow 10 requests in any rolling 60-second period, regardless of when those requests occur.

---

## 2. Usage

### Single Limiter Example

```python
from fastapicap import SlidingWindowLogRateLimiter
from fastapi import Depends

limiter = SlidingWindowLogRateLimiter(limit=10, window_minutes=1)

@app.get("/sliding-log", dependencies=[Depends(limiter)])
async def sliding_log_limited():
    return {"message": "You are within the log-based sliding window rate limit!"}
```

---

### Multiple Limiters Example

```python
limiter_10s = SlidingWindowLogRateLimiter(limit=3, window_seconds=10)
limiter_1m = SlidingWindowLogRateLimiter(limit=10, window_minutes=1)

@app.get("/multi-sliding-log", dependencies=[Depends(limiter_10s), Depends(limiter_1m)])
async def multi_sliding_log_limited():
    return {"message": "You passed both log-based sliding window rate limits!"}
```

---

## 3. Available Configuration Options

You can customize the Sliding Window (Log-based) limiter using the following parameters:

| Parameter         | Type      | Description                                                                                 | Default      |
|-------------------|-----------|---------------------------------------------------------------------------------------------|--------------|
| `limit`           | `int`     | **Required.** Maximum number of requests allowed within the sliding window. Must be positive.| —            |
| `window_seconds`  | `int`     | Number of seconds in the sliding window. Can be combined with minutes, hours, or days.      | `0`          |
| `window_minutes`  | `int`     | Number of minutes in the sliding window.                                                    | `0`          |
| `window_hours`    | `int`     | Number of hours in the sliding window.                                                      | `0`          |
| `window_days`     | `int`     | Number of days in the sliding window.                                                       | `0`          |
| `key_func`        | `Callable`| Function to extract a unique key from the request.                                          | By default, uses client IP and path. |
| `on_limit`        | `Callable`| Function called when the rate limit is exceeded.                                            | By default, raises HTTP 429.         |
| `prefix`          | `str`     | Redis key prefix for all limiter keys.                                                      | `"cap"`      |

**Note:**  
- The window size is calculated as the sum of all time units provided (`window_seconds`, `window_minutes`, `window_hours`, `window_days`).
- At least one time unit must be positive, and `limit` must be positive.

**Example:**
```python
# 100 requests per hour, with a custom Redis key prefix
limiter = SlidingWindowLogRateLimiter(limit=100, window_hours=1, prefix="myapi")
```

---

## 4. How Sliding Window (Log-based) Works (with Example)

Suppose you set a limit of **10 requests per minute**.

- Every request's timestamp is stored in a Redis sorted set.
- When a new request arrives:
  - All timestamps older than 60 seconds are removed.
  - The number of remaining timestamps is counted.
  - If the count is below 10, the request is allowed and its timestamp is added.
  - If the count is 10 or more, the request is blocked.

**Visualization:**

| Time         | Timestamps in Window (last 60s) | Allowed? | Reason                |
|--------------|----------------------------------|----------|-----------------------|
| 12:00:01     | 1                                | ✅       | Within limit          |
| 12:00:10     | 2                                | ✅       | Within limit          |
| 12:00:20     | 3                                | ✅       | Within limit          |
| ...          | ...                              | ...      | ...                   |
| 12:00:59     | 10                               | ✅       | At limit              |
| 12:01:00     | 10 (oldest at 12:00:01 removed)  | ✅       | Oldest expired        |
| 12:01:01     | 10 (oldest at 12:00:10 removed)  | ✅       | Oldest expired        |
| 12:01:02     | 10 (no expired, new request)     | ❌       | Limit exceeded        |

- The window "slides" with every request, always considering only the last 60 seconds.

---

## 5. Notes, Pros & Cons

**Notes:**

- This strategy uses Redis sorted sets for each client/key, which can increase memory usage for high-traffic endpoints.
- The `retry_after` value is precise, based on the timestamp of the oldest request in the window.

**Pros:**

- Most accurate and fair rate limiting.
- Eliminates burst issues at window boundaries.
- Ensures consistent rate over any time slice within the window.

**Cons:**

- Higher memory usage for high request volumes (stores a timestamp for every request in the window).
- Slightly more Redis operations per request compared to other strategies.

---

**Use Sliding Window (Log-based) when you need the highest accuracy and fairness in rate limiting, and can afford the extra memory usage.**