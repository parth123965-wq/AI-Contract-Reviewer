from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.auth.password import hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserResponse, UpdateUsernameRequest, UpdateEmailRequest, ChangePasswordRequest

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

    async def update_email(
        self, db: AsyncSession, current_user: User, request: UpdateEmailRequest
    ) -> UserResponse:
        new_email = request.email.lower().strip()
        if new_email == current_user.email:
            return UserResponse.model_validate(current_user)

        existing_user = await self.user_repository.get_user_by_email(db=db, email=new_email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered by another account."
            )

        current_user.email = new_email
        updated_user = await self.user_repository.update_user(db=db, user=current_user)
        return UserResponse.model_validate(updated_user)

    async def change_password(
        self, db: AsyncSession, current_user: User, request: ChangePasswordRequest
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

        current_user.password_hash = hash_password(password=request.new_password)
        await self.user_repository.update_user(db=db, user=current_user)
        return {"message": "Password changed successfully."}

def get_user_service() -> UserService:
    return UserService()
