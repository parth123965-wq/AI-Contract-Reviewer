from typing import Awaitable, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.auth.password import hash_password , verify_password
from app.schemas.user import UserCreate , UserLogin , LoginResponse , UserResponse
from app.models.user import User
from app.repositories.user_repository import UserRepository
from fastapi import HTTPException, status
from app.auth.jwt import create_access_token
from app.services.otp_service import otp_service
from app.services.email_service import email_service
from app.core.logger import get_app_logger

logger = get_app_logger("services.auth")
T = TypeVar("T")

class AuthService:
    
    def __init__(self):
        self.user_repository = UserRepository()

    async def _persist_registration(
        self, db: AsyncSession, operation: Awaitable[T]
    ) -> T:
        try:
            return await operation
        except IntegrityError as exc:
            await db.rollback()
            original_error = exc.orig
            sql_state = (
                getattr(original_error, "sqlstate", None)
                or getattr(original_error, "pgcode", None)
            )
            error_message = str(original_error).lower()
            if (
                sql_state == "23505"
                or "unique constraint failed" in error_message
                or "duplicate key value violates unique constraint" in error_message
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email or username is already registered."
                ) from exc
            raise
        
    async def register_user(self, db: AsyncSession, user: UserCreate) -> User:
        existing_user = await self.user_repository.get_user_by_email(db=db, email=user.email)
        if existing_user is not None and existing_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Email already registered'
            )

        username_owner = await self.user_repository.get_user_by_username(
            db=db,
            username=user.username
        )
        if username_owner is not None and (
            existing_user is None or username_owner.id != existing_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username is already registered."
            )
        hashed_password = hash_password(password=user.password)

        if existing_user is not None:
            # Unverified existing user: update details for re-registration
            existing_user.username = user.username
            existing_user.password_hash = hashed_password
            await self._persist_registration(db, db.commit())
            await db.refresh(existing_user)
            saved_user = existing_user
        else:
            new_user = User(
                username=user.username,
                email=user.email,
                password_hash=hashed_password,
                is_verified=False
            )
            saved_user = await self._persist_registration(
                db,
                self.user_repository.create_user(db=db, user=new_user)
            )

        # Generate and dispatch OTP
        otp_code = await otp_service.generate_otp(purpose="registration", identifier=saved_user.email)
        await otp_service.send_otp_email(email=saved_user.email, otp_code=otp_code, purpose="registration")

        return saved_user

    async def verify_registration(self, db: AsyncSession, email: str, otp_code: str) -> User:
        existing_user = await self.user_repository.get_user_by_email(db=db, email=email)
        if existing_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )

        if existing_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already verified."
            )

        # Verify OTP code via OTP service
        await otp_service.verify_otp(purpose="registration", identifier=email, input_otp=otp_code)

        # Mark user as verified in database
        verified_user = await self.user_repository.mark_user_verified(db=db, user_id=existing_user.id)
        if verified_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )

        await email_service.send_welcome_email(
            email=verified_user.email,
            name=verified_user.username
        )
        return verified_user

    async def request_password_reset(self, db: AsyncSession, email: str) -> None:
        normalized_email = email.strip().lower()
        user = await self.user_repository.get_user_by_email(
            db=db,
            email=normalized_email
        )
        if user is None or not user.is_active or not user.is_verified:
            return

        try:
            otp_code = await otp_service.generate_otp(
                purpose="password_reset",
                identifier=normalized_email
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                return
            raise

        await otp_service.send_otp_email(
            email=user.email,
            otp_code=otp_code,
            purpose="password reset"
        )

    async def reset_password(
        self,
        db: AsyncSession,
        email: str,
        otp_code: str,
        new_password: str
    ) -> None:
        normalized_email = email.strip().lower()
        user = await self.user_repository.get_user_by_email(
            db=db,
            email=normalized_email
        )
        if user is None or not user.is_active or not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset code."
            )

        await otp_service.verify_otp(
            purpose="password_reset",
            identifier=normalized_email,
            input_otp=otp_code
        )

        user.password_hash = hash_password(new_password)
        await self.user_repository.update_user(db=db, user=user)
        await email_service.send_password_changed_notification(
            email=user.email,
            username=user.username
        )

    async def resend_registration_otp(self, db: AsyncSession, email: str) -> None:
        existing_user = await self.user_repository.get_user_by_email(db=db, email=email)
        if existing_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )

        if existing_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already verified."
            )

        otp_code = await otp_service.generate_otp(purpose="registration", identifier=email)
        await otp_service.send_otp_email(email=email, otp_code=otp_code, purpose="registration")

    async def login_user(self, db: AsyncSession, user: UserLogin) -> LoginResponse:
        existing_user = await self.user_repository.get_user_by_email(db=db, email=user.email)
        if existing_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Email and Password."
            )
        if not verify_password(password=user.password, password_hash_value=existing_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Email and Password."
            )
        if not existing_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email address is not verified. Please verify your account with OTP."
            )
        token = create_access_token(data={'sub': str(existing_user.id)})
        return LoginResponse(
            access_token=token,
            token_type='bearer',
            user=UserResponse.model_validate(existing_user)
        )
    
def auth_service() -> AuthService:
    return AuthService() 