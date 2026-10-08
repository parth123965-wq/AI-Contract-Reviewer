import base64
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict

import httpx
from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader

from app.core.config import settings
from app.core.logger import get_app_logger

logger = get_app_logger("services.email")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class EmailService:
    """Render email templates and dispatch messages through the Gmail API."""

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
        """Send an HTML email as the configured Gmail account using OAuth."""
        credentials = (
            settings.GMAIL_CLIENT_ID,
            settings.GMAIL_CLIENT_SECRET,
            settings.GMAIL_REFRESH_TOKEN,
            settings.GMAIL_SENDER,
        )
        if not all(credentials):
            logger.error("Email delivery is not configured: Gmail credentials are missing.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email service is not configured.",
            )

        message = EmailMessage()
        message["From"] = settings.GMAIL_SENDER
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(
            "This message contains HTML content. Please view it in an HTML-capable email client."
        )
        message.add_alternative(body_html, subtype="html")
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        raw_message = encoded_message.rstrip("=")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                token_response = await client.post(
                    GMAIL_TOKEN_URL,
                    data={
                        "client_id": settings.GMAIL_CLIENT_ID,
                        "client_secret": settings.GMAIL_CLIENT_SECRET,
                        "refresh_token": settings.GMAIL_REFRESH_TOKEN,
                        "grant_type": "refresh_token",
                    },
                )
                token_response.raise_for_status()
                access_token = token_response.json().get("access_token")
                if not access_token:
                    logger.error("Google OAuth response did not include an access token.")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Google authorization failed. Reauthorize the Gmail account.",
                    )

                send_response = await client.post(
                    GMAIL_SEND_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={"raw": raw_message},
                )
                send_response.raise_for_status()
            logger.info("Email sent via Gmail API to %s", recipients)
        except httpx.HTTPStatusError as exc:
            try:
                provider_response = exc.response.json()
            except ValueError:
                provider_response = {}
            provider_error = (
                provider_response.get("error")
                if isinstance(provider_response, dict)
                else None
            )
            provider_message = (
                provider_error.get("message")
                if isinstance(provider_error, dict)
                else provider_error
            )
            is_token_error = str(exc.request.url) == GMAIL_TOKEN_URL
            logger.error(
                "Gmail API rejected email delivery.",
                extra={
                    "status_code": exc.response.status_code,
                    "endpoint": str(exc.request.url),
                    "provider_message": (
                        str(provider_message)[:500] if provider_message else None
                    ),
                    "recipients": recipients,
                },
            )
            if is_token_error:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Google OAuth failed. Check the Gmail client credentials and "
                        "refresh token, then authorize again if needed."
                    ),
                ) from exc
            if exc.response.status_code == status.HTTP_403_FORBIDDEN:
                detail = (
                    "Gmail denied email sending. Check that Gmail API is enabled, the "
                    "authorized account has gmail.send permission, and Gmail sending "
                    "limits have not been reached."
                )
            else:
                detail = "Gmail API rejected the email."
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=detail,
            ) from exc
        except httpx.HTTPError as exc:
            logger.error(
                "Gmail API request failed.",
                extra={"error_type": type(exc).__name__, "recipients": recipients},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Google email service could not be reached.",
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "Unexpected error while sending email via Gmail API.",
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
