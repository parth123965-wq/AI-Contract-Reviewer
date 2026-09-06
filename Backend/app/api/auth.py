from fastapi import APIRouter , Depends , Response
from app.database.database import get_db
from app.services.auth_service import AuthService , auth_service
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from app.schemas.user import UserResponse , UserCreate , LoginResponse , UserLogin , VerifyRegistrationRequest , ResendOTPRequest
from fastapi.security import OAuth2PasswordRequestForm
from app.core.rate_limit import RateLimiter

auth_router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@auth_router.post(
    "/register",
    status_code=201,
    summary="Register New User Account",
    description="Create a new user account with email and password. Generates and dispatches a 6-digit OTP verification code via email.",
    dependencies=[Depends(RateLimiter(times=5, seconds=60, prefix="auth_register"))]
)
async def register_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_services: Annotated[AuthService, Depends(auth_service)],
    user: UserCreate
):
    saved_user = await auth_services.register_user(
        db=db,
        user=user
    )
    return {
        "message": "Registration successful. Verification OTP sent to your email.",
        "user": UserResponse.model_validate(saved_user)
    }

@auth_router.post(
    "/verify-registration",
    response_model=UserResponse,
    summary="Verify User Email Registration",
    description="Validate the 6-digit OTP code sent during registration to activate the user account.",
    dependencies=[Depends(RateLimiter(times=10, seconds=60, prefix="auth_verify"))]
)
async def verify_registration(
    data: VerifyRegistrationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_services: Annotated[AuthService, Depends(auth_service)]
) -> UserResponse:
    verified_user = await auth_services.verify_registration(
        db=db,
        email=data.email,
        otp_code=data.otp_code
    )
    return UserResponse.model_validate(verified_user)

@auth_router.post(
    "/resend-otp",
    summary="Resend Email Verification OTP",
    description="Request a new 6-digit email OTP verification code for pending unverified accounts.",
    dependencies=[Depends(RateLimiter(times=5, seconds=60, prefix="auth_resend_otp"))]
)
async def resend_otp(
    data: ResendOTPRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    auth_services: Annotated[AuthService, Depends(auth_service)]
):
    await auth_services.resend_registration_otp(
        db=db,
        email=data.email
    )
    return {
        "message": "Verification OTP has been resent to your email."
    }

@auth_router.post(
    '/login',
    response_model=LoginResponse,
    summary="User Login (JSON Payload)",
    description="Authenticate user with email and password. Returns JWT access token and user profile details.",
    dependencies=[Depends(RateLimiter(times=5, seconds=60, prefix="auth_login"))]
)
async def login(
    response: Response,
    user: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AuthService, Depends(auth_service)]
):
    login_response = await service.login_user(
        db=db,
        user=user
    )

    response.set_cookie(
        key="ai_contract_session",
        value=login_response.access_token,
        httponly=True,
        samesite="lax",
        secure=False
    )

    return {
        "message": "Login successful",
        "access_token": login_response.access_token,
        "token_type": "bearer",
        "user": login_response.user
    }
    
@auth_router.post(
    '/token',
    response_model=LoginResponse,
    summary="OAuth2 Form Password Login (Swagger UI Testing)",
    description="OAuth2-compatible form authentication endpoint used by Swagger UI authorize button.",
    dependencies=[Depends(RateLimiter(times=5, seconds=60, prefix="auth_token"))]
)
async def token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AuthService, Depends(auth_service)]
):
    user = UserLogin(
        email=form_data.username,
        password=form_data.password
    )

    login_response = await service.login_user(
        db=db,
        user=user
    )

    response.set_cookie(
        key="ai_contract_session",
        value=login_response.access_token,
        httponly=True,
        samesite="lax",
        secure=False
    )

    return {
        "message": "Login successful",
        "access_token": login_response.access_token,
        "token_type": "bearer",
        "user": login_response.user
    }
    
@auth_router.post(
    "/logout",
    summary="User Logout",
    description="Clear session cookies and log out user.",
    dependencies=[Depends(RateLimiter(times=20, seconds=60, prefix="auth_logout"))]
)
async def logout(response: Response):
    response.delete_cookie(
        key="ai_contract_session"
    )

    return {
        "message": "Logout successful"
    }