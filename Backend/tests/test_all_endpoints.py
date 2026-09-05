import sys
from pathlib import Path

# Add Backend root directory to sys.path so direct execution works from any CWD
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
import io

from app.main import app
from app.database.database import Base, get_db
from app.auth.password import hash_password
from app.auth.jwt import create_access_token
from app.models.user import User
from app.models.contract import Contract, ContractStatus

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

@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

# Helper fixture for regular user token
@pytest_asyncio.fixture
async def sample_user():
    async with TestingSessionLocal() as session:
        user = User(
            username="testuser",
            email="testuser@example.com",
            password_hash=hash_password("Password123!"),
            is_admin=False,
            is_active=True,
            is_verified=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

# Helper fixture for admin user token
@pytest_asyncio.fixture
async def sample_admin():
    async with TestingSessionLocal() as session:
        admin = User(
            username="adminuser",
            email="adminuser@example.com",
            password_hash=hash_password("AdminPass123!"),
            is_admin=True,
            is_active=True,
            is_verified=True
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin


# =======================================================
# 1. SYSTEM HEALTH ENDPOINT
# =======================================================
@pytest.mark.asyncio
async def test_home_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


# =======================================================
# 2. AUTHENTICATION ENDPOINTS (/auth)
# =======================================================
@pytest.mark.asyncio
async def test_auth_full_flow(async_client: AsyncClient):
    with patch("app.services.otp_service.otp_service.generate_otp", new_callable=AsyncMock) as mock_gen_otp, \
         patch("app.services.otp_service.otp_service.send_otp_email", new_callable=AsyncMock) as mock_send_email, \
         patch("app.services.otp_service.otp_service.verify_otp", new_callable=AsyncMock) as mock_verify_otp:

        mock_gen_otp.return_value = "123456"
        mock_verify_otp.return_value = True

        # 1. Register User
        reg_resp = await async_client.post(
            "/auth/register",
            json={
                "username": "flowuser",
                "email": "flowuser@example.com",
                "password": "Password123!"
            }
        )
        assert reg_resp.status_code == 201
        assert reg_resp.json()["user"]["is_verified"] is False

        # 2. Login Before Verification (Fails)
        login_unverified = await async_client.post(
            "/auth/login",
            json={"email": "flowuser@example.com", "password": "Password123!"}
        )
        assert login_unverified.status_code == 403

        # 3. Verify Registration OTP
        verify_resp = await async_client.post(
            "/auth/verify-registration",
            json={"email": "flowuser@example.com", "otp_code": "123456"}
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["is_verified"] is True

        # 4. Login After Verification (Succeeds)
        login_resp = await async_client.post(
            "/auth/login",
            json={"email": "flowuser@example.com", "password": "Password123!"}
        )
        assert login_resp.status_code == 200
        tokens = login_resp.json()
        assert "access_token" in tokens

        # 5. Logout
        logout_resp = await async_client.post("/auth/logout")
        assert logout_resp.status_code == 200
        assert logout_resp.json()["message"] == "Logout successful"


# =======================================================
# 3. USER MANAGEMENT ENDPOINTS (/users)
# =======================================================
@pytest.mark.asyncio
async def test_users_endpoints(async_client: AsyncClient, sample_user: User):
    token = create_access_token(data={"sub": str(sample_user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.otp_service.otp_service.generate_otp", new_callable=AsyncMock) as mock_gen_otp, \
         patch("app.services.otp_service.otp_service.send_otp_email", new_callable=AsyncMock) as mock_send_email, \
         patch("app.services.otp_service.otp_service.verify_otp", new_callable=AsyncMock) as mock_verify_otp, \
         patch("app.services.email_service.email_service.send_email_changed_notification", new_callable=AsyncMock), \
         patch("app.services.email_service.email_service.send_password_changed_notification", new_callable=AsyncMock):

        mock_gen_otp.return_value = "654321"
        mock_verify_otp.return_value = True

        # 1. Get Me Profile
        me_resp = await async_client.get("/users/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "testuser"

        # 2. Update Username
        update_username_resp = await async_client.patch(
            "/users/me/username",
            json={"username": "updatedtestuser"},
            headers=headers
        )
        assert update_username_resp.status_code == 200
        assert update_username_resp.json()["username"] == "updatedtestuser"

        # 3. Request Email Change
        req_email_resp = await async_client.post(
            "/users/me/email/request",
            json={"new_email": "newemail@example.com"},
            headers=headers
        )
        assert req_email_resp.status_code == 200

        # 4. Confirm Email Change
        confirm_email_resp = await async_client.post(
            "/users/me/email/confirm",
            json={"new_email": "newemail@example.com", "otp_code": "654321"},
            headers=headers
        )
        assert confirm_email_resp.status_code == 200
        assert confirm_email_resp.json()["email"] == "newemail@example.com"

        # 5. Request Password Change
        req_pass_resp = await async_client.post(
            "/users/me/password/request",
            headers=headers
        )
        assert req_pass_resp.status_code == 200

        # 6. Confirm Password Change
        confirm_pass_resp = await async_client.post(
            "/users/me/password/confirm",
            json={
                "current_password": "Password123!",
                "new_password": "BrandNewPassword123!",
                "otp_code": "654321"
            },
            headers=headers
        )
        assert confirm_pass_resp.status_code == 200
        assert confirm_pass_resp.json()["message"] == "Password changed successfully."


# =======================================================
# 4. ADMIN ENDPOINTS (/admin)
# =======================================================
@pytest.mark.asyncio
async def test_admin_endpoints(async_client: AsyncClient, sample_admin: User, sample_user: User):
    # 1. Admin Login
    login_resp = await async_client.post(
        "/admin/auth/login",
        json={"email": "adminuser@example.com", "password": "AdminPass123!"}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Dashboard Stats
    stats_resp = await async_client.get("/admin/dashboard/stats", headers=headers)
    assert stats_resp.status_code == 200
    assert "total_users" in stats_resp.json()

    # 3. List Users
    users_resp = await async_client.get("/admin/users", headers=headers)
    assert users_resp.status_code == 200
    assert users_resp.json()["total"] >= 2

    # 4. Get User Detail
    user_detail_resp = await async_client.get(f"/admin/users/{sample_user.id}", headers=headers)
    assert user_detail_resp.status_code == 200
    assert user_detail_resp.json()["id"] == sample_user.id

    # 5. Update User Status
    status_update_resp = await async_client.patch(
        f"/admin/users/{sample_user.id}/status",
        json={"is_active": False},
        headers=headers
    )
    assert status_update_resp.status_code == 200
    assert status_update_resp.json()["is_active"] is False

    # 6. Update User Role
    role_update_resp = await async_client.patch(
        f"/admin/users/{sample_user.id}/role",
        json={"is_admin": True},
        headers=headers
    )
    assert role_update_resp.status_code == 200
    assert role_update_resp.json()["is_admin"] is True

    # 7. List Admin Contracts
    contracts_resp = await async_client.get("/admin/contracts", headers=headers)
    assert contracts_resp.status_code == 200


# =======================================================
# 5. CONTRACT ENDPOINTS (/contracts)
# =======================================================
@pytest.mark.asyncio
async def test_contract_endpoints(async_client: AsyncClient, sample_user: User):
    token = create_access_token(data={"sub": str(sample_user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.ai_analysis_service.ContractGraph") as mock_graph_cls, \
         patch("app.services.ai_analysis_service.AnalysisService.analyze_contract", new_callable=AsyncMock), \
         patch("ai_engine.services.embedding_service.EmbeddingService.create_embeddings", return_value=[[0.1]*1536]), \
         patch("ai_engine.services.vector_store_service.VectorStoreService.search", return_value=["clause details"]), \
         patch("ai_engine.services.llm_service.LLMService.ask_question", return_value="This is a valid answer."):
        mock_graph_cls.return_value.compile_graph.return_value = MagicMock()

        # 1. Upload Contract
        fake_pdf = io.BytesIO(b"%PDF-1.4 Fake PDF Content")
        files = {"file": ("test_contract.pdf", fake_pdf, "application/pdf")}
        upload_resp = await async_client.post("/contracts/upload", files=files, headers=headers)
        assert upload_resp.status_code == 200
        contract_data = upload_resp.json()
        contract_id = contract_data["id"]

        # 2. Get User Contracts List
        list_resp = await async_client.get("/contracts", headers=headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()["contracts"]) == 1

        # 3. Get Single Contract by ID
        get_resp = await async_client.get(f"/contracts/{contract_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == contract_id

        # 4. Ask Question on Contract
        ask_resp = await async_client.post(
            f"/contracts/{contract_id}/ask",
            json={"question": "What is the termination clause?"},
            headers=headers
        )
        assert ask_resp.status_code == 200

        # 5. Delete Contract
        del_resp = await async_client.delete(f"/contracts/{contract_id}", headers=headers)
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "success"


if __name__ == "__main__":
    pytest.main(["-W", "ignore::pytest.PytestAssertRewriteWarning", "-W", "ignore::DeprecationWarning", __file__])


