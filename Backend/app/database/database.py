from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Automatically format postgres:// or postgresql:// to postgresql+asyncpg:// if needed
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Production-grade connection pool configuration:
# - pool_pre_ping: tests liveness before checkout to prevent stale/dropped connections
# - pool_recycle: recycles connections every 30 minutes to prevent provider-side timeouts
# - pool_size & max_overflow: handles traffic bursts without exhausting DB connections
engine = create_async_engine(
    url=db_url,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Backwards compatibility alias for SessionLocal
SessionLocal = AsyncSessionLocal

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
