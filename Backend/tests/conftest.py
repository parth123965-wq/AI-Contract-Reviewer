import os
import sys
from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.update(
    {
        "APP_NAME": "Test Contract Reviewer",
        "APP_VERSION": "test",
        "DEBUG": "false",
        "PRODUCTION": "false",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "SECRET_KEY": "test-secret-key-that-is-not-used-outside-tests",
        "SUPABASE_URL": "https://test-project.supabase.co",
        "SUPABASE_SECRET_KEY": "test-supabase-secret-key",
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "EMBEDDING_MODEL": "test-embedding-model",
        "LOG_LEVEL": "CRITICAL",
        "PINECONE_API_KEY": "test-pinecone-key",
        "PINECONE_INDEX_NAME": "contracts",
        "PINECONE_CLOUD": "aws",
        "PINECONE_REGION": "us-east-1",
        "AI_MODEL_NAME": "test-model",
        "BREVO_API_KEY": "test-brevo-key",
        "REDIS_URL": "redis://localhost:6379/15",
        "GMAIL_SENDER": "sender@gmail.com",
        "OTP_LENGTH": "6",
        "OTP_EXPIRE_SECONDS": "300",
        "OTP_COOLDOWN_SECONDS": "60",
        "OTP_MAX_ATTEMPTS": "5",
        "ALLOWED_ORIGINS": "http://localhost",
    }
)

from app.database.database import Base
from app.models.contract import Contract, ContractAnalysis  # noqa: F401
from app.models.user import User  # noqa: F401


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()
