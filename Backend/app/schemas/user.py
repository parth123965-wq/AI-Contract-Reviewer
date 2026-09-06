from pydantic import EmailStr , Field , BaseModel , ConfigDict
from datetime import datetime

class UserCreate(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=100,
        description="Unique display name for the user profile",
        examples=["john_doe"]
    )
    email: EmailStr = Field(
        description="Valid user email address used for login and verification",
        examples=["john@example.com"]
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Account password (must contain at least 8 characters)",
        examples=["SecurePass123!"]
    )
    
class UserResponse(BaseModel):
    id: int = Field(description="Unique internal user ID", examples=[1])
    username: str = Field(description="User display name", examples=["john_doe"])
    is_active: bool = Field(description="Account active status flag", examples=[True])
    is_admin: bool = Field(default=False, description="Administrative privilege flag", examples=[False])
    is_verified: bool = Field(default=False, description="Email verification status", examples=[True])
    email: EmailStr = Field(description="User email address", examples=["john@example.com"])
    created_at: datetime = Field(description="Account registration timestamp")
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "username": "john_doe",
                "is_active": True,
                "is_admin": False,
                "is_verified": True,
                "email": "john@example.com",
                "created_at": "2026-09-06T12:00:00Z"
            }
        }
    )
    
class UserLogin(BaseModel):
    email: EmailStr = Field(description="Registered email address", examples=["john@example.com"])
    password: str = Field(
        min_length=8,
        max_length=128,
        description="Account password",
        examples=["SecurePass123!"]
    )
    
class LoginResponse(BaseModel):
    access_token: str = Field(description="JWT Bearer access token string")
    token_type: str = Field(default="bearer", description="Token protocol type", examples=["bearer"])
    user: UserResponse = Field(description="Authenticated user profile details")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "user": {
                    "id": 1,
                    "username": "john_doe",
                    "is_active": True,
                    "is_admin": False,
                    "is_verified": True,
                    "email": "john@example.com",
                    "created_at": "2026-09-06T12:00:00Z"
                }
            }
        }
    )

class VerifyRegistrationRequest(BaseModel):
    email: EmailStr = Field(description="Registered user email", examples=["john@example.com"])
    otp_code: str = Field(
        min_length=6,
        max_length=6,
        description="6-digit verification code sent via email",
        examples=["123456"]
    )

class ResendOTPRequest(BaseModel):
    email: EmailStr = Field(description="Target user email address for OTP delivery", examples=["john@example.com"])

class UpdateUsernameRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=100,
        description="New unique display username",
        examples=["john_doe_updated"]
    )

class UpdateEmailRequest(BaseModel):
    email: EmailStr = Field(description="New email address", examples=["new_email@example.com"])

class RequestEmailChangeRequest(BaseModel):
    new_email: EmailStr = Field(description="New target email address", examples=["new_email@example.com"])

class VerifyEmailChangeRequest(BaseModel):
    new_email: EmailStr = Field(description="New target email address", examples=["new_email@example.com"])
    otp_code: str = Field(
        min_length=6,
        max_length=6,
        description="6-digit OTP code sent to new email address",
        examples=["654321"]
    )

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(
        min_length=8,
        max_length=128,
        description="Current account password",
        examples=["OldPass123!"]
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New account password",
        examples=["NewSecurePass456!"]
    )

class VerifyPasswordChangeRequest(BaseModel):
    current_password: str = Field(
        min_length=8,
        max_length=128,
        description="Current account password",
        examples=["OldPass123!"]
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New account password",
        examples=["NewSecurePass456!"]
    )
    otp_code: str = Field(
        min_length=6,
        max_length=6,
        description="6-digit verification code sent via email",
        examples=["123456"]
    )

