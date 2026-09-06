import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base
from app.models.user import User
from app.models.contract import Contract, ContractStatus
from app.auth.password import hash_password
from app.repositories.user_repository import UserRepository
from app.repositories.contract_repository import ContractRepository

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


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
def user_repo():
    return UserRepository()


@pytest_asyncio.fixture
def contract_repo():
    return ContractRepository()


@pytest.mark.asyncio
async def test_user_repository_crud(db_session: AsyncSession, user_repo: UserRepository):
    user = User(
        username="repouser",
        email="repo@example.com",
        password_hash=hash_password("Pass123!"),
        is_verified=False,
        is_active=True
    )

    # Create
    created = await user_repo.create_user(db=db_session, user=user)
    assert created.id is not None

    # Get by email & username & id
    by_email = await user_repo.get_user_by_email(db=db_session, email="repo@example.com")
    assert by_email.id == created.id

    by_username = await user_repo.get_user_by_username(db=db_session, username="repouser")
    assert by_username.id == created.id

    by_id = await user_repo.get_user_by_id(db=db_session, user_id=created.id)
    assert by_id.username == "repouser"

    # Mark verified
    verified = await user_repo.mark_user_verified(db=db_session, user_id=created.id)
    assert verified.is_verified is True

    # Update role & status
    updated_status = await user_repo.update_user_status(db=db_session, user_id=created.id, is_active=False)
    assert updated_status.is_active is False

    updated_role = await user_repo.update_user_role(db=db_session, user_id=created.id, is_admin=True)
    assert updated_role.is_admin is True

    # Count and list users
    total = await user_repo.count_users(db=db_session, search="repo", is_active=False)
    assert total == 1

    all_users = await user_repo.get_all_users(db=db_session, search="repo", is_active=False)
    assert len(all_users) == 1

    # Delete
    deleted = await user_repo.delete_user(db=db_session, user_id=created.id)
    assert deleted is True

    missing = await user_repo.get_user_by_id(db=db_session, user_id=created.id)
    assert missing is None


@pytest.mark.asyncio
async def test_contract_repository_crud(db_session: AsyncSession, user_repo: UserRepository, contract_repo: ContractRepository):
    user = User(
        username="contractrepouser",
        email="contractrepo@example.com",
        password_hash=hash_password("Pass123!"),
        is_verified=True,
        is_active=True
    )
    user = await user_repo.create_user(db=db_session, user=user)

    contract = Contract(
        user_id=user.id,
        original_filename="license.pdf",
        stored_filename="license_uuid.pdf",
        file_path="/tmp/license_uuid.pdf",
        file_size=4096,
        content_type="application/pdf",
        status=ContractStatus.UPLOADED
    )

    created_contract = await contract_repo.create_contract(db=db_session, contract=contract)
    assert created_contract.id is not None

    by_id = await contract_repo.get_contract_by_id(db=db_session, contract_id=created_contract.id, user_id=user.id)
    assert by_id.original_filename == "license.pdf"

    user_contracts = await contract_repo.get_user_contracts(db=db_session, user_id=user.id)
    assert len(user_contracts) == 1

    # Update status
    updated = await contract_repo.update_status(db=db_session, contract=created_contract, status=ContractStatus.COMPLETED)
    assert updated.status == ContractStatus.COMPLETED

    # Counts
    total_count = await contract_repo.count_all_contracts(db=db_session, user_id=user.id)
    assert total_count == 1

    status_counts = await contract_repo.count_contracts_by_status(db=db_session)
    assert status_counts.get("COMPLETED", 0) == 1

    # Soft delete
    soft_deleted = await contract_repo.soft_delete_contract(db=db_session, contract=created_contract)
    assert soft_deleted.is_deleted is True
