import logging
from typing import Optional

from fastapi_mail import FastMail, ConnectionConfig
from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailSetup:
    """
    Email setup manager class using fastapi-mail.
    Handles initialization, closing, and retrieving FastMail instance.
    """

    def __init__(self) -> None:
        self.fastmail: Optional[FastMail] = None
        self.config: Optional[ConnectionConfig] = None
        self.is_initialized: bool = False

    async def initialize_email(self) -> None:
        """
        Initialize ConnectionConfig and FastMail instance using settings.
        """
        try:
            self.config = ConnectionConfig(
                MAIL_USERNAME=settings.MAIL_USERNAME or "",
                MAIL_PASSWORD=settings.MAIL_PASSWORD or "",
                MAIL_FROM=settings.MAIL_FROM,
                MAIL_PORT=settings.MAIL_PORT,
                MAIL_SERVER=settings.MAIL_SERVER,
                MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
                MAIL_STARTTLS=settings.MAIL_STARTTLS,
                MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
                USE_CREDENTIALS=bool(settings.MAIL_USERNAME and settings.MAIL_PASSWORD),
                VALIDATE_CERTS=True
            )
            self.fastmail = FastMail(self.config)
            self.is_initialized = True
            logger.info(f"Successfully initialized FastMail setup with server {settings.MAIL_SERVER}:{settings.MAIL_PORT}")
        except Exception as e:
            logger.error(f"Failed to initialize FastMail setup: {e}")
            self.fastmail = None
            self.config = None
            self.is_initialized = False
            raise e

    async def close_email(self) -> None:
        """
        Close and clear FastMail configuration and resources gracefully.
        """
        if self.is_initialized:
            try:
                self.fastmail = None
                self.config = None
                self.is_initialized = False
                logger.info("FastMail setup closed gracefully.")
            except Exception as e:
                logger.error(f"Error while closing FastMail setup: {e}")
            finally:
                self.fastmail = None
                self.config = None
                self.is_initialized = False

    def get_email(self) -> FastMail:
        """
        Returns the initialized FastMail instance.
        Raises RuntimeError if email setup has not been initialized.
        """
        if not self.is_initialized or self.fastmail is None:
            raise RuntimeError("Email setup is not initialized. Call initialize_email() first.")
        return self.fastmail


# Default global instance
email_setup = EmailSetup()


# Module-level wrapper functions
async def initialize_email() -> None:
    await email_setup.initialize_email()


async def close_email() -> None:
    await email_setup.close_email()


def get_email() -> FastMail:
    return email_setup.get_email()
