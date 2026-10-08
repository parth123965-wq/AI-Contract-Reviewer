import base64
from email import message_from_bytes
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import HTTPException

from app.services import email_service as email_module
from app.services.email_service import EmailService


class FakeAsyncClient:
    def __init__(self, *, timeout):
        self.timeout = timeout
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, **kwargs):
        self.requests.append({"url": url, **kwargs})
        if url == email_module.GMAIL_TOKEN_URL:
            response = httpx.Response(
                200,
                json={"access_token": "test-access-token"},
                request=httpx.Request("POST", url),
            )
        else:
            response = httpx.Response(
                200,
                json={"id": "gmail-message-id"},
                request=httpx.Request("POST", url),
            )
        response.raise_for_status()
        return response


@pytest.mark.asyncio
async def test_welcome_email_uses_gmail_oauth_and_sends_html(monkeypatch):
    client = FakeAsyncClient(timeout=15.0)
    monkeypatch.setattr(email_module.httpx, "AsyncClient", lambda **kwargs: client)

    await EmailService().send_welcome_email("new@example.com", "New User")

    token_request, send_request = client.requests
    assert token_request["url"] == email_module.GMAIL_TOKEN_URL
    assert token_request["data"] == {
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "refresh_token": "test-refresh-token",
        "grant_type": "refresh_token",
    }
    assert send_request["url"] == email_module.GMAIL_SEND_URL
    assert send_request["headers"]["Authorization"] == "Bearer test-access-token"
    message_bytes = base64.urlsafe_b64decode(send_request["json"]["raw"] + "===")
    message = message_from_bytes(message_bytes)
    assert message["To"] == "new@example.com"
    assert message["From"] == "sender@gmail.com"
    assert message["Subject"] == "Welcome to Test Contract Reviewer!"
    assert "New User" in message.get_payload()[1].get_payload(decode=True).decode()


@pytest.mark.asyncio
async def test_password_reset_email_is_encoded_for_gmail_api(monkeypatch):
    client = FakeAsyncClient(timeout=15.0)
    monkeypatch.setattr(email_module.httpx, "AsyncClient", lambda **kwargs: client)

    await EmailService().send_password_reset_email(
        "user@example.com",
        "https://example.com/reset?token=abc",
    )

    message_bytes = base64.urlsafe_b64decode(client.requests[1]["json"]["raw"] + "===")
    message = message_from_bytes(message_bytes)
    html_content = message.get_payload()[1].get_payload(decode=True).decode()
    assert message["To"] == "user@example.com"
    assert "https://example.com/reset?token=abc" in html_content


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "args", "subject_part", "html_part"),
    [
        ("send_otp_email", ("user@example.com", "123456", "registration"), "Verification Code", "123456"),
        (
            "send_email_changed_notification",
            ("user@example.com", "Reviewer", "new@example.com"),
            "Email Address Has Been Changed",
            "new@example.com",
        ),
        (
            "send_password_changed_notification",
            ("user@example.com", "Reviewer"),
            "Password Has Been Changed",
            "Reviewer",
        ),
        (
            "send_username_changed_notification",
            ("user@example.com", "old-name", "new-name"),
            "Username Has Been Changed",
            "new-name",
        ),
    ],
)
async def test_notification_templates_use_gmail_transport(
    monkeypatch, method_name, args, subject_part, html_part
):
    client = FakeAsyncClient(timeout=15.0)
    monkeypatch.setattr(email_module.httpx, "AsyncClient", lambda **kwargs: client)

    await getattr(EmailService(), method_name)(*args)

    assert len(client.requests) == 2
    message_bytes = base64.urlsafe_b64decode(client.requests[1]["json"]["raw"] + "===")
    message = message_from_bytes(message_bytes)
    assert message["To"] == "user@example.com"
    assert subject_part in message["Subject"]
    assert html_part in message.get_payload()[1].get_payload(decode=True).decode()


@pytest.mark.asyncio
async def test_gmail_api_forbidden_error_is_reported(monkeypatch):
    class RejectingClient(FakeAsyncClient):
        async def post(self, url, **kwargs):
            if url == email_module.GMAIL_TOKEN_URL:
                response = httpx.Response(
                    200,
                    json={"access_token": "test-access-token"},
                    request=httpx.Request("POST", url),
                )
                return response
            request = httpx.Request("POST", url)
            response = httpx.Response(
                403,
                json={"error": {"message": "Gmail API has not been enabled"}},
                request=request,
            )
            raise httpx.HTTPStatusError(
                "Gmail rejected request", request=request, response=response
            )

    monkeypatch.setattr(email_module.httpx, "AsyncClient", RejectingClient)
    log_error = Mock()
    monkeypatch.setattr(email_module.logger, "error", log_error)

    with pytest.raises(HTTPException) as error:
        await EmailService().send_welcome_email("user@example.com", "User")

    assert error.value.status_code == 502
    assert "Gmail API is enabled" in error.value.detail
    assert log_error.call_args.kwargs["extra"]["provider_message"] == (
        "Gmail API has not been enabled"
    )


@pytest.mark.asyncio
async def test_gmail_oauth_failure_is_reported(monkeypatch):
    class InvalidTokenClient(FakeAsyncClient):
        async def post(self, url, **kwargs):
            request = httpx.Request("POST", url)
            response = httpx.Response(
                400,
                json={"error": "invalid_grant"},
                request=request,
            )
            raise httpx.HTTPStatusError(
                "OAuth refresh failed", request=request, response=response
            )

    monkeypatch.setattr(email_module.httpx, "AsyncClient", InvalidTokenClient)

    with pytest.raises(HTTPException) as error:
        await EmailService().send_welcome_email("user@example.com", "User")

    assert error.value.status_code == 503
    assert "refresh token" in error.value.detail


@pytest.mark.asyncio
async def test_gmail_network_failure_is_reported(monkeypatch):
    class UnavailableClient(FakeAsyncClient):
        async def post(self, url, **kwargs):
            request = httpx.Request("POST", url)
            raise httpx.ConnectTimeout("Google timed out", request=request)

    monkeypatch.setattr(email_module.httpx, "AsyncClient", UnavailableClient)

    with pytest.raises(HTTPException) as error:
        await EmailService().send_welcome_email("user@example.com", "User")

    assert error.value.status_code == 502
    assert error.value.detail == "Google email service could not be reached."


@pytest.mark.asyncio
async def test_email_service_fails_explicitly_when_not_configured(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "GMAIL_REFRESH_TOKEN", None)

    with pytest.raises(HTTPException) as error:
        await EmailService().send_welcome_email("user@example.com", "User")

    assert error.value.status_code == 503
    assert error.value.detail == "Email service is not configured."


@pytest.mark.asyncio
async def test_admin_change_notification_uses_async_email_transport():
    service = EmailService()
    service.send_email = AsyncMock()

    await service.send_admin_change_notification(
        "user@example.com",
        "Example User",
        "An administrator changed your account role.",
        "Your role is now <administrator>.",
    )

    service.send_email.assert_awaited_once()
    recipients, subject, body = service.send_email.await_args.args
    assert recipients == ["user@example.com"]
    assert "administrator" in subject
    assert "Example User" in body
    assert "&lt;administrator&gt;" in body
