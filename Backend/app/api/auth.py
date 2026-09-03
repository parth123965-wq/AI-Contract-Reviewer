from fastapi import APIRouter , Depends , Response
from app.database.database import get_db
from app.services.auth_service import AuthService , auth_service
from sqlalchemy.orm import Session
from typing import Annotated
from app.schemas.user import UserResponse , UserCreate , LoginResponse , UserLogin
from fastapi.security import OAuth2PasswordRequestForm

auth_router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@auth_router.post("/register", response_model=UserResponse,status_code=201)
def register_user(
    db: Annotated[Session,Depends(get_db)],
    auth_services: Annotated[AuthService,Depends(auth_service)],
    user: UserCreate
) -> UserResponse:
    return auth_services.register_user(
        db=db,
        user=user
    )
    
@auth_router.post('/login')
def login(
    response: Response,
    user: UserLogin,
    db: Annotated[Session,Depends(get_db)],
    service: Annotated[AuthService,Depends(auth_service)]
):

    login_response = service.login_user(
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
    
@auth_router.post('/token')
def token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm,Depends()],
    db: Annotated[Session,Depends(get_db)],
    service: Annotated[AuthService,Depends(auth_service)]
):

    user = UserLogin(
        email=form_data.username,
        password=form_data.password
    )


    login_response = service.login_user(
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
    
@auth_router.post("/logout")
def logout(response: Response):

    response.delete_cookie(
        key="ai_contract_session"
    )

    return {
        "message": "Logout successful"
    }