 # 🧩 Rate Limiting Strategies in FastAPI-Cap

FastAPI-Cap provides a suite of powerful, production-grade rate limiting strategies, each designed to address different API traffic patterns and business requirements. All strategies are implemented using **Redis** for distributed state management and **Lua scripting** for atomic, high-performance operations.

This page introduces each available strategy, helping you choose the best fit for your use case.

---

## 📚 Available Strategies

### 1. **Fixed Window**

**Description:**  
Divides time into fixed intervals (windows), counting requests within each window. The counter resets at the start of each new window.

- **Best for:** Simple, aggressive limits (e.g., "100 requests per minute").
- **Pros:** Easy to understand and implement; low memory usage.
- **Cons:** Can allow bursts at window boundaries.

[Learn more →](./fixed_window.md)

---

### 2. **Token Bucket**

**Description:**  
Tokens are added to a bucket at a steady rate. Each request consumes a token. Allows short bursts up to the bucket's capacity, then enforces an average rate.

- **Best for:** Allowing bursts while maintaining a steady average rate.
- **Pros:** Smooths traffic; flexible burst control.
- **Cons:** Requires tuning of capacity and refill rate.

[Learn more →](./token_bucket.md)

---

### 3. **Leaky Bucket**

**Description:**  
Requests are added to a bucket and "leak" out at a constant rate. If the bucket overflows, new requests are rejected.

- **Best for:** Enforcing a constant output rate; smoothing out bursts.
- **Pros:** Produces a steady request flow.
- **Cons:** Does not allow bursts; may introduce latency.

[Learn more →](./leaky_bucket.md)

---

### 4. **Generic Cell Rate Algorithm (GCRA)**

**Description:**  
A precise algorithm that tracks a "Theoretical Arrival Time" for each request, providing fine-grained burst and rate control.

- **Best for:** Precise, fair rate limiting with accurate burst handling.
- **Pros:** Highly accurate; prevents starvation.
- **Cons:** More complex to configure and understand.

[Learn more →](./gcra.md)

---

### 5. **Approximated Sliding Window**

**Description:**  
Estimates the number of requests in a sliding window using two fixed windows and a weighted average.

- **Best for:** Balancing accuracy and resource usage.
- **Pros:** Smoother than fixed window; more efficient than log-based.
- **Cons:** Not perfectly accurate; some boundary effects.

[Learn more →](./sliding_window.md)

---

### 6. **Sliding Window (Log-based)**

**Description:**  
Records a timestamp for every request and counts only those within the current window, providing the most accurate and fair rate limiting.

- **Best for:** Maximum accuracy and fairness.
- **Pros:** Eliminates burst issues; ensures consistent rate.
- **Cons:** Higher memory usage for high-traffic endpoints.

[Learn more →](./sliding_window_log.md)

---

## 🛠️ How to Choose?

- **For simple, low-traffic APIs:** Start with **Fixed Window**.
- **For APIs needing burst tolerance:** Use **Token Bucket** or **GCRA**.
- **For strict, smooth traffic shaping:** Try **Leaky Bucket**.
- **For maximum fairness and accuracy:** Use **Sliding Window (Log-based)**.
- **For a balance of accuracy and efficiency:** Consider **Approximated Sliding Window**.

---

## 📖 Next Steps

- [Jump to the Quickstart Guide](../quickstart.md)
- [API Reference](../api.md)
---
