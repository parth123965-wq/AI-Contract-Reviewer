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
from app.main import app


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
    user = SimpleNamespace(
        id=7, email="owner@example.com", username="owner"
    )
    events = []
    service.user_repository = AsyncMock()
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.email_service = AsyncMock()
    service.user_repository.get_user_by_id.return_value = user
    service.contract_repository.get_storage_paths_by_user_id.return_value = [
        "7/active.pdf",
        "7/soft-deleted.pdf",
    ]

    async def send_email(**kwargs):
        events.append(("email", kwargs["email"]))

    async def remove_many(paths):
        events.append(("storage", paths))

    async def delete_user(*, db, user_id, commit):
        events.append(("database", user_id, commit))
        return True

    service.email_service.send_admin_change_notification.side_effect = send_email
    service.contract_storage.remove_many.side_effect = remove_many
    service.user_repository.delete_user.side_effect = delete_user
    db = AsyncMock()

    result = await service.delete_user(db=db, user_id=7)

    assert result == {"message": "User deleted successfully", "user_id": 7}
    assert events == [
        ("email", user.email),
        ("storage", ["7/active.pdf", "7/soft-deleted.pdf"]),
        ("database", 7, False),
    ]
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_user_does_not_delete_account_when_storage_cleanup_fails():
    service = AdminService()
    service.user_repository = AsyncMock()
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.email_service = AsyncMock()
    service.user_repository.get_user_by_id.return_value = SimpleNamespace(
        id=7, email="owner@example.com", username="owner"
    )
    service.contract_repository.get_storage_paths_by_user_id.return_value = [
        "7/contract.pdf"
    ]
    service.contract_storage.remove_many.side_effect = RuntimeError(
        "Supabase unavailable"
    )

    db = AsyncMock()
    with pytest.raises(HTTPException) as error:
        await service.delete_user(db=db, user_id=7)

    assert error.value.status_code == 502
    service.user_repository.delete_user.assert_not_awaited()
    service.email_service.send_admin_change_notification.assert_awaited_once()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_user_skips_storage_and_database_when_email_fails():
    service = AdminService()
    service.user_repository = AsyncMock()
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.email_service = AsyncMock()
    service.user_repository.get_user_by_id.return_value = SimpleNamespace(
        id=7, email="owner@example.com", username="owner"
    )
    service.contract_repository.get_storage_paths_by_user_id.return_value = [
        "7/contract.pdf"
    ]
    service.email_service.send_admin_change_notification.side_effect = HTTPException(
        status_code=502, detail="Email delivery failed"
    )
    db = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.delete_user(db=db, user_id=7)

    assert error.value.status_code == 502
    service.contract_storage.remove_many.assert_not_awaited()
    service.user_repository.delete_user.assert_not_awaited()
    db.rollback.assert_awaited_once()


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
async def test_admin_user_status_change_is_rolled_back_if_email_fails(db_session):
    user = User(
        username="status-user",
        email="status-user@example.com",
        password_hash="hash",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    service = AdminService()
    service.email_service = AsyncMock()
    service.email_service.send_admin_change_notification.side_effect = HTTPException(
        status_code=502, detail="Email delivery failed"
    )

    with pytest.raises(HTTPException) as error:
        await service.update_user_status(db_session, user.id, is_active=False)

    assert error.value.status_code == 502
    await db_session.refresh(user)
    assert user.is_active is True


@pytest.mark.asyncio
async def test_admin_user_role_change_notifies_then_commits(db_session):
    user = User(
        username="role-user",
        email="role-user@example.com",
        password_hash="hash",
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    service = AdminService()
    service.email_service = AsyncMock()

    result = await service.update_user_role(db_session, user.id, is_admin=True)

    assert result.is_admin is True
    service.email_service.send_admin_change_notification.assert_awaited_once()
    assert service.email_service.send_admin_change_notification.await_args.kwargs[
        "details"
    ] == "Your account role is now administrator."


@pytest.mark.asyncio
async def test_admin_user_status_change_skips_email_when_value_is_unchanged(db_session):
    user = User(
        username="unchanged-user",
        email="unchanged-user@example.com",
        password_hash="hash",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    service = AdminService()
    service.email_service = AsyncMock()

    result = await service.update_user_status(db_session, user.id, is_active=True)

    assert result.is_active is True
    service.email_service.send_admin_change_notification.assert_not_awaited()


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
    contract = SimpleNamespace(
        file_path="7/contract.pdf",
        is_deleted=True,
        original_filename="agreement.pdf",
        user=SimpleNamespace(username="owner", email="owner@example.com"),
    )
    events = []
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.email_service = AsyncMock()
    service.contract_repository.get_contract_by_id.return_value = contract

    async def send_email(**kwargs):
        events.append(("email", kwargs["email"]))

    async def remove(path):
        events.append(("storage", path))

    async def permanently_delete_contract(*, db, contract_id, commit):
        events.append(("database", contract_id, commit))

    service.email_service.send_admin_change_notification.side_effect = send_email
    service.contract_storage.remove.side_effect = remove
    service.contract_repository.permanently_delete_contract.side_effect = (
        permanently_delete_contract
    )
    db = AsyncMock()

    result = await service.delete_contract(db=db, contract_id=12)

    assert result == {
        "message": "Contract permanently deleted successfully",
        "contract_id": 12,
    }
    assert events == [
        ("database", 12, False),
        ("email", "owner@example.com"),
        ("storage", "7/contract.pdf"),
    ]
    db.commit.assert_awaited_once()
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
    service.email_service = AsyncMock()
    service.contract_repository.get_contract_by_id.return_value = SimpleNamespace(
        file_path="7/contract.pdf",
        is_deleted=False,
        original_filename="agreement.pdf",
        user=SimpleNamespace(username="owner", email="owner@example.com"),
    )
    service.contract_storage.remove.side_effect = RuntimeError("Storage unavailable")
    db = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.delete_contract(db=db, contract_id=12)

    assert error.value.status_code == 502
    service.contract_repository.permanently_delete_contract.assert_awaited_once_with(
        db=db, contract_id=12, commit=False
    )
    db.rollback.assert_awaited_once()
    service.email_service.send_admin_change_notification.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_permanent_delete_skips_storage_when_email_fails():
    service = AdminService()
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.email_service = AsyncMock()
    service.contract_repository.get_contract_by_id.return_value = SimpleNamespace(
        file_path="7/contract.pdf",
        is_deleted=False,
        original_filename="agreement.pdf",
        user=SimpleNamespace(username="owner", email="owner@example.com"),
    )
    service.email_service.send_admin_change_notification.side_effect = HTTPException(
        status_code=502, detail="Email delivery failed"
    )
    db = AsyncMock()

    with pytest.raises(HTTPException) as error:
        await service.delete_contract(db=db, contract_id=12)

    assert error.value.status_code == 502
    service.contract_repository.permanently_delete_contract.assert_awaited_once_with(
        db=db, contract_id=12, commit=False
    )
    service.contract_storage.remove.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_stage", ["email", "storage"])
async def test_admin_permanent_delete_rolls_back_database_failure(
    db_session, failure_stage
):
    user = User(
        username=f"delete-{failure_stage}",
        email=f"delete-{failure_stage}@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.flush()
    contract = Contract(
        user=user,
        original_filename="agreement.pdf",
        stored_filename=f"delete-{failure_stage}.pdf",
        file_path=f"{user.id}/delete-{failure_stage}.pdf",
        file_size=10,
        content_type="application/pdf",
        status=ContractStatus.UPLOADED,
    )
    contract.analyses.append(ContractAnalysis(summary="Keep until commit"))
    db_session.add(contract)
    await db_session.commit()
    contract_id = contract.id
    service = AdminService()
    service.email_service = AsyncMock()
    service.contract_storage = AsyncMock()
    if failure_stage == "email":
        service.email_service.send_admin_change_notification.side_effect = (
            HTTPException(status_code=502, detail="Email delivery failed")
        )
    else:
        service.contract_storage.remove.side_effect = RuntimeError(
            "Storage unavailable"
        )

    with pytest.raises(HTTPException):
        await service.delete_contract(db_session, contract_id)

    assert await db_session.scalar(
        select(Contract.id).where(Contract.id == contract_id)
    ) == contract_id
    assert await db_session.scalar(
        select(ContractAnalysis.id).where(
            ContractAnalysis.contract_id == contract_id
        )
    ) is not None
    if failure_stage == "email":
        service.contract_storage.remove.assert_not_awaited()
    else:
        service.contract_storage.remove.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("initially_deleted", "operation"),
    [
        (False, "soft_delete_contract"),
        (True, "recover_contract"),
    ],
)
async def test_admin_contract_visibility_change_rolls_back_when_email_fails(
    db_session, initially_deleted, operation
):
    user = User(
        username="soft-delete-owner",
        email="soft-delete-owner@example.com",
        password_hash="hash",
    )
    contract = Contract(
        user=user,
        original_filename="agreement.pdf",
        stored_filename="soft-delete-agreement.pdf",
        file_path="1/soft-delete-agreement.pdf",
        file_size=10,
        content_type="application/pdf",
        status=ContractStatus.UPLOADED,
        is_deleted=initially_deleted,
    )
    db_session.add(user)
    db_session.add(contract)
    await db_session.commit()
    if initially_deleted:
        await ContractRepository().soft_delete_contract(db_session, contract)

    service = AdminService()
    service.email_service = AsyncMock()
    service.email_service.send_admin_change_notification.side_effect = HTTPException(
        status_code=502, detail="Email delivery failed"
    )

    with pytest.raises(HTTPException):
        await getattr(service, operation)(db_session, contract.id)

    await db_session.refresh(contract)
    assert contract.is_deleted is initially_deleted
    assert (contract.deleted_at is not None) is initially_deleted


@pytest.mark.asyncio
async def test_admin_soft_delete_keeps_storage_and_rejects_deleted_contract():
    service = AdminService()
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.email_service = AsyncMock()
    active_contract = SimpleNamespace(
        is_deleted=False,
        original_filename="agreement.pdf",
        user=SimpleNamespace(username="owner", email="owner@example.com"),
    )
    service.contract_repository.get_contract_by_id.return_value = active_contract
    db = AsyncMock()

    result = await service.soft_delete_contract(db=db, contract_id=12)

    assert result == {
        "message": "Contract soft-deleted successfully",
        "contract_id": 12,
    }
    service.contract_repository.soft_delete_contract.assert_awaited_once_with(
        db=db, contract=active_contract, commit=False
    )
    service.contract_storage.remove.assert_not_awaited()
    service.email_service.send_admin_change_notification.assert_awaited_once()
    db.commit.assert_awaited_once()

    service.contract_repository.get_contract_by_id.return_value = SimpleNamespace(
        is_deleted=True
    )
    with pytest.raises(HTTPException) as error:
        await service.soft_delete_contract(db=object(), contract_id=12)

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_admin_recover_restores_deleted_contract_without_storage_operation():
    service = AdminService()
    service.contract_repository = AsyncMock()
    service.contract_storage = AsyncMock()
    service.email_service = AsyncMock()
    deleted_contract = SimpleNamespace(
        is_deleted=True,
        original_filename="agreement.pdf",
        user=SimpleNamespace(username="owner", email="owner@example.com"),
    )
    service.contract_repository.get_contract_by_id.return_value = deleted_contract
    db = AsyncMock()

    result = await service.recover_contract(db=db, contract_id=12)

    assert result == {
        "message": "Contract recovered successfully",
        "contract_id": 12,
    }
    service.contract_repository.recover_contract.assert_awaited_once_with(
        db=db, contract=deleted_contract, commit=False
    )
    service.contract_storage.remove.assert_not_awaited()
    service.email_service.send_admin_change_notification.assert_awaited_once()
    db.commit.assert_awaited_once()

    service.contract_repository.get_contract_by_id.return_value = SimpleNamespace(
        is_deleted=False
    )
    with pytest.raises(HTTPException) as error:
        await service.recover_contract(db=object(), contract_id=12)

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_admin_contract_status_change_notifies_and_commits():
    service = AdminService()
    service.contract_repository = AsyncMock()
    service.email_service = AsyncMock()
    contract = SimpleNamespace(
        status=ContractStatus.UPLOADED,
        original_filename="agreement.pdf",
        user=SimpleNamespace(username="owner", email="owner@example.com"),
    )
    service.contract_repository.get_contract_by_id.return_value = contract

    async def update_status(*, db, contract, status, commit):
        contract.status = status
        return contract

    service.contract_repository.update_status.side_effect = update_status
    db = AsyncMock()

    result = await service.update_contract_status(
        db, 12, ContractStatus.COMPLETED
    )

    assert result.status == ContractStatus.COMPLETED
    service.email_service.send_admin_change_notification.assert_awaited_once()
    assert service.email_service.send_admin_change_notification.await_args.kwargs[
        "details"
    ] == "The contract status changed from UPLOADED to COMPLETED."
    db.commit.assert_awaited_once()


def test_admin_contract_action_endpoints_declare_response_models():
    paths = app.openapi()["paths"]
    expected_schema = {
        "$ref": "#/components/schemas/ContractAdminActionResponse"
    }
    action_routes = [
        ("/admin/contracts/{contract_id}", "delete"),
        ("/admin/contracts/{contract_id}/soft-delete", "patch"),
        ("/admin/contracts/{contract_id}/recover", "patch"),
    ]

    for path, method in action_routes:
        assert paths[path][method]["responses"]["200"]["content"][
            "application/json"
        ]["schema"] == expected_schema
