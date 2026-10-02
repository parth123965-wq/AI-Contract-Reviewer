from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services import email_service as email_module
from app.services.email_service import EmailService


@pytest.mark.asyncio
async def test_welcome_email_renders_name_and_sends_to_recipient(monkeypatch):
    fastmail = AsyncMock()
    monkeypatch.setattr(email_module, "get_email", lambda: fastmail)

    await EmailService().send_welcome_email("new@example.com", "New User")

    fastmail.send_message.assert_awaited_once()
    message = fastmail.send_message.await_args.args[0]
    assert [recipient.email for recipient in message.recipients] == ["new@example.com"]
    assert "New User" in message.body


@pytest.mark.asyncio
async def test_password_reset_email_renders_reset_link(monkeypatch):
    fastmail = AsyncMock()
    monkeypatch.setattr(email_module, "get_email", lambda: fastmail)

    await EmailService().send_password_reset_email(
        "user@example.com",
        "https://example.com/reset?token=abc",
    )

    message = fastmail.send_message.await_args.args[0]
    assert [recipient.email for recipient in message.recipients] == ["user@example.com"]
    assert "https://example.com/reset?token=abc" in message.body


@pytest.mark.asyncio
async def test_email_delivery_failure_is_reported(monkeypatch):
    fastmail = AsyncMock()
    fastmail.send_message.side_effect = RuntimeError("SMTP unavailable")
    monkeypatch.setattr(email_module, "get_email", lambda: fastmail)

    with pytest.raises(HTTPException) as error:
        await EmailService().send_welcome_email("user@example.com", "User")

    assert error.value.status_code == 500
