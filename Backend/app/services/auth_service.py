from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.password import hash_password , verify_password
from app.schemas.user import UserCreate , UserLogin , LoginResponse , UserResponse
from app.models.user import User
from app.repositories.user_repository import UserRepository
from fastapi import HTTPException, status
from app.auth.jwt import create_access_token
from app.services.otp_service import otp_service

class AuthService:
    
    def __init__(self):
        self.user_repository = UserRepository()
        
    async def register_user(self, db: AsyncSession, user: UserCreate) -> User:
        existing_user = await self.user_repository.get_user_by_email(db=db, email=user.email)
        hashed_password = hash_password(password=user.password)

        if existing_user is not None:
            if existing_user.is_verified:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Email already registered'
                )
            # Unverified existing user: update details for re-registration
            existing_user.username = user.username
            existing_user.password_hash = hashed_password
            await db.commit()
            await db.refresh(existing_user)
            saved_user = existing_user
        else:
            new_user = User(
                username=user.username,
                email=user.email,
                password_hash=hashed_password,
                is_verified=False
            )
            saved_user = await self.user_repository.create_user(
                db=db,
                user=new_user
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
        return verified_user

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