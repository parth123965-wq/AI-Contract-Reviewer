import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
import io

from app.main import app
from app.database.database import Base, get_db
from app.auth.password import hash_password
from app.auth.jwt import create_access_token
from app.models.user import User
from app.models.contract import Contract, ContractStatus
from app.services.contract_service import ContractService, contract_service
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
async def setup_db(tmp_path, monkeypatch):
    # Override upload directory to temporary path
    monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
    
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
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def sample_user():
    async with TestingSessionLocal() as session:
        user = User(
            username="uploaduser",
            email="uploaduser@example.com",
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
async def test_upload_valid_contract_pdf(async_client: AsyncClient, sample_user: User, tmp_path):
    token = create_access_token(data={"sub": str(sample_user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    pdf_content = b"%PDF-1.4 sample contract content for testing"
    files = {"file": ("sample_contract.pdf", pdf_content, "application/pdf")}

    response = await async_client.post("/contracts/upload", headers=headers, files=files)
    assert response.status_code == 201
    data = response.json()

    assert data["original_filename"] == "sample_contract.pdf"
    assert data["status"] == ContractStatus.UPLOADED.value
    assert data["file_size"] == len(pdf_content)
    assert data["content_type"] == "application/pdf"

    # Verify physical file saved in upload dir
    saved_files = list(tmp_path.glob("*.pdf"))
    assert len(saved_files) == 1
    assert saved_files[0].read_bytes() == pdf_content


@pytest.mark.asyncio
async def test_upload_contract_exceeds_max_size(sample_user: User):
    service = ContractService()

    oversized_data = b"%PDF" + b"0" * (20 * 1024 * 1024 + 1)
    file_obj = io.BytesIO(oversized_data)
    upload_file = UploadFile(filename="large.pdf", file=file_obj, headers=Headers({"content-type": "application/pdf"}))

    with pytest.raises(HTTPException) as exc_info:
        service._validate_file_size(file=upload_file)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "File size exceeds the maximum allowed limit."


@pytest.mark.asyncio
async def test_upload_contract_invalid_content_type(async_client: AsyncClient, sample_user: User):
    token = create_access_token(data={"sub": str(sample_user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    pdf_content = b"%PDF-1.4 sample content"
    files = {"file": ("sample.pdf", pdf_content, "text/plain")}

    response = await async_client.post("/contracts/upload", headers=headers, files=files)
    assert response.status_code == 400
    assert "Only application/pdf content type is allowed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_contract_missing_filename(sample_user: User):
    service = ContractService()
    file_obj = io.BytesIO(b"%PDF-1.4 test")
    upload_file = UploadFile(filename="", file=file_obj)

    with pytest.raises(HTTPException) as exc_info:
        service._validate_extension(file=upload_file)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "File name is not Found"


@pytest.mark.asyncio
async def test_upload_contract_unauthenticated(async_client: AsyncClient):
    pdf_content = b"%PDF-1.4 content"
    files = {"file": ("sample.pdf", pdf_content, "application/pdf")}

    response = await async_client.post("/contracts/upload", files=files)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_contract_rollback_removes_file(db_session: AsyncSession, sample_user: User, tmp_path):
    service = ContractService()
    pdf_content = b"%PDF-1.4 content for rollback test"
    file_obj = io.BytesIO(pdf_content)
    upload_file = UploadFile(filename="fail.pdf", file=file_obj, headers=Headers({"content-type": "application/pdf"}))

    with patch.object(service.contract_repository, "create_contract", side_effect=Exception("Database error")):
        with pytest.raises(Exception, match="Database error"):
            await service.upload_contract(db=db_session, current_user=sample_user, file=upload_file)

    # Verify no file remains in upload dir after exception
    saved_files = list(tmp_path.glob("*.pdf"))
    assert len(saved_files) == 0


def test_contract_service_factory():
    instance = contract_service()
    assert isinstance(instance, ContractService)
