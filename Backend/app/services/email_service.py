from pathlib import Path
from typing import Any, Dict

import httpx
from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings
from app.core.logger import get_app_logger

logger = get_app_logger("services.email")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"



class EmailService:
    """Render email templates and dispatch messages through the Brevo API."""

    def __init__(self) -> None:
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        try:
            context["app_name"] = getattr(settings, "APP_NAME", "AI Contract Reviewer")
            template = self.jinja_env.get_template(template_name)
            return template.render(**context)
        except Exception:
            logger.exception("Failed to render email template %s.", template_name)
            raise

    async def send_email(
        self, recipients: list[str], subject: str, body_html: str
    ) -> None:
        """Send an HTML email through Brevo using the configured verified sender."""
        if not settings.BREVO_API_KEY or not settings.GMAIL_SENDER:
            logger.error(
                "Email delivery is not configured: Brevo API key or sender is missing."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email service is not configured.",
            )

        payload = {
            "sender": {
                "name": settings.APP_NAME,
                "email": settings.GMAIL_SENDER,
            },
            "to": [{"email": recipient} for recipient in recipients],
            "subject": subject,
            "htmlContent": body_html,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    settings.BREVO_SEND_URL,
                    headers={
                        "api-key": settings.BREVO_API_KEY,
                        "accept": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
            logger.info("Email accepted by Brevo for %s", recipients)
        except httpx.HTTPStatusError as exc:
            try:
                provider_response = exc.response.json()
            except ValueError:
                provider_response = {}
            provider_message = None
            if isinstance(provider_response, dict):
                provider_message = (
                    provider_response.get("message")
                    or provider_response.get("error")
                )
            logger.error(
                "Brevo API rejected email delivery.",
                extra={
                    "status_code": exc.response.status_code,
                    "endpoint": str(exc.request.url),
                    "provider_message": (
                        str(provider_message)[:500] if provider_message else None
                    ),
                    "recipients": recipients,
                },
            )
            if exc.response.status_code in {
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            }:
                detail = (
                    "Brevo rejected email sending. Check the API key and verify that "
                    "the configured sender address is active in Brevo."
                )
            else:
                detail = "Brevo API rejected the email."
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=detail,
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "Brevo API request failed.",
                extra={"error_type": type(exc).__name__, "recipients": recipients},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Brevo email service could not be reached.",
            ) from exc
        except Exception as exc:
            logger.exception(
                "Unexpected error while sending email via Brevo.",
                extra={"recipients": recipients},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email message.",
            ) from exc

    async def send_welcome_email(self, email: str, name: str) -> None:
        html_content = self._render_template("welcome.html", {"name": name})
        subject = f"Welcome to {settings.APP_NAME}!"
        await self.send_email([email], subject, html_content)

    async def send_otp_email(
        self, email: str, otp_code: str, purpose: str = "verification"
    ) -> None:
        expire_minutes = getattr(settings, "OTP_EXPIRE_SECONDS", 300) // 60
        html_content = self._render_template(
            "otp.html",
            {
                "otp_code": otp_code,
                "purpose": purpose.capitalize(),
                "expire_minutes": expire_minutes,
            },
        )
        subject = f"Your {settings.APP_NAME} Verification Code"
        await self.send_email([email], subject, html_content)

    async def send_password_reset_email(self, email: str, reset_url: str) -> None:
        html_content = self._render_template(
            "password_reset.html", {"reset_url": reset_url}
        )
        subject = f"Reset Your Password - {settings.APP_NAME}"
        await self.send_email([email], subject, html_content)

    async def send_email_changed_notification(
        self, email: str, username: str, new_email: str
    ) -> None:
        html_content = self._render_template(
            "email_changed.html",
            {"username": username, "new_email": new_email},
        )
        subject = f"Your {settings.APP_NAME} Email Address Has Been Changed"
        await self.send_email([email], subject, html_content)

    async def send_password_changed_notification(self, email: str, username: str) -> None:
        html_content = self._render_template(
            "password_changed.html", {"username": username}
        )
        subject = f"Your {settings.APP_NAME} Password Has Been Changed"
        await self.send_email([email], subject, html_content)

    async def send_username_changed_notification(
        self, email: str, old_username: str, new_username: str
    ) -> None:
        html_content = self._render_template(
            "username_changed.html",
            {"old_username": old_username, "new_username": new_username},
        )
        subject = f"Your {settings.APP_NAME} Username Has Been Changed"
        await self.send_email([email], subject, html_content)

    async def send_admin_change_notification(
        self,
        email: str,
        username: str,
        action: str,
        details: str,
    ) -> None:
        html_content = self._render_template(
            "admin_change_notification.html",
            {
                "username": username,
                "action": action,
                "details": details,
            },
        )
        subject = f"An administrator updated your {settings.APP_NAME} account"
        await self.send_email([email], subject, html_content)


email_service = EmailService()
