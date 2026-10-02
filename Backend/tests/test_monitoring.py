from unittest.mock import AsyncMock

import pytest

from app.core import monitoring, redis_setup


@pytest.mark.asyncio
async def test_redis_health_reports_disabled_without_client(monkeypatch):
    monkeypatch.setattr(redis_setup, "redis_client", None)

    result = await monitoring.get_redis_health()

    assert result["status"] == "disabled"
    assert result["connected"] is False


@pytest.mark.asyncio
async def test_redis_health_reports_ping_and_memory(monkeypatch):
    client = AsyncMock()
    client.ping.return_value = True
    client.info.return_value = {"used_memory_human": "1.00M"}
    monkeypatch.setattr(redis_setup, "redis_client", client)

    result = await monitoring.get_redis_health()

    assert result["status"] == "healthy"
    assert result["connected"] is True
    assert result["used_memory_human"] == "1.00M"
    client.info.assert_awaited_once_with("memory")


@pytest.mark.asyncio
async def test_redis_health_reports_unhealthy_ping(monkeypatch):
    client = AsyncMock()
    client.ping.return_value = False
    monkeypatch.setattr(redis_setup, "redis_client", client)

    result = await monitoring.get_redis_health()

    assert result["status"] == "unhealthy"
    assert result["connected"] is False


@pytest.mark.asyncio
async def test_redis_health_captures_client_errors(monkeypatch):
    client = AsyncMock()
    client.ping.side_effect = ConnectionError("Redis unavailable")
    monkeypatch.setattr(redis_setup, "redis_client", client)

    result = await monitoring.get_redis_health()

    assert result["status"] == "unhealthy"
    assert result["connected"] is False
    assert "Redis unavailable" in result["error"]
