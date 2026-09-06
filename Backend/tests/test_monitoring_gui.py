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

from app.main import app
from app.database.database import Base, get_db
from app.models.user import User
from app.models.contract import Contract
from app.auth.password import hash_password
from app.auth.jwt import create_access_token

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
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def seed_users(db_session: AsyncSession):
    admin = User(
        username="dashadmin",
        email="dashadmin@example.com",
        password_hash=hash_password("Pass123!"),
        is_admin=True,
        is_active=True,
        is_verified=True
    )
    regular = User(
        username="dashuser",
        email="dashuser@example.com",
        password_hash=hash_password("Pass123!"),
        is_admin=False,
        is_active=True,
        is_verified=True
    )
    db_session.add_all([admin, regular])
    await db_session.commit()
    await db_session.refresh(admin)
    await db_session.refresh(regular)
    return {"admin": admin, "regular": regular}


@pytest.mark.asyncio
async def test_monitoring_dashboard_gui_admin_success(async_client: AsyncClient, seed_users):
    admin = seed_users["admin"]
    token = create_access_token(data={"sub": str(admin.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get("/admin/monitoring/dashboard", headers=headers)
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "System Monitoring & Observation" in response.text
    assert "fetchMetrics" in response.text


@pytest.mark.asyncio
async def test_monitoring_dashboard_gui_non_admin_forbidden(async_client: AsyncClient, seed_users):
    regular = seed_users["regular"]
    token = create_access_token(data={"sub": str(regular.id)})
    headers = {"Authorization": f"Bearer {token}"}

    response = await async_client.get("/admin/monitoring/dashboard", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_monitoring_dashboard_gui_unauthenticated(async_client: AsyncClient):
    response = await async_client.get("/admin/monitoring/dashboard")
    assert response.status_code == 401
