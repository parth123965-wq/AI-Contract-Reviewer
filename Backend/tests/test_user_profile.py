import pytest
import pytest_asyncio
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
async def test_update_email_success():
    async with TestingSessionLocal() as session:
        user = User(
            username="testuser",
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
        response = await client.patch("/users/me/email", json={"email": "newemail@example.com"}, headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newemail@example.com"

@pytest.mark.asyncio
async def test_change_password_success():
    async with TestingSessionLocal() as session:
        user = User(
            username="passworduser",
            email="password@example.com",
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
        response = await client.post(
            "/users/me/change-password",
            json={"current_password": "oldpassword123", "new_password": "newpassword123"},
            headers=headers
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Password changed successfully."
