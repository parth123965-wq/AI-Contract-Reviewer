from fastapi import APIRouter , Depends
from app.dependencies.auth import get_current_user
from typing import Annotated
from app.models.user import User

users_router = APIRouter(
    prefix='/users',
    tags=['Users']
)

@users_router.get('/me')
def get_profile(current_user: Annotated[User,Depends(get_current_user)]):
    return current_user