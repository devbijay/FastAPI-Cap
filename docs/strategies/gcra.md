# ⚡ GCRA (Generic Cell Rate Algorithm) Rate Limiting

## 1. What is GCRA Rate Limiting?

- **Concept:**  
  The Generic Cell Rate Algorithm (GCRA) is a precise, burstable rate limiting algorithm. It tracks a "Theoretical Arrival Time" (TAT) for each client and allows requests as long as they do not arrive "too early" according to the configured rate. GCRA is similar to the Token Bucket algorithm but is often more precise for burst control and fairness.

- **Real-world usage:**  
  GCRA is widely used in telecommunications (ATM networks), API gateways, and distributed systems where both fairness and precise burst control are required.

---

## 2. Usage

### Single Limiter Example

```python
from fastapicap import GCRARateLimiter
from fastapi import Depends

# Allow a burst of 5 requests, then 2 requests per second
limiter = GCRARateLimiter(burst=5, tokens_per_second=2)

@app.get("/gcra", dependencies=[Depends(limiter)])
async def gcra_limited():
    return {"message": "You are within the GCRA rate limit!"}
```

---

### Multiple Limiters Example

```python
limiter_short = GCRARateLimiter(burst=2, tokens_per_second=1)
limiter_long = GCRARateLimiter(burst=10, tokens_per_minute=30)

@app.get("/multi-gcra", dependencies=[Depends(limiter_short), Depends(limiter_long)])
async def multi_gcra_limited():
    return {"message": "You passed both GCRA rate limits!"}
```

---

## 3. Available Configuration Options

You can customize the GCRA limiter using the following parameters:

| Parameter            | Type      | Description                                                                                 | Default      |
|----------------------|-----------|---------------------------------------------------------------------------------------------|--------------|
| `burst`              | `int`     | **Required.** Maximum number of requests that can be served instantly (burst capacity).      | —            |
| `tokens_per_second`  | `float`   | Number of tokens allowed per second (steady rate).                                          | `0`          |
| `tokens_per_minute`  | `float`   | Number of tokens allowed per minute.                                                        | `0`          |
| `tokens_per_hour`    | `float`   | Number of tokens allowed per hour.                                                          | `0`          |
| `tokens_per_day`     | `float`   | Number of tokens allowed per day.                                                           | `0`          |
| `key_func`           | `Callable`| Function to extract a unique key from the request.                                          | By default, uses client IP and path. |
| `on_limit`           | `Callable`| Function called when the rate limit is exceeded.                                            | By default, raises HTTP 429.         |
| `prefix`             | `str`     | Redis key prefix for all limiter keys.                                                      | `"cap"`      |

**Note:**  
- The total steady rate is the sum of all `tokens_per_*` arguments, converted to tokens per second.
- At least one steady rate must be positive, and `burst` must be positive.

**Example:**
```python
# Burst of 20, steady rate of 100 per hour, with a custom prefix
limiter = GCRARateLimiter(burst=20, tokens_per_hour=100, prefix="myapi")
```

---

## 4. How GCRA Works (with Example)

Suppose you set a **burst of 5** and a **steady rate of 2 requests per second**.

- If the client has been idle, they can make up to 5 requests instantly (burst).
- After the burst, requests are only allowed at the steady rate (2 per second).
- If requests arrive too quickly, the limiter calculates how long the client must wait before the next request is allowed (`retry_after`).

**Visualization:**

| Time         | Burst Left | Allowed? | Reason                | Retry-After (s) |
|--------------|------------|----------|-----------------------|-----------------|
| 12:00:00.000 | 5          | ✅       | Burst                 | 0               |
| 12:00:00.100 | 4          | ✅       | Burst                 | 0               |
| 12:00:00.200 | 3          | ✅       | Burst                 | 0               |
| 12:00:00.300 | 2          | ✅       | Burst                 | 0               |
| 12:00:00.400 | 1          | ✅       | Burst                 | 0               |
| 12:00:00.500 | 0          | ❌       | Rate exceeded         | 0.5             |
| 12:00:01.000 | 1          | ✅       | Steady rate resumes   | 0               |

- After the burst is used, requests are only allowed at the configured steady rate.

---

## 5. Notes, Pros & Cons

**Notes:**

- GCRA is highly accurate and fair, making it ideal for per-user or per-client rate limiting.
- The `retry_after` value is precise, based on the theoretical arrival time (TAT).

**Pros:**

- Precise burst and rate control.
- Smooth, fair distribution of requests over time.
- Prevents starvation and ensures fairness.

**Cons:**

- More complex to understand and configure than Fixed Window or Token Bucket.
- Requires careful tuning of burst and steady rate for best results.

---

**Use GCRA when you need precise, fair, and burstable rate limiting for your APIs or distributed systems.**