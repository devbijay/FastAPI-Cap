# 🪣 Token Bucket Rate Limiting

## 1. What is Token Bucket Rate Limiting?

- **Concept:**  
  The Token Bucket algorithm allows requests to be processed as long as there are tokens in the bucket. Tokens are added at a steady rate (the refill rate), up to a maximum capacity. Each request consumes a token. If the bucket is empty, requests are denied (or delayed). This allows for short bursts of traffic while enforcing a steady average rate over time.

- **Example:**  
  If you set a capacity of 10 tokens and a refill rate of 1 token per second, a client can make up to 10 requests instantly (if the bucket is full), and then 1 request per second thereafter as tokens are refilled.

---

## 2. Usage

### Single Limiter Example

```python
from fastapicap import TokenBucketRateLimiter
from fastapi import Depends

# Allow bursts up to 10 requests, refilling at 1 token per second
limiter = TokenBucketRateLimiter(capacity=10, tokens_per_second=1)

@app.get("/token-bucket", dependencies=[Depends(limiter)])
async def token_bucket_limited():
    return {"message": "You are within the token bucket rate limit!"}
```

---

### Multiple Limiters Example

```python
limiter_burst = TokenBucketRateLimiter(capacity=5, tokens_per_second=1)
limiter_long = TokenBucketRateLimiter(capacity=30, tokens_per_minute=10)

@app.get("/multi-token-bucket", dependencies=[Depends(limiter_burst), Depends(limiter_long)])
async def multi_token_bucket_limited():
    return {"message": "You passed both token bucket rate limits!"}
```

---

## 3. Available Configuration Options

You can customize the Token Bucket limiter using the following parameters:

| Parameter            | Type      | Description                                                                                 | Default      |
|----------------------|-----------|---------------------------------------------------------------------------------------------|--------------|
| `capacity`           | `int`     | **Required.** Maximum number of tokens the bucket can hold (burst size). Must be positive.  | —            |
| `tokens_per_second`  | `float`   | Number of tokens added per second.                                                          | `0`          |
| `tokens_per_minute`  | `float`   | Number of tokens added per minute.                                                          | `0`          |
| `tokens_per_hour`    | `float`   | Number of tokens added per hour.                                                            | `0`          |
| `tokens_per_day`     | `float`   | Number of tokens added per day.                                                             | `0`          |
| `key_func`           | `Callable`| Function to extract a unique key from the request.                                          | By default, uses client IP and path. |
| `on_limit`           | `Callable`| Function called when the rate limit is exceeded.                                            | By default, raises HTTP 429.         |
| `prefix`             | `str`     | Redis key prefix for all limiter keys.                                                      | `"cap"`      |

**Note:**  
- The total refill rate is the sum of all `tokens_per_*` arguments, converted to tokens per second.
- At least one refill rate must be positive, and `capacity` must be positive.

**Example:**
```python
# 100 token burst, refilling at 10 tokens per minute, with a custom prefix
limiter = TokenBucketRateLimiter(capacity=100, tokens_per_minute=10, prefix="myapi")
```

---

## 4. How Token Bucket Works (with Example)

Suppose you set a **capacity of 10 tokens** and a **refill rate of 1 token per second**.

- The bucket starts full (10 tokens).
- Each request consumes 1 token.
- If 10 requests arrive instantly, all are allowed (bucket is now empty).
- Further requests are denied until tokens are refilled (1 per second).
- After 5 seconds, 5 tokens are available again, allowing 5 more requests.

**Visualization:**

| Time         | Tokens in Bucket | Request? | Allowed? | Reason                |
|--------------|------------------|----------|----------|-----------------------|
| 12:00:00     | 10               | Yes      | ✅       | Bucket full           |
| 12:00:00     | 9                | Yes      | ✅       |                       |
| ...          | ...              | ...      | ...      | ...                   |
| 12:00:00     | 1                | Yes      | ✅       |                       |
| 12:00:00     | 0                | Yes      | ✅       | Last token used       |
| 12:00:01     | 0                | Yes      | ❌       | No tokens left        |
| 12:00:01     | 1 (refilled)     | Yes      | ✅       | 1 token refilled      |
| 12:00:02     | 1 (refilled)     | Yes      | ✅       | 1 token refilled      |

---

## 5. Notes, Pros & Cons

**Notes:**

- This strategy is excellent for APIs that need to allow short bursts but enforce a steady average rate.
- The `retry_after` value is based on how long until the next token is available.

**Pros:**

- Allows bursts up to the bucket capacity.
- Smooths out traffic over time.
- Flexible and widely used in real-world APIs.

**Cons:**

- Slightly more complex than Fixed Window.
- If refill rate or capacity is misconfigured, can allow more requests than intended in short bursts.

---

**Use Token Bucket when you want to allow bursts but enforce a steady average rate over time.**