# 🪟 Fixed Window Rate Limiting

## 1. What is Fixed Window Rate Limiting?

- **Concept:**  
  Time is split into fixed intervals (e.g., 1 minute). Each client can make up to a set number of requests per interval. When the interval resets, so does the counter.

- **Example:**  
  If the limit is 5 requests per minute, a client can make 5 requests between 12:00:00 and 12:00:59. At 12:01:00, the counter resets.

---

## 2. Usage

### Single Limiter Example

```python
from fastapicap import RateLimiter
from fastapi import Depends

limiter = RateLimiter(limit=5, minutes=1)

@app.get("/limited", dependencies=[Depends(limiter)])
async def limited_endpoint():
    return {"message": "You are within the rate limit!"}
```

---

### Multiple Limiters Example

```python
limiter_1s = RateLimiter(limit=1, seconds=1)
limiter_30m = RateLimiter(limit=30, minutes=1)

@app.get("/strict", dependencies=[Depends(limiter_1s), Depends(limiter_30m)])
async def strict_endpoint():
    return {"message": "You passed both rate limits!"}
```

---

## 3. Available Configuration Options

You can customize the Fixed Window limiter using the following parameters:

| Parameter   | Type      | Description                                                                                 | Default      |
|-------------|-----------|---------------------------------------------------------------------------------------------|--------------|
| `limit`     | `int`     | **Required.** Maximum number of requests allowed per window. Must be positive.              | —            |
| `seconds`   | `int`     | Number of seconds in the window. Can be combined with minutes, hours, or days.              | `0`          |
| `minutes`   | `int`     | Number of minutes in the window.                                                            | `0`          |
| `hours`     | `int`     | Number of hours in the window.                                                              | `0`          |
| `days`      | `int`     | Number of days in the window.                                                               | `0`          |
| `key_func`  | `Callable`| Function to extract a unique key from the request (e.g., by IP, user ID, etc.).             | By default, uses client IP and path. |
| `on_limit`  | `Callable`| Function called when the rate limit is exceeded.                                            | By default, raises HTTP 429.         |
| `prefix`    | `str`     | Redis key prefix for all limiter keys.                                                      | `"cap"`      |

**Note:**  
- The window size is calculated as the sum of all time units provided (`seconds`, `minutes`, `hours`, `days`).
- At least one time unit must be positive, and `limit` must be positive.

**Example:**
```python
# 100 requests per hour, with a custom Redis key prefix
limiter = RateLimiter(limit=100, hours=1, prefix="myapi")
```

---

## 4. How Fixed Window Works

Suppose you set a limit of **5 requests per minute**:

- At 12:00:00, the window starts.
- The client makes 5 requests between 12:00:00 and 12:00:59 — all are allowed.
- A 6th request at 12:00:30 is **blocked** with a 429 error.
- At 12:01:00, the window resets. The client can make 5 more requests.

**Visualization:**

| Time         | Request # | Allowed? | Reason                |
|--------------|-----------|----------|-----------------------|
| 12:00:01     | 1         | ✅       | Within limit          |
| 12:00:10     | 2         | ✅       | Within limit          |
| 12:00:20     | 3         | ✅       | Within limit          |
| 12:00:30     | 4         | ✅       | Within limit          |
| 12:00:50     | 5         | ✅       | Within limit          |
| 12:00:55     | 6         | ❌       | Limit exceeded        |
| 12:01:01     | 7         | ✅       | New window, allowed   |

---

## 5. Notes, Pros & Cons

**Pros:**
- Simple to understand and implement.
- Low memory usage.
- Good for aggressive, clear-cut limits.

**Cons:**
- Can allow bursts at window boundaries (e.g., 5 requests at 12:00:59 and 5 more at 12:01:00).

---

**Use Fixed Window for simple, aggressive limits where bursts at window boundaries are acceptable.**