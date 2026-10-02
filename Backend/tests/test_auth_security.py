from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth.jwt import (
    create_access_token,
    decode_access_token,
    verify_access_token,
)
from app.dependencies import auth as auth_dependencies


def make_request(headers=None, query_string=b""):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/private",
            "headers": [
                (key.lower().encode(), value.encode())
                for key, value in (headers or {}).items()
            ],
            "query_string": query_string,
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
        }
    )


def make_user(**overrides):
    values = {
        "id": 12,
        "is_active": True,
        "is_verified": True,
        "is_admin": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_access_token_round_trip_includes_standard_claims():
    token = create_access_token({"sub": "12"})

    payload = decode_access_token(token)

    assert payload["sub"] == "12"
    assert payload["type"] == "access"
    assert payload["jti"]
    assert verify_access_token(token) == "12"


def test_decode_access_token_rejects_tampered_token():
    token = create_access_token({"sub": "12"})

    assert decode_access_token(token + "tampered") is None


def test_decode_access_token_rejects_expired_token():
    token = create_access_token(
        {"sub": "12"},
        expires_delta=timedelta(seconds=-1),
    )

    assert decode_access_token(token) is None


def test_decode_access_token_rejects_non_access_token():
    token = create_access_token({"sub": "12", "type": "refresh"})

    assert decode_access_token(token) is None


def test_verify_access_token_raises_for_invalid_token():
    with pytest.raises(ValueError, match="Invalid or expired"):
        verify_access_token("not-a-jwt")


@pytest.mark.asyncio
async def test_current_user_accepts_cookie_token(monkeypatch):
    user = make_user()
    repository = AsyncMock()
    repository.get_user_by_id.return_value = user
    monkeypatch.setattr(auth_dependencies, "UserRepository", lambda: repository)
    decode = Mock(return_value={"sub": "12"})
    monkeypatch.setattr(auth_dependencies, "decode_access_token", decode)
    request = make_request({"Cookie": "ai_contract_session=cookie-token"})

    result = await auth_dependencies.get_current_user(request, object())

    assert result is user
    decode.assert_called_once_with(token="cookie-token")
    repository.get_user_by_id.assert_awaited_once_with(db=ANY, user_id=12)


@pytest.mark.asyncio
async def test_current_user_accepts_bearer_token(monkeypatch):
    user = make_user()
    repository = AsyncMock()
    repository.get_user_by_id.return_value = user
    monkeypatch.setattr(auth_dependencies, "UserRepository", lambda: repository)
    decode = Mock(return_value={"sub": "12"})
    monkeypatch.setattr(auth_dependencies, "decode_access_token", decode)

    await auth_dependencies.get_current_user(
        make_request({"Authorization": "Bearer bearer-token"}),
        object(),
    )

    decode.assert_called_once_with(token="bearer-token")


@pytest.mark.asyncio
async def test_current_user_rejects_missing_token():
    with pytest.raises(HTTPException) as error:
        await auth_dependencies.get_current_user(make_request(), object())

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_current_user_rejects_invalid_token(monkeypatch):
    monkeypatch.setattr(auth_dependencies, "decode_access_token", lambda **_: None)

    with pytest.raises(HTTPException) as error:
        await auth_dependencies.get_current_user(
            make_request({"Authorization": "Bearer invalid"}),
            object(),
        )

    assert error.value.status_code == 401


@pytest.mark.asyncio
async def test_current_user_rejects_missing_subject(monkeypatch):
    monkeypatch.setattr(auth_dependencies, "decode_access_token", lambda **_: {})

    with pytest.raises(HTTPException) as error:
        await auth_dependencies.get_current_user(
            make_request({"Authorization": "Bearer token"}),
            object(),
        )

    assert error.value.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("user", "expected_status"),
    [
        (None, 404),
        (make_user(is_active=False), 403),
        (make_user(is_verified=False), 403),
    ],
)
async def test_current_user_rejects_missing_or_ineligible_account(
    monkeypatch, user, expected_status
):
    repository = AsyncMock()
    repository.get_user_by_id.return_value = user
    monkeypatch.setattr(auth_dependencies, "UserRepository", lambda: repository)
    monkeypatch.setattr(
        auth_dependencies,
        "decode_access_token",
        lambda **_: {"sub": "12"},
    )

    with pytest.raises(HTTPException) as error:
        await auth_dependencies.get_current_user(
            make_request({"Authorization": "Bearer token"}),
            object(),
        )

    assert error.value.status_code == expected_status


def test_current_admin_rejects_non_admin():
    with pytest.raises(HTTPException) as error:
        auth_dependencies.get_current_admin(make_user(is_admin=False))

    assert error.value.status_code == 403
