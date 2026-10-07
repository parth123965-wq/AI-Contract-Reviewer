from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.contract import Contract, ContractAnalysis, ContractStatus
from app.models.user import User
from app.repositories.contract_repository import ContractRepository
from app.repositories.user_repository import UserRepository
from app.services.admin_service import AdminService


@pytest.mark.asyncio
async def test_dashboard_queries_run_sequentially_on_shared_session():
    service = AdminService()
    events = []

    async def user_stats(**kwargs):
        events.append("users")
        return {"total_users": 10, "active_users": 8, "admin_users": 2}

    async def total_contracts(**kwargs):
        events.append("contracts")
        return 7

    async def contracts_by_status(**kwargs):
        events.append("status")
        return {"COMPLETED": 7}

    async def analyses_by_risk(**kwargs):
        events.append("risk")
        return {"LOW": 3}

    service.user_repository = AsyncMock()
    service.contract_repository = AsyncMock()
    service.user_repository.get_user_summary_stats.side_effect = user_stats
    service.contract_repository.count_all_contracts.side_effect = total_contracts
    service.contract_repository.count_contracts_by_status.side_effect = contracts_by_status
    service.contract_repository.count_analyses_by_risk.side_effect = analyses_by_risk
    db = object()

    result = await service.get_dashboard_stats(db)

    assert events == ["users", "contracts", "status", "risk"]
    assert result.total_users == 10
    assert result.total_contracts == 7
    assert result.contracts_by_status == {"COMPLETED": 7}
    assert result.analyses_by_risk == {"LOW": 3}


@pytest.mark.asyncio
async def test_delete_user_removes_all_supabase_objects_before_database_account():
    service = AdminService()
    user = SimpleNamespace(id=7)
    events = []
    service.user_repository = AsyncMock()
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.user_repository.get_user_by_id.return_value = user
    service.contract_repository.get_storage_paths_by_user_id.return_value = [
        "7/active.pdf",
        "7/soft-deleted.pdf",
    ]

    async def remove_many(paths):
        events.append(("storage", paths))

    async def delete_user(*, db, user_id):
        events.append(("database", user_id))
        return True

    service.contract_storage.remove_many.side_effect = remove_many
    service.user_repository.delete_user.side_effect = delete_user

    result = await service.delete_user(db=object(), user_id=7)

    assert result == {"message": "User deleted successfully", "user_id": 7}
    assert events == [
        ("storage", ["7/active.pdf", "7/soft-deleted.pdf"]),
        ("database", 7),
    ]


@pytest.mark.asyncio
async def test_delete_user_does_not_delete_account_when_storage_cleanup_fails():
    service = AdminService()
    service.user_repository = AsyncMock()
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.user_repository.get_user_by_id.return_value = SimpleNamespace(id=7)
    service.contract_repository.get_storage_paths_by_user_id.return_value = [
        "7/contract.pdf"
    ]
    service.contract_storage.remove_many.side_effect = RuntimeError(
        "Supabase unavailable"
    )

    with pytest.raises(HTTPException) as error:
        await service.delete_user(db=object(), user_id=7)

    assert error.value.status_code == 502
    service.user_repository.delete_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_missing_user_skips_storage_and_database_cleanup():
    service = AdminService()
    service.user_repository = AsyncMock()
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.user_repository.get_user_by_id.return_value = None

    with pytest.raises(HTTPException) as error:
        await service.delete_user(db=object(), user_id=7)

    assert error.value.status_code == 404
    service.contract_repository.get_storage_paths_by_user_id.assert_not_awaited()
    service.contract_storage.remove_many.assert_not_awaited()
    service.user_repository.delete_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_repository_deletes_analyses_contracts_and_user(db_session):
    user = User(
        username="delete-me",
        email="delete-me@example.com",
        password_hash="test-hash",
    )
    contract = Contract(
        user=user,
        original_filename="agreement.pdf",
        stored_filename="agreement.pdf",
        file_path="1/agreement.pdf",
        file_size=10,
        content_type="application/pdf",
        status=ContractStatus.UPLOADED,
        is_deleted=True,
    )
    contract.analyses.append(ContractAnalysis(summary="Test analysis"))
    db_session.add(user)
    await db_session.commit()

    paths = await ContractRepository().get_storage_paths_by_user_id(
        db_session, user.id
    )
    assert paths == ["1/agreement.pdf"]

    assert await UserRepository().delete_user(db_session, user.id) is True
    assert await db_session.scalar(select(func.count()).select_from(ContractAnalysis)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Contract)) == 0
    assert await db_session.scalar(select(func.count()).select_from(User)) == 0


@pytest.mark.asyncio
async def test_admin_contract_listing_includes_soft_deleted_records():
    service = AdminService()
    service.contract_repository = AsyncMock()
    service.contract_repository.get_all_contracts.return_value = []
    service.contract_repository.count_all_contracts.return_value = 0
    db = object()

    result = await service.list_contracts(db=db)

    service.contract_repository.get_all_contracts.assert_awaited_once_with(
        db=db,
        skip=0,
        limit=20,
        status=None,
        user_id=None,
        search=None,
        include_deleted=True,
    )
    service.contract_repository.count_all_contracts.assert_awaited_once_with(
        db=db,
        status=None,
        user_id=None,
        search=None,
        include_deleted=True,
    )
    assert result.contracts == []
    assert result.total == 0


@pytest.mark.asyncio
async def test_admin_permanent_delete_removes_storage_before_database_records():
    service = AdminService()
    contract = SimpleNamespace(file_path="7/contract.pdf", is_deleted=True)
    events = []
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.contract_repository.get_contract_by_id.return_value = contract

    async def remove(path):
        events.append(("storage", path))

    async def permanently_delete_contract(*, db, contract_id):
        events.append(("database", contract_id))

    service.contract_storage.remove.side_effect = remove
    service.contract_repository.permanently_delete_contract.side_effect = (
        permanently_delete_contract
    )
    db = object()

    result = await service.delete_contract(db=db, contract_id=12)

    assert result == {
        "message": "Contract permanently deleted successfully",
        "contract_id": 12,
    }
    assert events == [
        ("storage", "7/contract.pdf"),
        ("database", 12),
    ]
    service.contract_repository.get_contract_by_id.assert_awaited_once_with(
        db=db,
        contract_id=12,
        include_deleted=True,
    )


@pytest.mark.asyncio
async def test_admin_permanent_delete_keeps_database_record_when_storage_fails():
    service = AdminService()
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.contract_repository.get_contract_by_id.return_value = SimpleNamespace(
        file_path="7/contract.pdf",
        is_deleted=False,
    )
    service.contract_storage.remove.side_effect = RuntimeError("Storage unavailable")

    with pytest.raises(HTTPException) as error:
        await service.delete_contract(db=object(), contract_id=12)

    assert error.value.status_code == 502
    service.contract_repository.permanently_delete_contract.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_soft_delete_keeps_storage_and_rejects_deleted_contract():
    service = AdminService()
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    active_contract = SimpleNamespace(is_deleted=False)
    service.contract_repository.get_contract_by_id.return_value = active_contract

    result = await service.soft_delete_contract(db=object(), contract_id=12)

    assert result == {
        "message": "Contract soft-deleted successfully",
        "contract_id": 12,
    }
    service.contract_repository.soft_delete_contract.assert_awaited_once()
    service.contract_storage.remove.assert_not_awaited()

    service.contract_repository.get_contract_by_id.return_value = SimpleNamespace(
        is_deleted=True
    )
    with pytest.raises(HTTPException) as error:
        await service.soft_delete_contract(db=object(), contract_id=12)

    assert error.value.status_code == 409
