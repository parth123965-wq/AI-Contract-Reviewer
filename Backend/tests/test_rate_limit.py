from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.core import redis_setup
from app.core.rate_limit import RateLimiter


def make_request(headers=None, client=("203.0.113.5", 1234)):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [
                (key.lower().encode(), value.encode())
                for key, value in (headers or {}).items()
            ],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": client,
            "scheme": "http",
        }
    )


@pytest.mark.asyncio
async def test_rate_limiter_fails_open_when_redis_is_uninitialized(monkeypatch):
    monkeypatch.setattr(redis_setup, "redis_client", None)

    assert await RateLimiter(times=1)(make_request(), Response()) is None


@pytest.mark.asyncio
async def test_rate_limiter_sets_headers_and_uses_forwarded_client_ip(monkeypatch):
    client = AsyncMock()
    client.incr.return_value = 1
    client.ttl.return_value = 30
    monkeypatch.setattr(redis_setup, "redis_client", client)
    response = Response()

    await RateLimiter(times=5, seconds=60, prefix="test")(
        make_request({"X-Forwarded-For": "198.51.100.4, 203.0.113.8"}),
        response,
    )

    client.incr.assert_awaited_once_with("rate_limit:test:198.51.100.4")
    client.expire.assert_awaited_once_with("rate_limit:test:198.51.100.4", 60)
    assert response.headers["X-RateLimit-Limit"] == "5"
    assert response.headers["X-RateLimit-Remaining"] == "4"
    assert response.headers["X-RateLimit-Reset"] == "30"


@pytest.mark.asyncio
async def test_rate_limiter_rejects_requests_over_limit(monkeypatch):
    client = AsyncMock()
    client.incr.return_value = 3
    client.ttl.return_value = 12
    monkeypatch.setattr(redis_setup, "redis_client", client)

    with pytest.raises(HTTPException) as error:
        await RateLimiter(times=2, prefix="test")(make_request(), Response())

    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "12"
    assert error.value.headers["X-RateLimit-Remaining"] == "0"


@pytest.mark.asyncio
async def test_rate_limiter_fails_open_on_redis_errors(monkeypatch):
    client = AsyncMock()
    client.incr.side_effect = ConnectionError("Redis unavailable")
    monkeypatch.setattr(redis_setup, "redis_client", client)

    assert await RateLimiter()(make_request(), Response()) is None
