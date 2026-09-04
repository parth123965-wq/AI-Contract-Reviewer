"""
=========================================================
AUTH DEPENDENCIES

Responsibilities:
- Extract JWT from HttpOnly cookie
- Validate JWT token
- Fetch current authenticated user
- Protect private routes

Cookie:
- ai_contract_session
=========================================================
"""


from typing import Annotated
from fastapi import Depends, HTTPException, status, Request
from app.database.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.auth.jwt import decode_access_token
from app.repositories.user_repository import UserRepository

async def get_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)]
) -> User:

    token = request.cookies.get("ai_contract_session")

    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if token is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    payload = decode_access_token(
        token=token
    )

    if payload is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    user_id = payload.get("sub")

    if user_id is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    user_repository = UserRepository()

    user = await user_repository.get_user_by_id(
        db=db,
        user_id=user_id_int
    )


    if user is None:

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not verified. Please verify your email via OTP."
        )

    return user


# =======================================================
# SECTION 2: CURRENT ADMIN DEPENDENCY
# =======================================================


def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account"
        )

    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )

    return current_user