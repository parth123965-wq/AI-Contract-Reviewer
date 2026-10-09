import pytest
from httpx import ASGITransport, AsyncClient

from app.main import _get_cors_origins, app


def test_cors_ignores_wildcard_and_keeps_explicit_origins():
    assert _get_cors_origins(
        "https://ai-contract-reviewer.ai.studio, *"
    ) == ["https://ai-contract-reviewer.ai.studio"]


def test_cors_with_only_wildcard_has_no_allowed_origins():
    assert _get_cors_origins("*") == []


def test_cors_with_empty_setting_has_no_allowed_origins():
    assert _get_cors_origins("  , ") == []


@pytest.mark.asyncio
async def test_cors_allows_configured_frontend_origin():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.options(
            "/auth/login",
            headers={
                "Origin": "http://localhost",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost"


@pytest.mark.asyncio
async def test_cors_rejects_unconfigured_origin():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.options(
            "/auth/login",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
