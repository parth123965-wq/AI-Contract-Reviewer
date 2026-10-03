from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from app.services import email_service as email_module
from app.services.email_service import EmailService


class FakeAsyncClient:
    def __init__(self, *, timeout):
        self.timeout = timeout
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, *, headers, json):
        self.request = {
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": self.timeout,
        }
        response = httpx.Response(200, json={"id": "email-id"}, request=httpx.Request("POST", url))
        response.raise_for_status()
        return response


@pytest.mark.asyncio
async def test_welcome_email_renders_name_and_sends_through_resend(monkeypatch):
    client = FakeAsyncClient(timeout=10.0)
    monkeypatch.setattr(email_module.httpx, "AsyncClient", lambda **kwargs: client)

    await EmailService().send_welcome_email("new@example.com", "New User")

    assert client.request["url"] == "https://api.resend.com/emails"
    assert client.request["headers"]["Authorization"] == "Bearer test-resend-key"
    assert client.request["json"]["to"] == ["new@example.com"]
    assert client.request["json"]["from"] == "Test Contract Reviewer <test@example.com>"
    assert client.request["json"]["subject"] == "Welcome to Test Contract Reviewer!"
    assert "New User" in client.request["json"]["html"]
    assert client.request["timeout"] == 10.0


@pytest.mark.asyncio
async def test_password_reset_email_renders_reset_link_for_resend(monkeypatch):
    client = FakeAsyncClient(timeout=10.0)
    monkeypatch.setattr(email_module.httpx, "AsyncClient", lambda **kwargs: client)

    await EmailService().send_password_reset_email(
        "user@example.com",
        "https://example.com/reset?token=abc",
    )

    assert client.request["json"]["to"] == ["user@example.com"]
    assert "https://example.com/reset?token=abc" in client.request["json"]["html"]


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
async def test_notification_templates_use_resend_transport(
    monkeypatch, method_name, args, subject_part, html_part
):
    client = FakeAsyncClient(timeout=10.0)
    monkeypatch.setattr(email_module.httpx, "AsyncClient", lambda **kwargs: client)

    await getattr(EmailService(), method_name)(*args)

    assert client.request["url"] == "https://api.resend.com/emails"
    assert client.request["json"]["to"] == ["user@example.com"]
    assert subject_part in client.request["json"]["subject"]
    assert html_part in client.request["json"]["html"]


@pytest.mark.asyncio
async def test_email_provider_http_failure_is_reported(monkeypatch):
    class RejectingClient(FakeAsyncClient):
        async def post(self, url, *, headers, json):
            request = httpx.Request("POST", url)
            response = httpx.Response(403, json={"message": "not authorized"}, request=request)
            raise httpx.HTTPStatusError("provider rejected request", request=request, response=response)

    monkeypatch.setattr(email_module.httpx, "AsyncClient", RejectingClient)

    with pytest.raises(HTTPException) as error:
        await EmailService().send_welcome_email("user@example.com", "User")

    assert error.value.status_code == 502
    assert error.value.detail == "Email provider rejected the message."


@pytest.mark.asyncio
async def test_email_provider_network_failure_is_reported(monkeypatch):
    class UnavailableClient(FakeAsyncClient):
        async def post(self, url, *, headers, json):
            request = httpx.Request("POST", url)
            raise httpx.ConnectTimeout("provider timed out", request=request)

    monkeypatch.setattr(email_module.httpx, "AsyncClient", UnavailableClient)

    with pytest.raises(HTTPException) as error:
        await EmailService().send_welcome_email("user@example.com", "User")

    assert error.value.status_code == 502
    assert error.value.detail == "Email provider could not be reached."


@pytest.mark.asyncio
async def test_email_service_fails_explicitly_when_not_configured(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "RESEND_API_KEY", None)

    with pytest.raises(HTTPException) as error:
        await EmailService().send_welcome_email("user@example.com", "User")

    assert error.value.status_code == 503
    assert error.value.detail == "Email service is not configured."
