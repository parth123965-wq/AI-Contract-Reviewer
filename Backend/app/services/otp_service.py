import logging
import secrets
from typing import Tuple
from fastapi import HTTPException, status
from fastapi_mail import MessageSchema, MessageType

from app.core.config import settings
from app.core.redis_setup import get_redis
from app.core.email_setup import get_email
from app.services.email_service import email_service

logger = logging.getLogger(__name__)


class OTPService:
    """
    Service for managing OTP lifecycle with Redis storage and email dispatch.
    
    Redis Key Patterns:
    - Code:     otp:{purpose}:{identifier}:code
    - Attempts: otp:{purpose}:{identifier}:attempts
    - Cooldown: otp:{purpose}:{identifier}:cooldown
    """

    def _get_keys(self, purpose: str, identifier: str) -> Tuple[str, str, str]:
        """
        Build Redis keys for code, attempts, and cooldown.
        """
        clean_purpose = purpose.strip().lower()
        clean_identifier = identifier.strip().lower()
        code_key = f"otp:{clean_purpose}:{clean_identifier}:code"
        attempts_key = f"otp:{clean_purpose}:{clean_identifier}:attempts"
        cooldown_key = f"otp:{clean_purpose}:{clean_identifier}:cooldown"
        return code_key, attempts_key, cooldown_key

    async def generate_otp(self, purpose: str, identifier: str) -> str:
        """
        Generate a secure numeric OTP, enforce cooldown, and store in Redis.
        """
        redis = get_redis()
        code_key, attempts_key, cooldown_key = self._get_keys(purpose, identifier)

        # Check cooldown
        if await redis.exists(cooldown_key):
            ttl = await redis.ttl(cooldown_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {ttl if ttl > 0 else settings.OTP_COOLDOWN_SECONDS} seconds before requesting a new OTP."
            )

        # Generate OTP string
        digits = "0123456789"
        otp_code = "".join(secrets.choice(digits) for _ in range(settings.OTP_LENGTH))

        # Store OTP and cooldown in Redis
        await redis.set(code_key, otp_code, ex=settings.OTP_EXPIRE_SECONDS)
        await redis.set(cooldown_key, "1", ex=settings.OTP_COOLDOWN_SECONDS)
        await redis.delete(attempts_key)

        logger.info(f"Generated OTP for purpose '{purpose}' and identifier '{identifier}'")
        return otp_code

    async def verify_otp(self, purpose: str, identifier: str, input_otp: str) -> bool:
        """
        Verify the provided OTP against Redis storage with attempt limit tracking.
        """
        redis = get_redis()
        code_key, attempts_key, cooldown_key = self._get_keys(purpose, identifier)

        # Check attempt count
        attempts_str = await redis.get(attempts_key)
        current_attempts = int(attempts_str) if attempts_str else 0

        if current_attempts >= settings.OTP_MAX_ATTEMPTS:
            await redis.delete(code_key, attempts_key)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum OTP verification attempts exceeded. Please request a new OTP."
            )

        stored_otp = await redis.get(code_key)

        if not stored_otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP is invalid or has expired."
            )

        if secrets.compare_digest(stored_otp.strip(), input_otp.strip()):
            # Successful verification: cleanup Redis keys
            await redis.delete(code_key, attempts_key, cooldown_key)
            logger.info(f"Successfully verified OTP for purpose '{purpose}' and identifier '{identifier}'")
            return True

        # Incorrect OTP: increment attempts
        new_attempts = await redis.incr(attempts_key)
        if new_attempts == 1:
            await redis.expire(attempts_key, settings.OTP_EXPIRE_SECONDS)

        remaining = settings.OTP_MAX_ATTEMPTS - new_attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OTP code. {remaining} attempt(s) remaining."
        )

    async def send_otp_email(self, email: str, otp_code: str, purpose: str = "verification") -> None:
        """
        Dispatch the OTP code to the target email address using EmailService template rendering.
        """
        await email_service.send_otp_email(email=email, otp_code=otp_code, purpose=purpose)


# Default service instance
otp_service = OTPService()
