import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import Request, Response, HTTPException, status
from app.core.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_under_limit():
    limiter = RateLimiter(times=3, seconds=60, prefix="test")

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    mock_request.client.host = "192.168.1.100"

    mock_response = Response()

    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 1
    mock_redis.ttl.return_value = 58

    with patch("app.core.redis_setup.redis_client", mock_redis):
        await limiter(request=mock_request, response=mock_response)

    assert mock_response.headers["X-RateLimit-Limit"] == "3"
    assert mock_response.headers["X-RateLimit-Remaining"] == "2"
    assert mock_response.headers["X-RateLimit-Reset"] == "58"
    mock_redis.expire.assert_called_once_with("rate_limit:test:192.168.1.100", 60)


@pytest.mark.asyncio
async def test_rate_limiter_exceeded_limit():
    limiter = RateLimiter(times=2, seconds=60, prefix="test")

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"X-Forwarded-For": "203.0.113.195, 70.41.3.18"}
    mock_request.client.host = "127.0.0.1"

    mock_response = Response()

    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 3
    mock_redis.ttl.return_value = 45

    with patch("app.core.redis_setup.redis_client", mock_redis):
        with pytest.raises(HTTPException) as exc_info:
            await limiter(request=mock_request, response=mock_response)

        assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert exc_info.value.detail == "Too many requests. Please try again later."
        assert exc_info.value.headers["Retry-After"] == "45"
        assert exc_info.value.headers["X-RateLimit-Remaining"] == "0"


@pytest.mark.asyncio
async def test_rate_limiter_fail_open_redis_uninitialized():
    limiter = RateLimiter(times=5, seconds=60, prefix="test")

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    mock_request.client.host = "127.0.0.1"
    mock_response = Response()

    # Pass None as redis_client
    with patch("app.core.redis_setup.redis_client", None):
        # Should not raise any exception (fail-open)
        await limiter(request=mock_request, response=mock_response)


@pytest.mark.asyncio
async def test_rate_limiter_fail_open_on_redis_exception():
    limiter = RateLimiter(times=5, seconds=60, prefix="test")

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    mock_request.client.host = "127.0.0.1"
    mock_response = Response()

    mock_redis = AsyncMock()
    mock_redis.incr.side_effect = Exception("Redis connection refused")

    with patch("app.core.redis_setup.redis_client", mock_redis):
        # Should catch exception and fail-open without crashing
        await limiter(request=mock_request, response=mock_response)
