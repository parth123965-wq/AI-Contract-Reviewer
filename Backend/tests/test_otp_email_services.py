import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.services.otp_service import OTPService, otp_service
from app.services.email_service import EmailService, email_service


class FakeRedis:
    """In-memory Async Redis Mock for OTPService testing."""
    def __init__(self):
        self.store = {}

    async def exists(self, key: str) -> bool:
        return key in self.store

    async def ttl(self, key: str) -> int:
        return 60 if key in self.store else -2

    async def set(self, key: str, value: str, ex: int = None):
        self.store[key] = str(value)

    async def get(self, key: str):
        return self.store.get(key)

    async def delete(self, *keys: str):
        for k in keys:
            self.store.pop(k, None)

    async def incr(self, key: str) -> int:
        val = int(self.store.get(key, 0)) + 1
        self.store[key] = str(val)
        return val

    async def expire(self, key: str, seconds: int):
        pass


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.mark.asyncio
async def test_otp_generate_and_verify_success(fake_redis):
    service = OTPService()

    with patch("app.services.otp_service.get_redis", return_value=fake_redis):
        otp = await service.generate_otp(purpose="registration", identifier="user@example.com")
        assert len(otp) == 6
        assert otp.isdigit()

        verified = await service.verify_otp(purpose="registration", identifier="user@example.com", input_otp=otp)
        assert verified is True


@pytest.mark.asyncio
async def test_otp_cooldown_error(fake_redis):
    service = OTPService()

    with patch("app.services.otp_service.get_redis", return_value=fake_redis):
        await service.generate_otp(purpose="registration", identifier="cooldown@example.com")

        with pytest.raises(HTTPException) as exc_info:
            await service.generate_otp(purpose="registration", identifier="cooldown@example.com")

        assert exc_info.value.status_code == 429
        assert "Please wait" in exc_info.value.detail


@pytest.mark.asyncio
async def test_otp_invalid_code(fake_redis):
    service = OTPService()

    with patch("app.services.otp_service.get_redis", return_value=fake_redis):
        await service.generate_otp(purpose="login", identifier="invalid@example.com")

        with pytest.raises(HTTPException) as exc_info:
            await service.verify_otp(purpose="login", identifier="invalid@example.com", input_otp="000000")

        assert exc_info.value.status_code == 400
        assert "Invalid OTP code" in exc_info.value.detail


@pytest.mark.asyncio
async def test_otp_expired_code(fake_redis):
    service = OTPService()

    with patch("app.services.otp_service.get_redis", return_value=fake_redis):
        with pytest.raises(HTTPException) as exc_info:
            await service.verify_otp(purpose="login", identifier="expired@example.com", input_otp="123456")

        assert exc_info.value.status_code == 400
        assert "OTP is invalid or has expired." in exc_info.value.detail


@pytest.mark.asyncio
async def test_otp_max_attempts_exceeded(fake_redis):
    service = OTPService()

    with patch("app.services.otp_service.get_redis", return_value=fake_redis):
        await service.generate_otp(purpose="login", identifier="max@example.com")

        # Fake 5 failed attempts
        code_key, attempts_key, cooldown_key = service._get_keys("login", "max@example.com")
        fake_redis.store[attempts_key] = "5"

        with pytest.raises(HTTPException) as exc_info:
            await service.verify_otp(purpose="login", identifier="max@example.com", input_otp="123456")

        assert exc_info.value.status_code == 400
        assert "Maximum OTP verification attempts exceeded" in exc_info.value.detail


@pytest.mark.asyncio
async def test_email_service_render_templates():
    service = EmailService()
    welcome_html = service._render_template("welcome.html", {"name": "Alex"})
    assert "Alex" in welcome_html

    otp_html = service._render_template("otp.html", {"otp_code": "987654", "purpose": "Testing", "expire_minutes": 5})
    assert "987654" in otp_html
    assert "Testing" in otp_html


@pytest.mark.asyncio
async def test_email_service_send_email_success():
    service = EmailService()
    mock_fastmail = AsyncMock()

    with patch("app.services.email_service.get_email", return_value=mock_fastmail):
        await service.send_email(recipients=["test@example.com"], subject="Test", body_html="<h1>Hello</h1>")
        assert mock_fastmail.send_message.called


@pytest.mark.asyncio
async def test_email_service_send_email_failure():
    service = EmailService()
    mock_fastmail = AsyncMock()
    mock_fastmail.send_message.side_effect = Exception("SMTP Connection Failed")

    with patch("app.services.email_service.get_email", return_value=mock_fastmail):
        with pytest.raises(HTTPException) as exc_info:
            await service.send_email(recipients=["fail@example.com"], subject="Test", body_html="<p>Fail</p>")
        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to send email message."


@pytest.mark.asyncio
async def test_email_service_convenience_methods():
    service = EmailService()

    with patch.object(service, "send_email", new_callable=AsyncMock) as mock_send:
        await service.send_welcome_email(email="welcome@example.com", name="John")
        assert mock_send.called

        await service.send_otp_email(email="otp@example.com", otp_code="123456")
        assert mock_send.called

        await service.send_password_reset_email(email="reset@example.com", reset_url="http://reset.link")
        assert mock_send.called

        await service.send_email_changed_notification(email="changed@example.com", username="john", new_email="changed@example.com")
        assert mock_send.called

        await service.send_password_changed_notification(email="pass@example.com", username="john")
        assert mock_send.called
