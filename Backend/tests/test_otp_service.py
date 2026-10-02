from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status

from app.core.config import settings
from app.services import otp_service as otp_module
from app.services.otp_service import OTPService


@pytest.fixture
def service():
    return OTPService()


@pytest.fixture
def redis_client(monkeypatch):
    client = AsyncMock()
    monkeypatch.setattr(otp_module, "get_redis", lambda: client)
    return client


def test_key_generation_normalizes_purpose_and_identifier(service):
    assert service._get_keys(" Password_Reset ", " User@Example.COM ") == (
        "otp:password_reset:user@example.com:code",
        "otp:password_reset:user@example.com:attempts",
        "otp:password_reset:user@example.com:cooldown",
    )


@pytest.mark.asyncio
async def test_generate_otp_stores_code_and_enforces_configured_expiry(
    service, redis_client, monkeypatch
):
    redis_client.exists.return_value = False
    monkeypatch.setattr(otp_module.secrets, "choice", lambda _: "8")

    code = await service.generate_otp("registration", "test@example.com")

    assert code == "8" * settings.OTP_LENGTH
    redis_client.set.assert_any_await(
        "otp:registration:test@example.com:code",
        code,
        ex=settings.OTP_EXPIRE_SECONDS,
    )
    redis_client.set.assert_any_await(
        "otp:registration:test@example.com:cooldown",
        "1",
        ex=settings.OTP_COOLDOWN_SECONDS,
    )
    redis_client.delete.assert_awaited_once_with(
        "otp:registration:test@example.com:attempts"
    )


@pytest.mark.asyncio
async def test_generate_otp_rejects_during_cooldown(service, redis_client):
    redis_client.exists.return_value = True
    redis_client.ttl.return_value = 23

    with pytest.raises(HTTPException) as error:
        await service.generate_otp("password_reset", "test@example.com")

    assert error.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "23 seconds" in error.value.detail
    redis_client.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_verify_otp_cleans_up_all_keys_on_success(service, redis_client):
    redis_client.get.side_effect = [None, "123456"]

    assert await service.verify_otp("registration", "test@example.com", "123456")

    redis_client.delete.assert_awaited_once_with(
        "otp:registration:test@example.com:code",
        "otp:registration:test@example.com:attempts",
        "otp:registration:test@example.com:cooldown",
    )


@pytest.mark.asyncio
async def test_verify_otp_increments_attempt_counter_on_wrong_code(service, redis_client):
    redis_client.get.side_effect = [None, "123456"]
    redis_client.incr.return_value = 1

    with pytest.raises(HTTPException) as error:
        await service.verify_otp("registration", "test@example.com", "000000")

    assert error.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "attempt(s) remaining" in error.value.detail
    redis_client.expire.assert_awaited_once_with(
        "otp:registration:test@example.com:attempts",
        settings.OTP_EXPIRE_SECONDS,
    )


@pytest.mark.asyncio
async def test_verify_otp_rejects_and_clears_code_after_max_attempts(
    service, redis_client, monkeypatch
):
    monkeypatch.setattr(settings, "OTP_MAX_ATTEMPTS", 3)
    redis_client.get.return_value = "3"

    with pytest.raises(HTTPException) as error:
        await service.verify_otp("registration", "test@example.com", "000000")

    assert error.value.status_code == status.HTTP_400_BAD_REQUEST
    redis_client.delete.assert_awaited_once_with(
        "otp:registration:test@example.com:code",
        "otp:registration:test@example.com:attempts",
    )


@pytest.mark.asyncio
async def test_verify_otp_rejects_missing_or_expired_code(service, redis_client):
    redis_client.get.side_effect = [None, None]

    with pytest.raises(HTTPException) as error:
        await service.verify_otp("registration", "test@example.com", "123456")

    assert error.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "invalid or has expired" in error.value.detail
    redis_client.incr.assert_not_awaited()
