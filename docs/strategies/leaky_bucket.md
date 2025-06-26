# 🪣 Leaky Bucket Rate Limiting

## 1. What is Leaky Bucket Rate Limiting?

- **Concept:**  
  The Leaky Bucket algorithm models traffic flow like water in a bucket. Each request is a "drop" added to the bucket. The bucket leaks at a constant rate (the leak rate), and if the bucket overflows (i.e., too many requests arrive too quickly), new requests are rejected. This produces a smooth, constant output rate and prevents bursts from overwhelming downstream systems.

- **Real-world usage:**  
  Leaky Bucket is commonly used in network routers, firewalls, and API gateways to ensure a steady flow of requests and to protect backend services from sudden spikes in traffic.

---

## 2. Usage

### Single Limiter Example

```python
from fastapicap import LeakyBucketRateLimiter
from fastapi import Depends

# Allow a burst of up to 10 requests, leaking at 2 requests per second
limiter = LeakyBucketRateLimiter(capacity=10, leaks_per_second=2)

@app.get("/leaky-bucket", dependencies=[Depends(limiter)])
async def leaky_bucket_limited():
    return {"message": "You are within the leaky bucket rate limit!"}
```

---

### Multiple Limiters Example

```python
limiter_short = LeakyBucketRateLimiter(capacity=5, leaks_per_second=1)
limiter_long = LeakyBucketRateLimiter(capacity=30, leaks_per_minute=10)

@app.get("/multi-leaky-bucket", dependencies=[Depends(limiter_short), Depends(limiter_long)])
async def multi_leaky_bucket_limited():
    return {"message": "You passed both leaky bucket rate limits!"}
```

---

## 3. Available Configuration Options

You can customize the Leaky Bucket limiter using the following parameters:

| Parameter           | Type      | Description                                                                                 | Default      |
|---------------------|-----------|---------------------------------------------------------------------------------------------|--------------|
| `capacity`          | `int`     | **Required.** Maximum number of requests the bucket can hold (burst size). Must be positive.| —            |
| `leaks_per_second`  | `float`   | Number of requests leaked (processed) per second.                                           | `0`          |
| `leaks_per_minute`  | `float`   | Number of requests leaked per minute.                                                       | `0`          |
| `leaks_per_hour`    | `float`   | Number of requests leaked per hour.                                                         | `0`          |
| `leaks_per_day`     | `float`   | Number of requests leaked per day.                                                          | `0`          |
| `key_func`          | `Callable`| Function to extract a unique key from the request.                                          | By default, uses client IP and path. |
| `on_limit`          | `Callable`| Function called when the rate limit is exceeded.                                            | By default, raises HTTP 429.         |
| `prefix`            | `str`     | Redis key prefix for all limiter keys.                                                      | `"cap"`      |

**Note:**  
- The total leak rate is the sum of all `leaks_per_*` arguments, converted to requests per second.
- At least one leak rate must be positive, and `capacity` must be positive.

**Example:**
```python
# 100 request burst, leaking at 10 requests per minute, with a custom prefix
limiter = LeakyBucketRateLimiter(capacity=100, leaks_per_minute=10, prefix="myapi")
```

---

## 4. How Leaky Bucket Works (with Example)

Suppose you set a **capacity of 10** and a **leak rate of 2 requests per second**.

- The bucket starts empty.
- Each request adds a "drop" to the bucket.
- If 10 requests arrive instantly, all are accepted (bucket is now full).
- If more requests arrive before the bucket has leaked enough, they are rejected.
- The bucket leaks at a constant rate (2 requests per second), making space for new requests.

**Visualization:**

| Time         | Bucket Level | Request? | Allowed? | Reason                |
|--------------|-------------|----------|----------|-----------------------|
| 12:00:00.000 | 0           | Yes      | ✅       | Bucket not full       |
| 12:00:00.100 | 1           | Yes      | ✅       |                       |
| ...          | ...         | ...      | ...      | ...                   |
| 12:00:00.900 | 9           | Yes      | ✅       |                       |
| 12:00:01.000 | 10          | Yes      | ✅       | Bucket full           |
| 12:00:01.100 | 10          | Yes      | ❌       | Bucket still full     |
| 12:00:01.500 | 9           | Yes      | ✅       | 1 request leaked out  |

- The bucket "leaks" at a constant rate, so after 0.5 seconds, 1 request has leaked out, making space for a new request.

---

## 5. Notes, Pros & Cons

**Notes:**

- This strategy is ideal for smoothing out bursty traffic and ensuring a constant request rate to downstream services.
- The `retry_after` value is based on how long until the next "drop" leaks out.

**Pros:**

- Produces a steady, predictable output rate.
- Prevents bursts from overwhelming your backend.
- Simple and effective for traffic shaping.

**Cons:**

- Does not allow true bursts beyond the bucket capacity.
- May introduce latency if requests are queued up in the bucket.
- Configuration (capacity vs. leak rate) can be unintuitive for some use cases.

---

**Use Leaky Bucket when you need to smooth out bursts and enforce a constant request rate to protect downstream systems.**