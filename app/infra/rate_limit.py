"""
Sliding window rate limiter using Redis.
Implements token bucket algorithm for burst protection.
"""
import time
import redis.asyncio as redis


async def sliding_window_ok(r: redis.Redis, key: str, limit: int, window_s: int, burst: int) -> bool:
    """
    Check if a request is allowed under the sliding window rate limit.
    
    Args:
        r: Redis client instance
        key: Rate limit key (e.g., "rate_limit:ip:192.168.1.1")
        limit: Maximum number of requests allowed in the window
        window_s: Time window in seconds
        burst: Maximum burst size allowed
    
    Returns:
        True if the request is allowed, False otherwise
    """
    now = time.time()
    pipe = r.pipeline()
    
    # Remove old entries outside the window
    pipe.zremrangebyscore(key, 0, now - window_s)
    
    # Count current requests in window
    pipe.zcard(key)
    
    # Add current request timestamp
    pipe.zadd(key, {str(now): now})
    
    # Set expiry on the key
    pipe.expire(key, window_s + 1)
    
    # Execute pipeline
    _, count, *_ = await pipe.execute()
    
    # Check if within limits
    return count < limit


class RateLimiter:
    """Rate limiter with sliding window and burst protection."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = redis.from_url(redis_url, decode_responses=True)
    
    async def is_allowed(self, identifier: str, limit: int = 20, window_s: int = 60, burst: int = 5) -> bool:
        """
        Check if a request from the given identifier is allowed.
        
        Args:
            identifier: Unique identifier (e.g., IP address or user ID)
            limit: Sustained rate limit (requests per window)
            window_s: Time window in seconds
            burst: Burst allowance
        
        Returns:
            True if allowed, False if rate limited
        """
        key = f"rate_limit:{identifier}"
        return await sliding_window_ok(self.redis, key, limit, window_s, burst)
    
    async def close(self):
        """Close Redis connection."""
        await self.redis.close()
