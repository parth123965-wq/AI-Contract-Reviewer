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

from app.main import app
from app.database.database import Base, get_db
from app.auth.password import hash_password
from app.auth.jwt import create_access_token
from app.models.user import User
from app.models.contract import Contract, ContractStatus
from app.services.ai_analysis_service import get_analysis_service

from ai_engine.services.chunk_service import ChunkService
from ai_engine.services.parser_service import ParserService
from ai_engine.services.text_extractor import TextExtractor

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
async def sample_contract_user():
    async with TestingSessionLocal() as session:
        user = User(
            username="raguser",
            email="raguser@example.com",
            password_hash=hash_password("Password123!"),
            is_active=True,
            is_verified=True
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        contract = Contract(
            user_id=user.id,
            original_filename="nd_agreement.pdf",
            stored_filename="nda_uuid.pdf",
            file_path="/tmp/nda_uuid.pdf",
            file_size=1024,
            content_type="application/pdf",
            status=ContractStatus.UPLOADED
        )
        session.add(contract)
        await session.commit()
        await session.refresh(contract)
        return {"user": user, "contract": contract}


def test_chunk_service_splitting():
    chunker = ChunkService()
    text = "Clause 1: Confidentiality obligation and indemnification clause. " * 30
    chunks = chunker.chunk_text(text)
    assert len(chunks) >= 1
    assert isinstance(chunks[0], str)


def test_parser_service_clean_json():
    parser = ParserService()
    valid_json_text = '{"risk_score": 85, "risk": "HIGH", "summary": "High risk contract", "suggestions": ["Review section 4"]}'

    result = parser.process_json(valid_json_text)
    assert result.risk_score == 85
    assert result.risk == "HIGH"
    assert result.summary == "High risk contract"


def test_parser_service_markdown_wrapped_json():
    parser = ParserService()
    markdown_json = '```json\n{"risk_score": 40, "risk": "MEDIUM", "summary": "Medium risk", "suggestions": ["Check termination"]}\n```'

    result = parser.process_json(markdown_json)
    assert result.risk_score == 40
    assert result.risk == "MEDIUM"


def test_parser_service_fallback_on_invalid_string():
    parser = ParserService()
    invalid_text = "This is not JSON content"

    result = parser.process_json(invalid_text)
    assert hasattr(result, "risk_score")
    assert result.risk == "MEDIUM"


def test_text_extractor_file_not_found():
    extractor = TextExtractor()
    with pytest.raises(Exception):
        extractor.extract_text("/nonexistent/file/path.pdf")


@pytest.mark.asyncio
async def test_ask_question_on_contract_sse_stream(async_client: AsyncClient, sample_contract_user):
    user = sample_contract_user["user"]
    contract = sample_contract_user["contract"]

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    with patch("ai_engine.services.llm_service.LLMService.ask_question_stream", return_value=["Token1 ", "Token2 ", "Token3"]):
        response = await async_client.post(
            f"/contracts/{contract.id}/ask",
            headers=headers,
            json={"question": "What is the termination period?"}
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        content = response.text
        assert 'data: {"chunk": "Token1 "}' in content
        assert 'data: {"chunk": "Token2 "}' in content


@pytest.mark.asyncio
async def test_ask_question_contract_not_found(async_client: AsyncClient, sample_contract_user):
    user = sample_contract_user["user"]

    token = create_access_token(data={"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.post(
        "/contracts/999999/ask",
        headers=headers,
        json={"question": "What is the liability clause?"}
    )
    assert response.status_code == 404
    assert "Contract Not Found." in response.json()["detail"]
