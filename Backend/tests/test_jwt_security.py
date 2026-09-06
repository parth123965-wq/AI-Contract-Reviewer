from datetime import timedelta
import pytest
from jose import jwt
from app.auth.jwt import create_access_token, decode_access_token, verify_access_token
from app.core.config import settings


def test_create_and_decode_valid_access_token():
    user_id = "42"
    token = create_access_token(data={"sub": user_id})
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "nbf" in payload
    assert "jti" in payload
    assert "exp" in payload


def test_verify_access_token_returns_subject():
    token = create_access_token(data={"sub": "100"})
    subject = verify_access_token(token)
    assert subject == "100"


def test_expired_token_rejected():
    token = create_access_token(data={"sub": "100"}, expires_delta=timedelta(seconds=-10))

    payload = decode_access_token(token)
    assert payload is None

    with pytest.raises(ValueError, match="Invalid or expired token"):
        verify_access_token(token)


def test_tampered_signature_rejected():
    token = create_access_token(data={"sub": "100"})
    tampered_token = token[:-4] + "abcd"

    payload = decode_access_token(tampered_token)
    assert payload is None


def test_invalid_token_type_rejected():
    token = create_access_token(data={"sub": "100", "type": "refresh"})

    payload = decode_access_token(token)
    assert payload is None


def test_missing_sub_rejected():
    raw_payload = {"type": "access"}
    token = jwt.encode(raw_payload, key=settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    payload = decode_access_token(token)
    assert payload is None
