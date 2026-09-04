from pydantic import EmailStr , Field , BaseModel , ConfigDict
from datetime import datetime

class UserCreate(BaseModel):
    username : str = Field(
        min_length=3,
        max_length=100
    )
    email : EmailStr
    password : str = Field(
        min_length=8,
        max_length=128
    )
    
class UserResponse(BaseModel):
    id : int
    username : str
    is_active : bool
    is_admin : bool = False
    is_verified : bool = False
    email : EmailStr
    created_at : datetime
    model_config = ConfigDict(
        from_attributes=True
    )
    
class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=128
    )
    
class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

class VerifyRegistrationRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(
        min_length=6,
        max_length=6
    )

class ResendOTPRequest(BaseModel):
    email: EmailStr

class UpdateUsernameRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=100
    )

class UpdateEmailRequest(BaseModel):
    email: EmailStr

class RequestEmailChangeRequest(BaseModel):
    new_email: EmailStr

class VerifyEmailChangeRequest(BaseModel):
    new_email: EmailStr
    otp_code: str = Field(
        min_length=6,
        max_length=6
    )

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(
        min_length=8,
        max_length=128
    )
    new_password: str = Field(
        min_length=8,
        max_length=128
    )

class VerifyPasswordChangeRequest(BaseModel):
    current_password: str = Field(
        min_length=8,
        max_length=128
    )
    new_password: str = Field(
        min_length=8,
        max_length=128
    )
    otp_code: str = Field(
        min_length=6,
        max_length=6
    )

