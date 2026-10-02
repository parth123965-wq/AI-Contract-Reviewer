from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.schemas.user import (
    RequestEmailChangeRequest,
    UpdateUsernameRequest,
    VerifyEmailChangeRequest,
    VerifyPasswordChangeRequest,
)
from app.services import user_service as user_module
from app.services.user_service import UserService


def make_user(**overrides):
    values = {
        "id": 5,
        "username": "old-name",
        "email": "old@example.com",
        "password_hash": "old-hash",
        "is_active": True,
        "is_admin": False,
        "is_verified": True,
        "created_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def service():
    instance = UserService()
    instance.user_repository = AsyncMock()
    return instance


@pytest.mark.asyncio
async def test_update_username_returns_without_writing_when_unchanged(service):
    user = make_user()

    result = await service.update_username(
        AsyncMock(),
        user,
        UpdateUsernameRequest(username=user.username),
    )

    assert result.username == user.username
    service.user_repository.update_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_username_rejects_another_users_name(service):
    user = make_user()
    service.user_repository.get_user_by_username.return_value = make_user(
        id=9,
        username="taken",
    )

    with pytest.raises(HTTPException) as error:
        await service.update_username(
            AsyncMock(),
            user,
            UpdateUsernameRequest(username="taken"),
        )

    assert error.value.status_code == 400
    service.user_repository.update_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_username_persists_and_sends_notification(service, monkeypatch):
    user = make_user()
    service.user_repository.get_user_by_username.return_value = None
    service.user_repository.update_user.side_effect = lambda db, user: user
    email = AsyncMock()
    monkeypatch.setattr(user_module, "email_service", email)

    result = await service.update_username(
        AsyncMock(),
        user,
        UpdateUsernameRequest(username="  new-name  "),
    )

    assert result.username == "new-name"
    email.send_username_changed_notification.assert_awaited_once_with(
        email=user.email,
        old_username="old-name",
        new_username="new-name",
    )


@pytest.mark.asyncio
async def test_request_email_change_sends_otp(service, monkeypatch):
    user = make_user()
    service.user_repository.get_user_by_email.return_value = None
    otp = AsyncMock()
    otp.generate_otp.return_value = "123456"
    monkeypatch.setattr(user_module, "otp_service", otp)

    result = await service.request_email_change(
        AsyncMock(),
        user,
        RequestEmailChangeRequest(new_email="New@example.com"),
    )

    assert "new@example.com" in result["message"]
    otp.generate_otp.assert_awaited_once_with(
        purpose="email_change",
        identifier="new@example.com",
    )
    otp.send_otp_email.assert_awaited_once_with(
        email="new@example.com",
        otp_code="123456",
        purpose="email_change",
    )


@pytest.mark.asyncio
async def test_request_email_change_rejects_duplicate_address(service, monkeypatch):
    service.user_repository.get_user_by_email.return_value = make_user(id=9)
    otp = AsyncMock()
    monkeypatch.setattr(user_module, "otp_service", otp)

    with pytest.raises(HTTPException) as error:
        await service.request_email_change(
            AsyncMock(),
            make_user(),
            RequestEmailChangeRequest(new_email="other@example.com"),
        )

    assert error.value.status_code == 400
    otp.generate_otp.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_email_change_verifies_otp_persists_and_notifies_both_addresses(
    service, monkeypatch
):
    user = make_user()
    service.user_repository.get_user_by_email.return_value = None
    service.user_repository.update_user.side_effect = lambda db, user: user
    otp = AsyncMock()
    email = AsyncMock()
    monkeypatch.setattr(user_module, "otp_service", otp)
    monkeypatch.setattr(user_module, "email_service", email)

    result = await service.confirm_email_change(
        AsyncMock(),
        user,
        VerifyEmailChangeRequest(
            new_email="new@example.com",
            otp_code="123456",
        ),
    )

    assert result.email == "new@example.com"
    otp.verify_otp.assert_awaited_once_with(
        purpose="email_change",
        identifier="new@example.com",
        input_otp="123456",
    )
    notified_addresses = {
        call.kwargs["email"]
        for call in email.send_email_changed_notification.await_args_list
    }
    assert notified_addresses == {"old@example.com", "new@example.com"}


@pytest.mark.asyncio
async def test_request_password_change_sends_otp(service, monkeypatch):
    user = make_user()
    otp = AsyncMock()
    otp.generate_otp.return_value = "654321"
    monkeypatch.setattr(user_module, "otp_service", otp)

    result = await service.request_password_change(AsyncMock(), user)

    assert user.email in result["message"]
    otp.generate_otp.assert_awaited_once_with(
        purpose="password_change",
        identifier=user.email,
    )
    otp.send_otp_email.assert_awaited_once_with(
        email=user.email,
        otp_code="654321",
        purpose="password_change",
    )


@pytest.mark.asyncio
async def test_confirm_password_change_checks_current_password_before_otp(
    service, monkeypatch
):
    otp = AsyncMock()
    monkeypatch.setattr(user_module, "otp_service", otp)
    monkeypatch.setattr(user_module, "verify_password", lambda **_: False)

    with pytest.raises(HTTPException) as error:
        await service.confirm_password_change(
            AsyncMock(),
            make_user(),
            VerifyPasswordChangeRequest(
                current_password="wrong-password",
                new_password="new-password",
                otp_code="123456",
            ),
        )

    assert error.value.status_code == 400
    otp.verify_otp.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_password_change_rejects_reusing_current_password(
    service, monkeypatch
):
    otp = AsyncMock()
    monkeypatch.setattr(user_module, "otp_service", otp)
    monkeypatch.setattr(user_module, "verify_password", lambda **_: True)

    with pytest.raises(HTTPException) as error:
        await service.confirm_password_change(
            AsyncMock(),
            make_user(),
            VerifyPasswordChangeRequest(
                current_password="same-password",
                new_password="same-password",
                otp_code="123456",
            ),
        )

    assert error.value.status_code == 400
    otp.verify_otp.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_password_change_updates_hash_after_otp(service, monkeypatch):
    db = AsyncMock()
    user = make_user()
    otp = AsyncMock()
    email = AsyncMock()
    monkeypatch.setattr(user_module, "otp_service", otp)
    monkeypatch.setattr(user_module, "email_service", email)
    monkeypatch.setattr(user_module, "verify_password", lambda **_: True)
    monkeypatch.setattr(user_module, "hash_password", lambda **_: "new-hash")

    result = await service.confirm_password_change(
        db,
        user,
        VerifyPasswordChangeRequest(
            current_password="current-password",
            new_password="different-password",
            otp_code="123456",
        ),
    )

    assert result["message"] == "Password changed successfully."
    assert user.password_hash == "new-hash"
    service.user_repository.update_user.assert_awaited_once_with(db=db, user=user)
    email.send_password_changed_notification.assert_awaited_once_with(
        email=user.email,
        username=user.username,
    )
