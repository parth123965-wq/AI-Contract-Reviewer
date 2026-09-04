from fastapi import APIRouter, Depends
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import (
    UserResponse,
    UpdateUsernameRequest,
    RequestEmailChangeRequest,
    VerifyEmailChangeRequest,
    VerifyPasswordChangeRequest
)
from app.services.user_service import UserService, get_user_service

users_router = APIRouter(
    prefix='/users',
    tags=['Users']
)

@users_router.get('/me', response_model=UserResponse)
async def get_profile(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user

@users_router.patch('/me/username', response_model=UserResponse)
async def update_username(
    request: UpdateUsernameRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    return await user_service.update_username(db=db, current_user=current_user, request=request)

@users_router.post('/me/email/request')
async def request_email_change(
    request: RequestEmailChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    return await user_service.request_email_change(db=db, current_user=current_user, request=request)

@users_router.post('/me/email/confirm', response_model=UserResponse)
async def confirm_email_change(
    request: VerifyEmailChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    return await user_service.confirm_email_change(db=db, current_user=current_user, request=request)

@users_router.post('/me/password/request')
async def request_password_change(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    return await user_service.request_password_change(db=db, current_user=current_user)

@users_router.post('/me/password/confirm')
async def confirm_password_change(
    request: VerifyPasswordChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    return await user_service.confirm_password_change(db=db, current_user=current_user, request=request)