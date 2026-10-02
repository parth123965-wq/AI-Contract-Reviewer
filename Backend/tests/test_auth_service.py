from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, status

from app.schemas.user import UserCreate
from app.services import auth_service as auth_service_module
from app.services.auth_service import AuthService


def make_user(**overrides):
    values = {
        "id": 7,
        "username": "test-user",
        "email": "test@example.com",
        "password_hash": "old-hash",
        "is_active": True,
        "is_verified": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def service():
    instance = AuthService()
    instance.user_repository = AsyncMock()
    return instance


@pytest.mark.asyncio
async def test_register_creates_user_and_sends_verification_otp(service, monkeypatch):
    db = AsyncMock()
    user = UserCreate(
        username="test-user",
        email="test@example.com",
        password="safe-password",
    )
    saved_user = make_user(is_verified=False)
    service.user_repository.get_user_by_email.return_value = None
    service.user_repository.create_user.return_value = saved_user
    otp = AsyncMock()
    otp.generate_otp.return_value = "123456"
    otp.send_otp_email = AsyncMock()
    monkeypatch.setattr(auth_service_module, "otp_service", otp)
    monkeypatch.setattr(auth_service_module, "hash_password", lambda **_: "hashed")

    result = await service.register_user(db, user)

    assert result is saved_user
    service.user_repository.create_user.assert_awaited_once()
    otp.generate_otp.assert_awaited_once_with(
        purpose="registration",
        identifier="test@example.com",
    )
    otp.send_otp_email.assert_awaited_once_with(
        email="test@example.com",
        otp_code="123456",
        purpose="registration",
    )


@pytest.mark.asyncio
async def test_register_rejects_existing_verified_email(service):
    service.user_repository.get_user_by_email.return_value = make_user(is_verified=True)
    user = UserCreate(
        username="test-user",
        email="test@example.com",
        password="safe-password",
    )

    with pytest.raises(HTTPException) as error:
        await service.register_user(AsyncMock(), user)

    assert error.value.status_code == status.HTTP_400_BAD_REQUEST
    service.user_repository.create_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_updates_existing_unverified_account(service, monkeypatch):
    db = AsyncMock()
    existing_user = make_user(is_verified=False)
    user = UserCreate(
        username="updated-user",
        email="test@example.com",
        password="safe-password",
    )
    service.user_repository.get_user_by_email.return_value = existing_user
    otp = AsyncMock()
    otp.generate_otp.return_value = "123456"
    otp.send_otp_email = AsyncMock()
    monkeypatch.setattr(auth_service_module, "otp_service", otp)
    monkeypatch.setattr(auth_service_module, "hash_password", lambda **_: "new-hash")

    result = await service.register_user(db, user)

    assert result is existing_user
    assert existing_user.username == "updated-user"
    assert existing_user.password_hash == "new-hash"
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(existing_user)


@pytest.mark.asyncio
async def test_verify_registration_marks_user_verified_and_sends_welcome_email(
    service, monkeypatch
):
    db = AsyncMock()
    user = make_user(is_verified=False)
    verified_user = make_user(is_verified=True)
    service.user_repository.get_user_by_email.return_value = user
    service.user_repository.mark_user_verified.return_value = verified_user
    otp = AsyncMock()
    otp.verify_otp.return_value = True
    email = AsyncMock()
    email.send_welcome_email = AsyncMock()
    monkeypatch.setattr(auth_service_module, "otp_service", otp)
    monkeypatch.setattr(auth_service_module, "email_service", email)

    result = await service.verify_registration(db, user.email, "123456")

    assert result is verified_user
    otp.verify_otp.assert_awaited_once_with(
        purpose="registration",
        identifier=user.email,
        input_otp="123456",
    )
    email.send_welcome_email.assert_awaited_once_with(
        email=verified_user.email,
        name=verified_user.username,
    )


@pytest.mark.asyncio
async def test_verify_registration_does_not_send_welcome_if_otp_fails(
    service, monkeypatch
):
    service.user_repository.get_user_by_email.return_value = make_user(is_verified=False)
    otp = AsyncMock()
    otp.verify_otp.side_effect = HTTPException(status_code=400, detail="Bad OTP")
    email = AsyncMock()
    monkeypatch.setattr(auth_service_module, "otp_service", otp)
    monkeypatch.setattr(auth_service_module, "email_service", email)

    with pytest.raises(HTTPException):
        await service.verify_registration(AsyncMock(), "test@example.com", "000000")

    service.user_repository.mark_user_verified.assert_not_awaited()
    email.send_welcome_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_password_reset_request_sends_otp_for_verified_active_user(
    service, monkeypatch
):
    user = make_user()
    service.user_repository.get_user_by_email.return_value = user
    otp = AsyncMock()
    otp.generate_otp.return_value = "123456"
    otp.send_otp_email = AsyncMock()
    monkeypatch.setattr(auth_service_module, "otp_service", otp)

    await service.request_password_reset(AsyncMock(), user.email)

    otp.generate_otp.assert_awaited_once_with(
        purpose="password_reset",
        identifier=user.email,
    )
    otp.send_otp_email.assert_awaited_once_with(
        email=user.email,
        otp_code="123456",
        purpose="password reset",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user",
    [
        None,
        make_user(is_active=False),
        make_user(is_verified=False),
    ],
)
async def test_password_reset_request_does_not_send_for_unknown_or_ineligible_user(
    service, monkeypatch, user
):
    service.user_repository.get_user_by_email.return_value = user
    otp = AsyncMock()
    monkeypatch.setattr(auth_service_module, "otp_service", otp)

    await service.request_password_reset(AsyncMock(), "test@example.com")

    otp.generate_otp.assert_not_awaited()
    otp.send_otp_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_password_reset_request_silently_respects_otp_cooldown(service, monkeypatch):
    service.user_repository.get_user_by_email.return_value = make_user()
    otp = AsyncMock()
    otp.generate_otp.side_effect = HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Cooldown",
    )
    monkeypatch.setattr(auth_service_module, "otp_service", otp)

    await service.request_password_reset(AsyncMock(), "test@example.com")

    otp.send_otp_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_password_reset_propagates_non_cooldown_otp_errors(service, monkeypatch):
    service.user_repository.get_user_by_email.return_value = make_user()
    otp = AsyncMock()
    otp.generate_otp.side_effect = HTTPException(status_code=503, detail="Redis down")
    monkeypatch.setattr(auth_service_module, "otp_service", otp)

    with pytest.raises(HTTPException) as error:
        await service.request_password_reset(AsyncMock(), "test@example.com")

    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_password_reset_updates_hash_and_sends_confirmation(service, monkeypatch):
    db = AsyncMock()
    user = make_user()
    service.user_repository.get_user_by_email.return_value = user
    otp = AsyncMock()
    otp.verify_otp.return_value = True
    email = AsyncMock()
    email.send_password_changed_notification = AsyncMock()
    monkeypatch.setattr(auth_service_module, "otp_service", otp)
    monkeypatch.setattr(auth_service_module, "email_service", email)
    monkeypatch.setattr(auth_service_module, "hash_password", lambda _: "new-hash")

    await service.reset_password(db, user.email, "123456", "new-password")

    otp.verify_otp.assert_awaited_once_with(
        purpose="password_reset",
        identifier=user.email,
        input_otp="123456",
    )
    assert user.password_hash == "new-hash"
    service.user_repository.update_user.assert_awaited_once_with(db=db, user=user)
    email.send_password_changed_notification.assert_awaited_once_with(
        email=user.email,
        username=user.username,
    )


@pytest.mark.asyncio
async def test_password_reset_rejects_unknown_account_without_verifying_otp(
    service, monkeypatch
):
    service.user_repository.get_user_by_email.return_value = None
    otp = AsyncMock()
    monkeypatch.setattr(auth_service_module, "otp_service", otp)

    with pytest.raises(HTTPException) as error:
        await service.reset_password(AsyncMock(), "missing@example.com", "123456", "new-password")

    assert error.value.status_code == status.HTTP_400_BAD_REQUEST
    otp.verify_otp.assert_not_awaited()
