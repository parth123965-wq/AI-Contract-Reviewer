from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.auth import auth_router
from app.database.database import get_db
from app.services.auth_service import auth_service


def create_app(service):
    app = FastAPI()
    app.include_router(auth_router)

    async def override_db():
        yield object()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[auth_service] = lambda: service
    return app


@pytest.mark.asyncio
async def test_password_reset_request_returns_generic_response():
    service = AsyncMock()
    app = create_app(service)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/auth/password-reset/request",
            json={"email": "user@example.com"},
        )

    assert response.status_code == 200
    assert "If an active, verified account exists" in response.json()["message"]
    service.request_password_reset.assert_awaited_once()


@pytest.mark.asyncio
async def test_password_reset_confirmation_calls_service_with_validated_data():
    service = AsyncMock()
    app = create_app(service)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/auth/password-reset/confirm",
            json={
                "email": "user@example.com",
                "otp_code": "123456",
                "new_password": "new-password",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"message": "Password reset successfully."}
    service.reset_password.assert_awaited_once()
    assert service.reset_password.await_args.kwargs["email"] == "user@example.com"
    assert service.reset_password.await_args.kwargs["otp_code"] == "123456"


@pytest.mark.asyncio
async def test_password_reset_confirmation_rejects_invalid_input():
    app = create_app(AsyncMock())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/auth/password-reset/confirm",
            json={
                "email": "not-an-email",
                "otp_code": "12",
                "new_password": "short",
            },
        )

    assert response.status_code == 422
