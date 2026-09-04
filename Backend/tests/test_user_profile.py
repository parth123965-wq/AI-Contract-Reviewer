import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import Base, get_db
from app.auth.password import hash_password
from app.auth.jwt import create_access_token
from app.models.user import User

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

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_update_username_success():
    async with TestingSessionLocal() as session:
        user = User(
            username="oldusername",
            email="user1@example.com",
            password_hash=hash_password("password123"),
            is_active=True,
            is_verified=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(data={"sub": str(user_id)})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch("/users/me/username", json={"username": "newusername"}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newusername"

@pytest.mark.asyncio
async def test_update_username_duplicate_fails():
    async with TestingSessionLocal() as session:
        user1 = User(
            username="existinguser",
            email="user1@example.com",
            password_hash=hash_password("password123"),
            is_active=True,
            is_verified=True
        )
        user2 = User(
            username="seconduser",
            email="user2@example.com",
            password_hash=hash_password("password123"),
            is_active=True,
            is_verified=True
        )
        session.add_all([user1, user2])
        await session.commit()
        await session.refresh(user2)
        user2_id = user2.id

    token = create_access_token(data={"sub": str(user2_id)})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch("/users/me/username", json={"username": "existinguser"}, headers=headers)
        assert response.status_code == 400
        assert "Username is already taken" in response.json()["detail"]

@pytest.mark.asyncio
@patch("app.services.user_service.otp_service.send_otp_email", new_callable=AsyncMock)
@patch("app.services.user_service.otp_service.generate_otp", new_callable=AsyncMock, return_value="123456")
@patch("app.services.user_service.otp_service.verify_otp", new_callable=AsyncMock, return_value=True)
async def test_email_change_with_otp_flow(mock_verify_otp, mock_generate_otp, mock_send_email):
    async with TestingSessionLocal() as session:
        user = User(
            username="emailuser",
            email="oldemail@example.com",
            password_hash=hash_password("password123"),
            is_active=True,
            is_verified=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(data={"sub": str(user_id)})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Request Email Change
        req_resp = await client.post("/users/me/email/request", json={"new_email": "newemail@example.com"}, headers=headers)
        assert req_resp.status_code == 200
        mock_generate_otp.assert_called_once_with(purpose="email_change", identifier="newemail@example.com")
        mock_send_email.assert_called_once_with(email="newemail@example.com", otp_code="123456", purpose="email_change")

        # Step 2: Confirm Email Change
        confirm_resp = await client.post(
            "/users/me/email/confirm",
            json={"new_email": "newemail@example.com", "otp_code": "123456"},
            headers=headers
        )
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["email"] == "newemail@example.com"
        mock_verify_otp.assert_called_once_with(purpose="email_change", identifier="newemail@example.com", input_otp="123456")

@pytest.mark.asyncio
@patch("app.services.user_service.otp_service.send_otp_email", new_callable=AsyncMock)
@patch("app.services.user_service.otp_service.generate_otp", new_callable=AsyncMock, return_value="654321")
@patch("app.services.user_service.otp_service.verify_otp", new_callable=AsyncMock, return_value=True)
async def test_password_change_with_otp_flow(mock_verify_otp, mock_generate_otp, mock_send_email):
    async with TestingSessionLocal() as session:
        user = User(
            username="passuser",
            email="pass@example.com",
            password_hash=hash_password("oldpassword123"),
            is_active=True,
            is_verified=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(data={"sub": str(user_id)})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: Request Password Change OTP
        req_resp = await client.post("/users/me/password/request", headers=headers)
        assert req_resp.status_code == 200
        mock_generate_otp.assert_called_once_with(purpose="password_change", identifier="pass@example.com")
        mock_send_email.assert_called_once_with(email="pass@example.com", otp_code="654321", purpose="password_change")

        # Step 2: Confirm Password Change
        confirm_resp = await client.post(
            "/users/me/password/confirm",
            json={"current_password": "oldpassword123", "new_password": "newpassword123", "otp_code": "654321"},
            headers=headers
        )
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["message"] == "Password changed successfully."
        mock_verify_otp.assert_called_once_with(purpose="password_change", identifier="pass@example.com", input_otp="654321")
