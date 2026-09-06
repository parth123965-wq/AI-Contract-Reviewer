import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from jose import JWTError, ExpiredSignatureError, jwt
from app.core.config import settings
from app.core.logger import get_app_logger

logger = get_app_logger("auth_jwt")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generate a signed JWT access token with standard security claims:
    - sub: subject identifier
    - exp: expiration timestamp
    - iat: issued at timestamp
    - nbf: not before timestamp
    - jti: unique JWT ID
    - type: 'access' token type identifier
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "iat": now,
        "nbf": now,
        "jti": to_encode.get("jti", str(uuid.uuid4())),
        "type": to_encode.get("type", "access"),
    })

    encoded_jwt = jwt.encode(
        claims=to_encode,
        key=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """
    Decode and validate a JWT access token.
    Enforces algorithm restrictions, signature verification, expiration check,
    subject claim presence, and token type validation.
    """
    try:
        payload = jwt.decode(
            token=token,
            key=settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
            }
        )

        subject = payload.get("sub")
        if subject is None:
            logger.warning("JWT token missing 'sub' claim.")
            return None

        # Validate token type if present
        token_type = payload.get("type")
        if token_type and token_type != "access":
            logger.warning(f"Invalid JWT token type: '{token_type}'. Expected 'access'.")
            return None

        return payload

    except ExpiredSignatureError:
        logger.info("Access token has expired.")
        return None
    except JWTError as e:
        logger.warning(f"Failed to decode or verify JWT token: {e}")
        return None


def verify_access_token(token: str) -> str:
    """
    Verify access token and return subject ('sub') claim string.
    Raises ValueError if token is expired, invalid, or missing subject.
    """
    payload = decode_access_token(token=token)
    if payload is None:
        raise ValueError("Invalid or expired token")

    subject = payload.get("sub")
    if subject is None:
        raise ValueError("Missing Subject Claim")

    return str(subject)