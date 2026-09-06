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
from fastapi import HTTPException

from app.main import app
from app.database.database import Base, get_db
from app.models.user import User
from app.models.contract import Contract, ContractStatus
from app.auth.password import hash_password
from app.services.admin_service import AdminService, get_admin_service
from app.schemas.admin import AdminLoginRequest

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
async def seed_users_and_contracts(db_session: AsyncSession):
    admin_user = User(
        username="admin_hero",
        email="admin_hero@example.com",
        password_hash=hash_password("adminpass123"),
        is_active=True,
        is_verified=True,
        is_admin=True
    )
    inactive_admin = User(
        username="inactive_admin",
        email="inactive_admin@example.com",
        password_hash=hash_password("adminpass123"),
        is_active=False,
        is_verified=True,
        is_admin=True
    )
    regular_user = User(
        username="regular_guy",
        email="regular@example.com",
        password_hash=hash_password("userpass123"),
        is_active=True,
        is_verified=True,
        is_admin=False
    )
    db_session.add_all([admin_user, inactive_admin, regular_user])
    await db_session.commit()
    await db_session.refresh(admin_user)
    await db_session.refresh(regular_user)

    contract = Contract(
        user_id=regular_user.id,
        original_filename="service_agreement.pdf",
        stored_filename="uuid_agreement.pdf",
        file_path="/uploads/uuid_agreement.pdf",
        file_size=2048,
        content_type="application/pdf",
        status=ContractStatus.UPLOADED
    )
    db_session.add(contract)
    await db_session.commit()
    await db_session.refresh(contract)

    return {
        "admin": admin_user,
        "inactive_admin": inactive_admin,
        "regular": regular_user,
        "contract": contract
    }


@pytest.fixture
def service():
    return AdminService()


@pytest.mark.asyncio
async def test_admin_login_success(db_session: AsyncSession, service: AdminService, seed_users_and_contracts):
    req = AdminLoginRequest(email="admin_hero@example.com", password="adminpass123")
    res = await service.admin_login(db=db_session, credentials=req)
    assert res.access_token is not None
    assert res.user.email == "admin_hero@example.com"
    assert res.user.is_admin is True


@pytest.mark.asyncio
async def test_admin_login_inactive_account(db_session: AsyncSession, service: AdminService, seed_users_and_contracts):
    req = AdminLoginRequest(email="inactive_admin@example.com", password="adminpass123")
    with pytest.raises(HTTPException) as exc_info:
        await service.admin_login(db=db_session, credentials=req)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Account is inactive"


@pytest.mark.asyncio
async def test_admin_login_non_admin(db_session: AsyncSession, service: AdminService, seed_users_and_contracts):
    req = AdminLoginRequest(email="regular@example.com", password="userpass123")
    with pytest.raises(HTTPException) as exc_info:
        await service.admin_login(db=db_session, credentials=req)
    assert exc_info.value.status_code == 403
    assert "Admin privileges required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_admin_login_invalid_credentials(db_session: AsyncSession, service: AdminService, seed_users_and_contracts):
    req = AdminLoginRequest(email="admin_hero@example.com", password="wrongpassword")
    with pytest.raises(HTTPException) as exc_info:
        await service.admin_login(db=db_session, credentials=req)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid email or password"


@pytest.mark.asyncio
async def test_admin_list_users_and_detail(db_session: AsyncSession, service: AdminService, seed_users_and_contracts):
    user_list = await service.list_users(db=db_session, page=1, limit=10, search="regular")
    assert user_list.total == 1
    assert user_list.users[0].username == "regular_guy"
    assert user_list.users[0].total_contracts == 1

    regular_id = seed_users_and_contracts["regular"].id
    detail = await service.get_user_detail(db=db_session, user_id=regular_id)
    assert detail.id == regular_id
    assert detail.email == "regular@example.com"
    assert detail.total_contracts == 1


@pytest.mark.asyncio
async def test_admin_get_user_detail_not_found(db_session: AsyncSession, service: AdminService):
    with pytest.raises(HTTPException) as exc_info:
        await service.get_user_detail(db=db_session, user_id=99999)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found"


@pytest.mark.asyncio
async def test_admin_update_user_status_and_role(db_session: AsyncSession, service: AdminService, seed_users_and_contracts):
    regular_id = seed_users_and_contracts["regular"].id

    # Deactivate user
    updated = await service.update_user_status(db=db_session, user_id=regular_id, is_active=False)
    assert updated.is_active is False

    # Promote to admin
    promoted = await service.update_user_role(db=db_session, user_id=regular_id, is_admin=True)
    assert promoted.is_admin is True


@pytest.mark.asyncio
async def test_admin_update_user_status_not_found(db_session: AsyncSession, service: AdminService):
    with pytest.raises(HTTPException) as exc_info:
        await service.update_user_status(db=db_session, user_id=88888, is_active=False)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_delete_user_success_and_not_found(db_session: AsyncSession, service: AdminService, seed_users_and_contracts):
    regular_id = seed_users_and_contracts["regular"].id

    result = await service.delete_user(db=db_session, user_id=regular_id)
    assert result["message"] == "User deleted successfully"

    with pytest.raises(HTTPException) as exc_info:
        await service.delete_user(db=db_session, user_id=regular_id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_list_contracts_and_detail(db_session: AsyncSession, service: AdminService, seed_users_and_contracts):
    contract_list = await service.list_contracts(db=db_session, status_filter=ContractStatus.UPLOADED)
    assert contract_list.total == 1
    assert contract_list.contracts[0].original_filename == "service_agreement.pdf"
    assert contract_list.contracts[0].username == "regular_guy"

    contract_id = seed_users_and_contracts["contract"].id
    detail = await service.get_contract_detail(db=db_session, contract_id=contract_id)
    assert detail.id == contract_id
    assert detail.user_email == "regular@example.com"


@pytest.mark.asyncio
async def test_admin_get_contract_detail_not_found(db_session: AsyncSession, service: AdminService):
    with pytest.raises(HTTPException) as exc_info:
        await service.get_contract_detail(db=db_session, contract_id=77777)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_update_contract_status_and_delete(db_session: AsyncSession, service: AdminService, seed_users_and_contracts):
    contract_id = seed_users_and_contracts["contract"].id

    updated = await service.update_contract_status(db=db_session, contract_id=contract_id, new_status=ContractStatus.COMPLETED)
    assert updated.status == ContractStatus.COMPLETED

    del_res = await service.delete_contract(db=db_session, contract_id=contract_id)
    assert del_res["message"] == "Contract deleted successfully"


@pytest.mark.asyncio
async def test_admin_delete_contract_not_found(db_session: AsyncSession, service: AdminService):
    with pytest.raises(HTTPException) as exc_info:
        await service.delete_contract(db=db_session, contract_id=66666)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_admin_dashboard_stats(db_session: AsyncSession, service: AdminService, seed_users_and_contracts):
    stats = await service.get_dashboard_stats(db=db_session)
    assert stats.total_users == 3
    assert stats.active_users == 2
    assert stats.admin_users == 2
    assert stats.total_contracts == 1


def test_admin_service_factory():
    instance = get_admin_service()
    assert isinstance(instance, AdminService)
