import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from app.database.database import Base
from app.models.user import User
from app.models.contract import Contract
from app.auth.password import hash_password
from app.services.user_service import UserService, get_user_service
from app.schemas.user import (
    UpdateUsernameRequest,
    RequestEmailChangeRequest,
    VerifyEmailChangeRequest,
    VerifyPasswordChangeRequest
)

SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)

TestingSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def seed_users(db_session: AsyncSession):
    user1 = User(
        username="user1",
        email="user1@example.com",
        password_hash=hash_password("Password123!"),
        is_verified=True,
        is_active=True
    )
    user2 = User(
        username="user2",
        email="user2@example.com",
        password_hash=hash_password("Password123!"),
        is_verified=True,
        is_active=True
    )
    db_session.add_all([user1, user2])
    await db_session.commit()
    await db_session.refresh(user1)
    await db_session.refresh(user2)
    return {"user1": user1, "user2": user2}


@pytest.fixture
def service():
    return UserService()


@pytest.mark.asyncio
async def test_update_username_success(db_session: AsyncSession, service: UserService, seed_users):
    user1 = seed_users["user1"]
    req = UpdateUsernameRequest(username="new_user1_name")

    res = await service.update_username(db=db_session, current_user=user1, request=req)
    assert res.username == "new_user1_name"


@pytest.mark.asyncio
async def test_update_username_unchanged(db_session: AsyncSession, service: UserService, seed_users):
    user1 = seed_users["user1"]
    req = UpdateUsernameRequest(username="user1")

    res = await service.update_username(db=db_session, current_user=user1, request=req)
    assert res.username == "user1"


@pytest.mark.asyncio
async def test_update_username_duplicate_fails(db_session: AsyncSession, service: UserService, seed_users):
    user1 = seed_users["user1"]
    req = UpdateUsernameRequest(username="user2")

    with pytest.raises(HTTPException) as exc_info:
        await service.update_username(db=db_session, current_user=user1, request=req)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Username is already taken."


@pytest.mark.asyncio
async def test_request_email_change_success(db_session: AsyncSession, service: UserService, seed_users):
    user1 = seed_users["user1"]
    req = RequestEmailChangeRequest(new_email="new_user1@example.com")

    with patch("app.services.otp_service.otp_service.generate_otp", new_callable=AsyncMock) as mock_gen, \
         patch("app.services.otp_service.otp_service.send_otp_email", new_callable=AsyncMock) as mock_send:
        mock_gen.return_value = "112233"

        res = await service.request_email_change(db=db_session, current_user=user1, request=req)
        assert "Verification OTP sent" in res["message"]
        mock_gen.assert_called_once_with(purpose="email_change", identifier="new_user1@example.com")
        mock_send.assert_called_once_with(email="new_user1@example.com", otp_code="112233", purpose="email_change")


@pytest.mark.asyncio
async def test_request_email_change_same_email_fails(db_session: AsyncSession, service: UserService, seed_users):
    user1 = seed_users["user1"]
    req = RequestEmailChangeRequest(new_email="user1@example.com")

    with pytest.raises(HTTPException) as exc_info:
        await service.request_email_change(db=db_session, current_user=user1, request=req)
    assert exc_info.value.status_code == 400
    assert "New email must be different" in exc_info.value.detail


@pytest.mark.asyncio
async def test_request_email_change_registered_email_fails(db_session: AsyncSession, service: UserService, seed_users):
    user1 = seed_users["user1"]
    req = RequestEmailChangeRequest(new_email="user2@example.com")

    with pytest.raises(HTTPException) as exc_info:
        await service.request_email_change(db=db_session, current_user=user1, request=req)
    assert exc_info.value.status_code == 400
    assert "Email is already registered" in exc_info.value.detail


@pytest.mark.asyncio
async def test_confirm_email_change_success(db_session: AsyncSession, service: UserService, seed_users):
    user1 = seed_users["user1"]
    req = VerifyEmailChangeRequest(new_email="updated_user1@example.com", otp_code="112233")

    with patch("app.services.otp_service.otp_service.verify_otp", new_callable=AsyncMock) as mock_verify, \
         patch("app.services.email_service.email_service.send_email_changed_notification", new_callable=AsyncMock) as mock_notify:
        mock_verify.return_value = True

        res = await service.confirm_email_change(db=db_session, current_user=user1, request=req)
        assert res.email == "updated_user1@example.com"
        mock_verify.assert_called_once_with(purpose="email_change", identifier="updated_user1@example.com", input_otp="112233")


@pytest.mark.asyncio
async def test_request_and_confirm_password_change(db_session: AsyncSession, service: UserService, seed_users):
    user1 = seed_users["user1"]

    with patch("app.services.otp_service.otp_service.generate_otp", new_callable=AsyncMock) as mock_gen, \
         patch("app.services.otp_service.otp_service.send_otp_email", new_callable=AsyncMock) as mock_send:
        mock_gen.return_value = "445566"
        res = await service.request_password_change(db=db_session, current_user=user1)
        assert "Verification OTP sent" in res["message"]

    req_pass = VerifyPasswordChangeRequest(
        current_password="Password123!",
        new_password="NewPassword123!",
        otp_code="445566"
    )

    with patch("app.services.otp_service.otp_service.verify_otp", new_callable=AsyncMock) as mock_verify, \
         patch("app.services.email_service.email_service.send_password_changed_notification", new_callable=AsyncMock):
        mock_verify.return_value = True

        res_pass = await service.confirm_password_change(db=db_session, current_user=user1, request=req_pass)
        assert res_pass["message"] == "Password changed successfully."


@pytest.mark.asyncio
async def test_confirm_password_change_incorrect_current_password(db_session: AsyncSession, service: UserService, seed_users):
    user1 = seed_users["user1"]
    req = VerifyPasswordChangeRequest(
        current_password="WrongCurrentPassword",
        new_password="NewPassword123!",
        otp_code="123456"
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.confirm_password_change(db=db_session, current_user=user1, request=req)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Incorrect current password."


@pytest.mark.asyncio
async def test_confirm_password_change_same_password(db_session: AsyncSession, service: UserService, seed_users):
    user1 = seed_users["user1"]
    req = VerifyPasswordChangeRequest(
        current_password="Password123!",
        new_password="Password123!",
        otp_code="123456"
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.confirm_password_change(db=db_session, current_user=user1, request=req)
    assert exc_info.value.status_code == 400
    assert "New password must be different" in exc_info.value.detail


def test_user_service_factory():
    instance = get_user_service()
    assert isinstance(instance, UserService)
