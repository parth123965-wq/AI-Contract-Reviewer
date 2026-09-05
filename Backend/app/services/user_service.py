from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.auth.password import hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.otp_service import otp_service
from app.services.email_service import email_service
from app.schemas.user import (
    UserResponse,
    UpdateUsernameRequest,
    RequestEmailChangeRequest,
    VerifyEmailChangeRequest,
    VerifyPasswordChangeRequest
)

class UserService:
    def __init__(self):
        self.user_repository = UserRepository()

    async def update_username(
        self, db: AsyncSession, current_user: User, request: UpdateUsernameRequest
    ) -> UserResponse:
        new_username = request.username.strip()
        if new_username == current_user.username:
            return UserResponse.model_validate(current_user)

        existing_user = await self.user_repository.get_user_by_username(db=db, username=new_username)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already taken."
            )

        current_user.username = new_username
        updated_user = await self.user_repository.update_user(db=db, user=current_user)
        return UserResponse.model_validate(updated_user)

    async def request_email_change(
        self, db: AsyncSession, current_user: User, request: RequestEmailChangeRequest
    ) -> dict:
        new_email = request.new_email.lower().strip()
        if new_email == current_user.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New email must be different from current email."
            )

        existing_user = await self.user_repository.get_user_by_email(db=db, email=new_email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered by another account."
            )

        otp_code = await otp_service.generate_otp(purpose="email_change", identifier=new_email)
        await otp_service.send_otp_email(email=new_email, otp_code=otp_code, purpose="email_change")
        return {"message": f"Verification OTP sent to {new_email}."}

    async def confirm_email_change(
        self, db: AsyncSession, current_user: User, request: VerifyEmailChangeRequest
    ) -> UserResponse:
        new_email = request.new_email.lower().strip()
        existing_user = await self.user_repository.get_user_by_email(db=db, email=new_email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered by another account."
            )

        await otp_service.verify_otp(purpose="email_change", identifier=new_email, input_otp=request.otp_code)

        old_email = current_user.email
        current_user.email = new_email
        updated_user = await self.user_repository.update_user(db=db, user=current_user)

        # Notify user about email change (sent to new email address)
        try:
            await email_service.send_email_changed_notification(
                email=new_email,
                username=current_user.username,
                new_email=new_email
            )
        except Exception:
            pass

        return UserResponse.model_validate(updated_user)

    async def request_password_change(
        self, db: AsyncSession, current_user: User
    ) -> dict:
        otp_code = await otp_service.generate_otp(purpose="password_change", identifier=current_user.email)
        await otp_service.send_otp_email(email=current_user.email, otp_code=otp_code, purpose="password_change")
        return {"message": f"Verification OTP sent to {current_user.email}."}

    async def confirm_password_change(
        self, db: AsyncSession, current_user: User, request: VerifyPasswordChangeRequest
    ) -> dict:
        if not verify_password(password=request.current_password, password_hash_value=current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password."
            )

        if request.current_password == request.new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be different from current password."
            )

        await otp_service.verify_otp(purpose="password_change", identifier=current_user.email, input_otp=request.otp_code)

        current_user.password_hash = hash_password(password=request.new_password)
        await self.user_repository.update_user(db=db, user=current_user)

        # Notify user about password change
        try:
            await email_service.send_password_changed_notification(
                email=current_user.email,
                username=current_user.username
            )
        except Exception:
            pass

        return {"message": "Password changed successfully."}

def get_user_service() -> UserService:
    return UserService()

