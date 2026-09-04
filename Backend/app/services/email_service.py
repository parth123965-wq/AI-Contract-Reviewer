import logging
from pathlib import Path
from typing import Any, Dict
from fastapi import HTTPException, status
from fastapi_mail import MessageSchema, MessageType
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings
from app.core.email_setup import get_email

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class EmailService:
    """
    Centralized email service for rendering HTML templates in app/templates
    and dispatching emails via FastMail.
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
        Send HTML email message using FastMail instance.
        """
        try:
            fastmail = get_email()
            message = MessageSchema(
                subject=subject,
                recipients=recipients,
                body=body_html,
                subtype=MessageType.html
            )
            await fastmail.send_message(message)
            logger.info(f"Email sent successfully to {recipients}")
        except Exception as e:
            logger.error(f"Failed to send email to {recipients}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send email message."
            )

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


# Default service instance
email_service = EmailService()
