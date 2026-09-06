import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
import io

from app.main import app
from app.database.database import Base, get_db
from app.auth.password import hash_password
from app.auth.jwt import create_access_token
from app.models.user import User

from unittest.mock import MagicMock
from app.services.ai_analysis_service import get_analysis_service

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
    app.dependency_overrides[get_analysis_service] = lambda: MagicMock()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_analysis_service, None)

@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

@pytest_asyncio.fixture
async def sample_user():
    async with TestingSessionLocal() as session:
        user = User(
            username="contractuser",
            email="contractuser@example.com",
            password_hash=hash_password("Password123!"),
            is_admin=False,
            is_active=True,
            is_verified=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

@pytest.mark.asyncio
async def test_upload_contract_invalid_extension(async_client: AsyncClient, sample_user: User):
    token = create_access_token(data={"sub": str(sample_user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    files = {"file": ("contract.txt", b"%PDF-dummy text content", "application/pdf")}
    response = await async_client.post("/contracts/upload", headers=headers, files=files)
    assert response.status_code == 400
    assert "Only PDF files are allowed" in response.json()["detail"]

@pytest.mark.asyncio
async def test_upload_contract_invalid_magic_bytes(async_client: AsyncClient, sample_user: User):
    token = create_access_token(data={"sub": str(sample_user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    # File named .pdf but containing plain text without %PDF header
    files = {"file": ("fake_contract.pdf", b"This is not a PDF file content", "application/pdf")}
    response = await async_client.post("/contracts/upload", headers=headers, files=files)
    assert response.status_code == 400
    assert "Invalid PDF file format" in response.json()["detail"]

@pytest.mark.asyncio
async def test_upload_contract_empty_file(async_client: AsyncClient, sample_user: User):
    token = create_access_token(data={"sub": str(sample_user.id)})
    headers = {"Authorization": f"Bearer {token}"}
    
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    response = await async_client.post("/contracts/upload", headers=headers, files=files)
    assert response.status_code == 400
    assert "Uploaded file cannot be empty" in response.json()["detail"]
