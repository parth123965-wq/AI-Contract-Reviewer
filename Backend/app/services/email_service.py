from pathlib import Path
from typing import Any, Dict
from fastapi import HTTPException, status
import httpx
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings
from app.core.logger import get_app_logger

logger = get_app_logger("services.email")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class EmailService:
    """
    Centralized email service for rendering HTML templates in app/templates
    and dispatching emails via the Resend HTTPS API.
    """

    def __init__(self) -> None:
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True
        )

    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render Jinja2 HTML template with context data.
        """
        try:
            context["app_name"] = getattr(settings, "APP_NAME", "AI Contract Reviewer")
            template = self.jinja_env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render email template {template_name}: {e}")
            raise e

    async def send_email(self, recipients: list[str], subject: str, body_html: str) -> None:
        """
        Send an HTML email using Resend's HTTPS API.
        """
        if not settings.RESEND_API_KEY or not settings.EMAIL_FROM:
            logger.error("Email delivery is not configured: Resend API key or sender is missing.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email service is not configured."
            )

        payload = {
            "from": settings.EMAIL_FROM,
            "to": recipients,
            "subject": subject,
            "html": body_html,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    settings.RESEND_EMAILS_URL,
                    headers={
                        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
            logger.info(f"Email sent successfully to {recipients}")
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Resend rejected email delivery.",
                extra={"status_code": exc.response.status_code, "recipients": recipients},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Email provider rejected the message."
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "Resend email request failed.",
                extra={"error_type": type(exc).__name__, "recipients": recipients},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Email provider could not be reached."
            ) from exc
        except Exception as e:
            logger.error(
                "Unexpected error while sending email.",
                extra={"error_type": type(e).__name__, "recipients": recipients},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email message."
            ) from e

    async def send_welcome_email(self, email: str, name: str) -> None:
        """
        Send registration welcome email to newly registered user.
        """
        html_content = self._render_template("welcome.html", {"name": name})
        subject = f"Welcome to {settings.APP_NAME}!"
        await self.send_email(recipients=[email], subject=subject, body_html=html_content)

    async def send_otp_email(self, email: str, otp_code: str, purpose: str = "verification") -> None:
        """
        Send OTP verification email using app/templates/otp.html.
        """
        expire_minutes = getattr(settings, "OTP_EXPIRE_SECONDS", 300) // 60
        html_content = self._render_template(
            "otp.html",
            {
                "otp_code": otp_code,
                "purpose": purpose.capitalize(),
                "expire_minutes": expire_minutes
            }
        )
        subject = f"Your {settings.APP_NAME} Verification Code"
        await self.send_email(recipients=[email], subject=subject, body_html=html_content)

    async def send_password_reset_email(self, email: str, reset_url: str) -> None:
        """
        Send password reset link email using app/templates/password_reset.html.
        """
        html_content = self._render_template("password_reset.html", {"reset_url": reset_url})
        subject = f"Reset Your Password - {settings.APP_NAME}"
        await self.send_email(recipients=[email], subject=subject, body_html=html_content)

    async def send_email_changed_notification(self, email: str, username: str, new_email: str) -> None:
        """
        Send email change notification email using app/templates/email_changed.html.
        """
        html_content = self._render_template(
            "email_changed.html",
            {
                "username": username,
                "new_email": new_email
            }
        )
        subject = f"Your {settings.APP_NAME} Email Address Has Been Changed"
        await self.send_email(recipients=[email], subject=subject, body_html=html_content)

    async def send_password_changed_notification(self, email: str, username: str) -> None:
        """
        Send password changed notification email using app/templates/password_changed.html.
        """
        html_content = self._render_template(
            "password_changed.html",
            {
                "username": username
            }
        )
        subject = f"Your {settings.APP_NAME} Password Has Been Changed"
        await self.send_email(recipients=[email], subject=subject, body_html=html_content)

    async def send_username_changed_notification(self, email: str, old_username: str, new_username: str) -> None:
        """
        Send username change notification email using app/templates/username_changed.html.
        """
        html_content = self._render_template(
            "username_changed.html",
            {
                "old_username": old_username,
                "new_username": new_username
            }
        )
        subject = f"Your {settings.APP_NAME} Username Has Been Changed"
        await self.send_email(recipients=[email], subject=subject, body_html=html_content)


# Default service instance
email_service = EmailService()
