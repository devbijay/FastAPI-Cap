# 👋 Welcome to FastAPI-Cap!

**FastAPI-Cap** is a robust and flexible rate-limiting library designed specifically
for FastAPI applications. Leveraging the power of Redis and highly optimized Lua scripts,
Cap provides a suite of algorithms to effectively control traffic to your APIs,
prevent abuse, and ensure stable service delivery.

Whether you need simple request limiting or sophisticated traffic shaping,
FastAPI-Cap offers a battle-tested solution that integrates seamlessly into
your existing FastAPI projects.

## 🌟 Why FastAPI-Cap?

*   **Diverse Algorithms:** Choose from a range of algorithms to perfectly match your
    rate-limiting requirements.
*   **High Performance:** Built on Redis and efficient Lua scripting for atomic
    operations and minimal overhead.
*   **Easy Integration:** Designed as FastAPI dependencies/decorators for a smooth
    developer experience.
*   **Customizable:** Tailor key extraction and rate-limit handling to fit your
    application's unique needs.
*   **Reliable:** Distributed by nature, ensuring consistent limits across multiple
    API instances.

## ⚖️ Algorithm Comparison

FastAPI-Cap offers several distinct rate-limiting strategies. Each algorithm has
its strengths, making it suitable for different use cases. All of these implementations
leverage **Redis for state management** and **Lua scripting for atomic, high-performance
operations**.

| Algorithm                     | Description                                                                                                                                                             | Best For                                                                  | Pros                                                                                                    | Cons                                                                                                                                                                 |
| :---------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------ | :------------------------------------------------------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Fixed Window**              | Divides time into discrete, fixed windows (e.g., 60 seconds). Requests are counted within the current window, resetting when a new window begins.                        | Simple, aggressive limits; easy to understand.                            | Easy to implement; low memory footprint.                                                                | Can lead to "bursts" at the window boundary if many requests arrive simultaneously right before/after reset.                                                         |
| **Token Bucket**              | Tokens are added to a "bucket" at a constant rate up to a max capacity. Each request consumes one token. Allows for bursts up to bucket capacity, then enforces average rate. | Controlling average rate with allowed bursts; smooth traffic flow.        | Handles bursts well; offers flexibility with capacity; good average throughput.                         | Can allow more requests in short bursts than the average rate if the bucket is full; configuration requires tuning capacity vs. refill rate.                        |
| **Leaky Bucket**              | Requests are placed into a "bucket" that has a fixed outflow (leak) rate. If the bucket overflows, new requests are rejected.                                            | Ensuring a truly smooth, constant output rate; queueing requests (conceptually). | Produces the most consistent output rate; effectively smooths out bursty traffic.                       | Does not directly support bursts (they are absorbed and smoothed); may introduce latency if requests are conceptually queued; configuration can be unintuitive. |
| **Generic Cell Rate Algorithm (GCRA)** | An advanced, precise algorithm that determines a "Theoretical Arrival Time" (TAT) for each request. It's similar to Token Bucket but often more precise for burst allowance. | Precise burst control; very smooth and fair distribution over time.       | Highly accurate; excellent for preventing starvation; good for per-user limits.                         | Can be complex to understand and configure initially; `retry-after` calculation is based on TAT.                                                                    |
| **Approximated Sliding Window** | Uses two fixed windows (current and previous) and a weighted average to estimate the count in a sliding window. More efficient than log-based, smoother than fixed. | Balancing accuracy and resource usage.                                    | Better burst handling than fixed window; more memory-efficient than log-based sliding window.           | Not perfectly accurate (it's an approximation); still susceptible to some boundary issues if not carefully tuned.                                                    |
| **Sliding Window (Log-based)** | Records a timestamp for every request in a sorted set. The count is dynamically calculated by removing old timestamps and summing the remaining within the window.   | Highest accuracy and fairness; eliminates fixed window "burst" problem.   | Most accurate and fair; ensures consistent rate over any time slice within the window.                  | Can be more memory-intensive for high request volumes due to storing individual timestamps.             |

## 🚀 Get Started

Ready to implement robust rate limiting in your FastAPI application?

[**➡️ Jump to the Quickstart Guide**](quickstart.md)

Or [explore each algorithm](strategies/overview.md) in detail: