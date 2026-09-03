from sqlalchemy.orm import Session
from app.auth.password import hash_password , verify_password
from app.schemas.user import UserCreate , UserLogin , LoginResponse , UserResponse
from app.models.user import User
from app.repositories.user_repository import UserRepository
from fastapi import HTTPException
from app.auth.jwt import create_access_token

class AuthService:
    
    def __init__(self):
        self.user_repository = UserRepository()
        
    def register_user(self, db:Session, user: UserCreate) -> User:
        existing_user = self.user_repository.get_user_by_email(db=db, email=user.email)
        if existing_user is not None:
            raise HTTPException(
                status_code=400,
                detail='Email already registered'
            )
        hashed_password = hash_password(password=user.password)
        new_user = User(
            username = user.username,
            email = user.email,
            password_hash = hashed_password
        )
        saved_user = self.user_repository.create_user(
            db=db,
            user=new_user
        )
        return saved_user
    
    def login_user(self, db: Session, user: UserLogin) -> LoginResponse:
        existing_user = self.user_repository.get_user_by_email(db=db, email=user.email)
        if existing_user is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid Email and Password."
            )
        if not verify_password(password=user.password, password_hash_value=existing_user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="Invalid Email and Password."
            )
        token = create_access_token(data={'sub': str(existing_user.id)})
        return LoginResponse(
            access_token=token,
            token_type='bearer',
            user=UserResponse.model_validate(existing_user)
        )
    
def auth_service() -> AuthService:
    return AuthService() 