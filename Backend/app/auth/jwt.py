from datetime import datetime , timedelta , timezone
from jose import JWTError , jwt
from app.core.config import settings
from typing import Any , Optional

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    encode_jwt = jwt.encode(
        claims=to_encode,
        key=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encode_jwt

def verify_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token=token,
            key=settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )    
        subject = payload.get("sub")
        if subject is None:
            raise ValueError("Missing Subject Claim")
        return subject
    except JWTError:
        raise ValueError("Invalid or Expire token")
    
def decode_access_token(token: str) -> Optional[dict[str,Any]]:
    try:
        payload = jwt.decode(
            token=token,
            key=settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None