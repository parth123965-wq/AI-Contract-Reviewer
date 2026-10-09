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
        response = httpx.Response(
            201,
            json={"messageId": "brevo-message-id"},
            request=httpx.Request("POST", url),
        )
        response.raise_for_status()
        return response


@pytest.mark.asyncio
async def test_welcome_email_uses_brevo_api_and_sends_html(monkeypatch):
    client = FakeAsyncClient(timeout=15.0)
    monkeypatch.setattr(email_module.httpx, "AsyncClient", lambda **kwargs: client)

    await EmailService().send_welcome_email("new@example.com", "New User")

    assert len(client.requests) == 1
    request = client.requests[0]
    assert request["url"] == email_module.BREVO_SEND_URL
    assert request["headers"] == {
        "api-key": "test-brevo-key",
        "accept": "application/json",
    }
    assert request["json"]["sender"] == {
        "name": "Test Contract Reviewer",
        "email": "sender@gmail.com",
    }
    assert request["json"]["to"] == [{"email": "new@example.com"}]
    assert request["json"]["subject"] == "Welcome to Test Contract Reviewer!"
    assert "New User" in request["json"]["htmlContent"]


@pytest.mark.asyncio
async def test_password_reset_email_uses_brevo_html_payload(monkeypatch):
    client = FakeAsyncClient(timeout=15.0)
    monkeypatch.setattr(email_module.httpx, "AsyncClient", lambda **kwargs: client)

    await EmailService().send_password_reset_email(
        "user@example.com",
        "https://example.com/reset?token=abc",
    )

    payload = client.requests[0]["json"]
    assert payload["to"] == [{"email": "user@example.com"}]
    assert "https://example.com/reset?token=abc" in payload["htmlContent"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "args", "subject_part", "html_part"),
    [
        (
            "send_otp_email",
            ("user@example.com", "123456", "registration"),
            "Verification Code",
            "123456",
        ),
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
async def test_notification_templates_use_brevo_transport(
    monkeypatch, method_name, args, subject_part, html_part
):
    client = FakeAsyncClient(timeout=15.0)
    monkeypatch.setattr(email_module.httpx, "AsyncClient", lambda **kwargs: client)

    await getattr(EmailService(), method_name)(*args)

    assert len(client.requests) == 1
    payload = client.requests[0]["json"]
    assert payload["to"] == [{"email": "user@example.com"}]
    assert subject_part in payload["subject"]
    assert html_part in payload["htmlContent"]


@pytest.mark.asyncio
async def test_brevo_unauthorized_error_is_reported_without_exposing_api_key(
    monkeypatch,
):
    class RejectingClient(FakeAsyncClient):
        async def post(self, url, **kwargs):
            request = httpx.Request("POST", url)
            response = httpx.Response(
                401,
                json={"code": "unauthorized", "message": "Invalid API key"},
                request=request,
            )
            raise httpx.HTTPStatusError(
                "Brevo rejected request", request=request, response=response
            )

    monkeypatch.setattr(email_module.httpx, "AsyncClient", RejectingClient)
    log_error = Mock()
    monkeypatch.setattr(email_module.logger, "error", log_error)

    with pytest.raises(HTTPException) as error:
        await EmailService().send_welcome_email("user@example.com", "User")

    assert error.value.status_code == 502
    assert "verify that" in error.value.detail
    assert "test-brevo-key" not in error.value.detail
    assert log_error.call_args.kwargs["extra"]["provider_message"] == "Invalid API key"


@pytest.mark.asyncio
async def test_brevo_network_failure_is_reported(monkeypatch):
    class UnavailableClient(FakeAsyncClient):
        async def post(self, url, **kwargs):
            request = httpx.Request("POST", url)
            raise httpx.ConnectTimeout("Brevo timed out", request=request)

    monkeypatch.setattr(email_module.httpx, "AsyncClient", UnavailableClient)

    with pytest.raises(HTTPException) as error:
        await EmailService().send_welcome_email("user@example.com", "User")

    assert error.value.status_code == 502
    assert error.value.detail == "Brevo email service could not be reached."


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_setting", ["BREVO_API_KEY", "GMAIL_SENDER"])
async def test_email_service_fails_explicitly_when_not_configured(
    monkeypatch, missing_setting
):
    from app.core import config

    monkeypatch.setattr(config.settings, missing_setting, None)

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
