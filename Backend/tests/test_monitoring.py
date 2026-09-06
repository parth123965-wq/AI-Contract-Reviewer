import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import Base, get_db
from app.models.user import User
from app.auth.password import hash_password
from app.core.monitoring import (
    get_system_resources,
    get_process_metrics,
    get_db_health,
    get_redis_health,
    get_full_monitoring_report
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


async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as db:
        normal_user = User(
            username="normaluser",
            email="user@example.com",
            password_hash=hash_password("password123"),
            is_active=True,
            is_verified=True,
            is_admin=False
        )
        admin_user = User(
            username="adminuser",
            email="admin@example.com",
            password_hash=hash_password("adminpassword123"),
            is_active=True,
            is_verified=True,
            is_admin=True
        )
        db.add(normal_user)
        db.add(admin_user)
        await db.commit()

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_monitoring_functions_direct():
    resources = get_system_resources()
    assert "cpu" in resources
    assert "memory" in resources
    assert "disk" in resources

    metrics = get_process_metrics()
    assert "pid" in metrics
    assert "python_version" in metrics
    assert "uptime_seconds" in metrics

    async with TestingSessionLocal() as db:
        db_health = await get_db_health(db)
        assert db_health["connected"] is True
        assert db_health["status"] == "healthy"

        redis_health = await get_redis_health()
        assert "status" in redis_health

        report = await get_full_monitoring_report(db)
        assert "overall_status" in report
        assert "system" in report
        assert "process" in report
        assert "services" in report
        assert "performance" in report
        assert "http_requests" in report["performance"]
        assert "llm_api_calls" in report["performance"]
        assert "vector_search" in report["performance"]
        assert "database_queries" in report["performance"]


@pytest.mark.asyncio
async def test_monitoring_admin_access_success(async_client: AsyncClient):
    # Login as admin
    login_res = await async_client.post(
        "/admin/auth/login",
        json={"email": "admin@example.com", "password": "adminpassword123"}
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Access monitoring system endpoint
    sys_res = await async_client.get("/admin/monitoring/system", headers=headers)
    assert sys_res.status_code == 200
    data = sys_res.json()
    assert "overall_status" in data
    assert "system" in data
    assert "process" in data
    assert "services" in data

    # Access monitoring health endpoint
    health_res = await async_client.get("/admin/monitoring/health", headers=headers)
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert "status" in health_data
    assert "database" in health_data
    assert "redis" in health_data


@pytest.mark.asyncio
async def test_monitoring_normal_user_access_forbidden(async_client: AsyncClient):
    # Login as normal user
    login_res = await async_client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "password123"}
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to access admin monitoring endpoints
    sys_res = await async_client.get("/admin/monitoring/system", headers=headers)
    assert sys_res.status_code == 403
    assert sys_res.json()["detail"] == "Admin privileges required"

    health_res = await async_client.get("/admin/monitoring/health", headers=headers)
    assert health_res.status_code == 403
    assert health_res.json()["detail"] == "Admin privileges required"


@pytest.mark.asyncio
async def test_monitoring_unauthenticated_access_unauthorized(async_client: AsyncClient):
    sys_res = await async_client.get("/admin/monitoring/system")
    assert sys_res.status_code == 401

    health_res = await async_client.get("/admin/monitoring/health")
    assert health_res.status_code == 401
