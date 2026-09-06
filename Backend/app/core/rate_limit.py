import logging
from typing import Optional
from fastapi import Request, Response, HTTPException, status
import app.core.redis_setup as redis_setup
from app.core.logger import get_app_logger

logger = get_app_logger("rate_limiter")


class RateLimiter:
    """
    Redis-backed Rate Limiter dependency for FastAPI routes.

    Attributes:
        times (int): Maximum number of requests allowed within the given window.
        seconds (int): Time window duration in seconds.
        prefix (str): Namespace prefix for Redis keys.
    """

    def __init__(self, times: int = 60, seconds: int = 60, prefix: str = "default"):
        self.times = times
        self.seconds = seconds
        self.prefix = prefix

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract the client IP address from the request.
        Supports X-Forwarded-For header if behind a reverse proxy.
        """
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Take the first IP address in the chain
            return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    async def __call__(self, request: Request, response: Response) -> None:
        client_ip = self._get_client_ip(request)
        key = f"rate_limit:{self.prefix}:{client_ip}"

        redis_client = redis_setup.redis_client

        if redis_client is None:
            # Fail-open resilience: log warning and proceed if Redis connection is unavailable
            logger.warning("Redis client uninitialized during rate limit check; allowing request (fail-open).")
            return

        try:
            # Increment current counter atomically
            current = await redis_client.incr(key)

            # Set expiration on key creation
            if current == 1:
                await redis_client.expire(key, self.seconds)

            # Get remaining time-to-live for the key
            ttl = await redis_client.ttl(key)
            if ttl < 0:
                ttl = self.seconds

            remaining = max(0, self.times - current)

            # Attach standard RateLimit headers to response
            response.headers["X-RateLimit-Limit"] = str(self.times)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(ttl)

            # Check if limit has been exceeded
            if current > self.times:
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip} on prefix '{self.prefix}'. "
                    f"Count: {current}/{self.times}"
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={
                        "Retry-After": str(ttl),
                        "X-RateLimit-Limit": str(self.times),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(ttl),
                    }
                )

        except HTTPException:
            # Re-raise HTTPException (such as 429) directly
            raise
        except Exception as e:
            # Catch Redis connection errors / timeouts and fail-open gracefully
            logger.error(f"Error executing Redis rate limit check for key {key}: {e}")
            return
