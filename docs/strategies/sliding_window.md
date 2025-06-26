# 🪟 Approximated Sliding Window Rate Limiting

## 1. What is Approximated Sliding Window Rate Limiting?

- **Concept:**  
  The Approximated Sliding Window algorithm provides smoother and more accurate rate limiting than a simple Fixed Window, while being more memory-efficient than a log-based sliding window.  
  It works by maintaining counters for the current and previous fixed windows. The effective count for the sliding window is calculated as a weighted sum of requests in both windows, based on how much of the previous window still "slides" into the current view.

- **Example:**  
  If you set a limit of 10 requests per minute, the limiter will estimate the number of requests in the last 60 seconds by combining the counts from the current and previous minute, weighted by how much of each window overlaps with the current time.

---

## 2. Usage

### Single Limiter Example

```python
from fastapicap import SlidingWindowRateLimiter
from fastapi import Depends

limiter = SlidingWindowRateLimiter(limit=10, minutes=1)

@app.get("/sliding", dependencies=[Depends(limiter)])
async def sliding_limited():
    return {"message": "You are within the sliding window rate limit!"}
```

---

### Multiple Limiters Example

```python
limiter_5s = SlidingWindowRateLimiter(limit=2, seconds=5)
limiter_1m = SlidingWindowRateLimiter(limit=10, minutes=1)

@app.get("/multi-sliding", dependencies=[Depends(limiter_5s), Depends(limiter_1m)])
async def multi_sliding_limited():
    return {"message": "You passed both sliding window rate limits!"}
```

---

## 3. Available Configuration Options

You can customize the Approximated Sliding Window limiter using the following parameters:

| Parameter   | Type      | Description                                                                                 | Default      |
|-------------|-----------|---------------------------------------------------------------------------------------------|--------------|
| `limit`     | `int`     | **Required.** Maximum number of requests allowed within the sliding window. Must be positive.| —            |
| `seconds`   | `int`     | Number of seconds in the window segment. Can be combined with minutes, hours, or days.      | `0`          |
| `minutes`   | `int`     | Number of minutes in the window segment.                                                    | `0`          |
| `hours`     | `int`     | Number of hours in the window segment.                                                      | `0`          |
| `days`      | `int`     | Number of days in the window segment.                                                       | `0`          |
| `key_func`  | `Callable`| Function to extract a unique key from the request.                                          | By default, uses client IP and path. |
| `on_limit`  | `Callable`| Function called when the rate limit is exceeded.                                            | By default, raises HTTP 429.         |
| `prefix`    | `str`     | Redis key prefix for all limiter keys.                                                      | `"cap"`      |

**Note:**  
- The window size is calculated as the sum of all time units provided (`seconds`, `minutes`, `hours`, `days`).
- At least one time unit must be positive, and `limit` must be positive.

**Example:**
```python
# 100 requests per hour, with a custom Redis key prefix
limiter = SlidingWindowRateLimiter(limit=100, hours=1, prefix="myapi")
```

---

## 4. How Approximated Sliding Window Works (with Example)

Suppose you set a limit of **10 requests per minute**.

- The limiter keeps two counters: one for the current minute and one for the previous minute.
- When a request arrives, it calculates how much of the previous window overlaps with the current 60-second period and combines the counts accordingly.
- This provides a smoother, more accurate rate limit than a simple fixed window.

**Visualization:**

| Time         | Requests in Previous Window | Requests in Current Window | Effective Count (Weighted) | Allowed? |
|--------------|----------------------------|---------------------------|----------------------------|----------|
| 12:00:30     | 4                          | 5                         | 4 * 0.5 + 5 = 7            | ✅       |
| 12:00:45     | 4                          | 7                         | 4 * 0.25 + 7 = 8           | ✅       |
| 12:00:59     | 4                          | 10                        | 4 * 0.01 + 10 ≈ 10.04      | ❌       |

- The "Effective Count" is the sum of the current window's count plus a weighted portion of the previous window's count, based on how much of the previous window still overlaps with the sliding window.

---

## 5. Notes, Pros & Cons

**Notes:**
- This strategy is more accurate and smoother than Fixed Window, but more memory-efficient than log-based sliding window.
- The `retry_after` value is an approximation.

**Pros:**
- Smoother rate limiting than Fixed Window.
- More memory-efficient than log-based sliding window.
- Good balance of accuracy and performance.

**Cons:**
- Not perfectly accurate (it's an approximation).
- Still susceptible to some boundary effects if not carefully tuned.

---

**Use Approximated Sliding Window when you want smoother, fairer rate limiting than Fixed Window, but don't need the full accuracy (or memory cost) of a log-based sliding window.**