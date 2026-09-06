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
from app.core.rate_limit import RateLimiter

users_router = APIRouter(
    prefix='/users',
    tags=['Users']
)

@users_router.get(
    '/me',
    response_model=UserResponse,
    summary="Get Current User Profile",
    description="Retrieve account details and metadata for the currently authenticated user.",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="users_me"))]
)
async def get_profile(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user

@users_router.patch(
    '/me/username',
    response_model=UserResponse,
    summary="Update Username",
    description="Update the display username for the authenticated user.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="users_username"))]
)
async def update_username(
    request: UpdateUsernameRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    return await user_service.update_username(db=db, current_user=current_user, request=request)

@users_router.post(
    '/me/email/request',
    summary="Request Email Address Change",
    description="Initiate an email address change request. Dispatches a 6-digit OTP code to the new target email address.",
    dependencies=[Depends(RateLimiter(times=5, seconds=60, prefix="users_email_req"))]
)
async def request_email_change(
    request: RequestEmailChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    return await user_service.request_email_change(db=db, current_user=current_user, request=request)

@users_router.post(
    '/me/email/confirm',
    response_model=UserResponse,
    summary="Confirm Email Address Change",
    description="Verify the OTP code sent to the new email address to complete the email change workflow.",
    dependencies=[Depends(RateLimiter(times=10, seconds=60, prefix="users_email_confirm"))]
)
async def confirm_email_change(
    request: VerifyEmailChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    return await user_service.confirm_email_change(db=db, current_user=current_user, request=request)

@users_router.post(
    '/me/password/request',
    summary="Request Password Change OTP",
    description="Initiate a password change workflow. Dispatches a 6-digit verification OTP code to the user's primary email.",
    dependencies=[Depends(RateLimiter(times=5, seconds=60, prefix="users_password_req"))]
)
async def request_password_change(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    return await user_service.request_password_change(db=db, current_user=current_user)

@users_router.post(
    '/me/password/confirm',
    summary="Confirm Password Change",
    description="Validate current password, new password, and email OTP code to complete password update.",
    dependencies=[Depends(RateLimiter(times=10, seconds=60, prefix="users_password_confirm"))]
)
async def confirm_password_change(
    request: VerifyPasswordChangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_service: Annotated[UserService, Depends(get_user_service)]
):
    return await user_service.confirm_password_change(db=db, current_user=current_user, request=request)