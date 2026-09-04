import pytest
from unittest.mock import AsyncMock, patch
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import Base, get_db

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

app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

@pytest.mark.asyncio
async def test_full_otp_registration_flow(async_client: AsyncClient):
    with patch("app.services.otp_service.otp_service.generate_otp", new_callable=AsyncMock) as mock_gen_otp, \
         patch("app.services.otp_service.otp_service.send_otp_email", new_callable=AsyncMock) as mock_send_email, \
         patch("app.services.otp_service.otp_service.verify_otp", new_callable=AsyncMock) as mock_verify_otp:
        
        mock_gen_otp.return_value = "123456"
        mock_verify_otp.return_value = True

        # Step 1: Register User
        reg_resp = await async_client.post(
            "/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepassword123"
            }
        )
        assert reg_resp.status_code == 201
        data = reg_resp.json()
        assert data["message"] == "Registration successful. Verification OTP sent to your email."
        assert data["user"]["is_verified"] is False
        assert mock_gen_otp.called
        assert mock_send_email.called

        # Step 2: Attempt Login before Verification (Should Fail with 403)
        login_resp = await async_client.post(
            "/auth/login",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123"
            }
        )
        assert login_resp.status_code == 403
        assert "not verified" in login_resp.json()["detail"]

        # Step 3: Verify OTP
        verify_resp = await async_client.post(
            "/auth/verify-registration",
            json={
                "email": "newuser@example.com",
                "otp_code": "123456"
            }
        )
        assert verify_resp.status_code == 200
        verified_user_data = verify_resp.json()
        assert verified_user_data["is_verified"] is True

        # Step 4: Login after Verification (Should Succeed)
        login_resp_2 = await async_client.post(
            "/auth/login",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123"
            }
        )
        assert login_resp_2.status_code == 200
        assert "access_token" in login_resp_2.json()

@pytest.mark.asyncio
async def test_resend_otp(async_client: AsyncClient):
    with patch("app.services.otp_service.otp_service.generate_otp", new_callable=AsyncMock) as mock_gen_otp, \
         patch("app.services.otp_service.otp_service.send_otp_email", new_callable=AsyncMock) as mock_send_email:
        
        mock_gen_otp.return_value = "654321"

        # Register unverified user
        await async_client.post(
            "/auth/register",
            json={
                "username": "resenduser",
                "email": "resend@example.com",
                "password": "securepassword123"
            }
        )

        # Resend OTP
        resend_resp = await async_client.post(
            "/auth/resend-otp",
            json={"email": "resend@example.com"}
        )
        assert resend_resp.status_code == 200
        assert resend_resp.json()["message"] == "Verification OTP has been resent to your email."

@pytest.mark.asyncio
async def test_unverified_token_blocked_by_dependency(async_client: AsyncClient):
    from app.auth.jwt import create_access_token
    from app.models.user import User
    from app.auth.password import hash_password

    # Manually create unverified user in DB
    async with TestingSessionLocal() as db:
        user = User(
            username="unverifiedguy",
            email="unverified@example.com",
            password_hash=hash_password("password123"),
            is_verified=False,
            is_active=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    token = create_access_token(data={"sub": str(user_id)})
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to request protected route using token of unverified user
    resp = await async_client.get("/users/me", headers=headers)
    assert resp.status_code == 403
    assert "not verified" in resp.json()["detail"]

