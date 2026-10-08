from unittest.mock import AsyncMock
from types import SimpleNamespace

import pytest
import httpx
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.contract import Contract, ContractAnalysis, ContractStatus, RiskLevel
from app.models.user import User
from app.auth.password import verify_password
from app.schemas.admin import AdminPasswordChangeRequest
from app.repositories.contract_repository import ContractRepository
from app.repositories.user_repository import UserRepository
from app.services.admin_service import AdminService
from app.database.database import get_db
from app.dependencies.auth import get_current_admin
from app.main import app
from app.schemas.user import (
    RequestEmailChangeRequest,
    UpdateUsernameRequest,
    VerifyEmailChangeRequest,
)
from app.services import admin_service as admin_service_module


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    async def set(self, key, value, ex=None):
        self.values[key] = value
        self.expirations[key] = ex
        return True

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, *keys):
        removed = 0
        for key in keys:
            if key in self.values:
                del self.values[key]
                self.expirations.pop(key, None)
                removed += 1
        return removed


@pytest.mark.asyncio
async def test_dashboard_queries_run_sequentially_on_shared_session():
    service = AdminService()
    events = []

    async def user_stats(**kwargs):
        events.append("users")
        return {"total_users": 10, "active_users": 8, "admin_users": 2}

    async def contracts_by_deletion_status(*, db, is_deleted):
        events.append("deleted" if is_deleted else "non_deleted")
        return 2 if is_deleted else 7

    async def contracts_by_status(**kwargs):
        events.append("status")
        return {"COMPLETED": 7}

    async def analyses_by_risk(**kwargs):
        events.append("risk")
        return {"LOW": 3}

    service.user_repository = AsyncMock()
    service.contract_repository = AsyncMock()
    service.user_repository.get_user_summary_stats.side_effect = user_stats
    service.contract_repository.count_contracts_by_deletion_status.side_effect = (
        contracts_by_deletion_status
    )
    service.contract_repository.count_contracts_by_status.side_effect = contracts_by_status
    service.contract_repository.count_analyses_by_risk.side_effect = analyses_by_risk
    db = object()

    result = await service.get_dashboard_stats(db)

    assert events == [
        "users",
        "non_deleted",
        "deleted",
        "status",
        "risk",
    ]
    assert result.total_users == 10
    assert result.total_contracts == 7
    assert result.total_non_deleted_contracts == 7
    assert result.total_deleted_contracts == 2
    assert result.contracts_by_status == {"COMPLETED": 7}
    assert result.analyses_by_risk == {"LOW": 3}


@pytest.mark.asyncio
async def test_dashboard_stats_exclude_soft_deleted_contracts_from_all_metrics(
    db_session,
):
    user = User(
        username="dashboard-user",
        email="dashboard-user@example.com",
        password_hash="test-hash",
    )
    active_contract = Contract(
        user=user,
        original_filename="active.pdf",
        stored_filename="active.pdf",
        file_path="1/active.pdf",
        file_size=10,
        content_type="application/pdf",
        status=ContractStatus.COMPLETED,
    )
    active_contract.analyses.append(
        ContractAnalysis(
            summary="Active contract analysis",
            risk_score=25,
            risk_level=RiskLevel.LOW,
            analysis_version=1,
        )
    )
    deleted_contract = Contract(
        user=user,
        original_filename="deleted.pdf",
        stored_filename="deleted.pdf",
        file_path="1/deleted.pdf",
        file_size=10,
        content_type="application/pdf",
        status=ContractStatus.FAILED,
        is_deleted=True,
    )
    deleted_contract.analyses.append(
        ContractAnalysis(
            summary="Deleted contract analysis",
            risk_score=90,
            risk_level=RiskLevel.HIGH,
            analysis_version=1,
        )
    )
    db_session.add(user)
    db_session.add_all([active_contract, deleted_contract])
    await db_session.commit()

    stats = await AdminService().get_dashboard_stats(db_session)

    assert stats.total_contracts == 1
    assert stats.total_non_deleted_contracts == 1
    assert stats.total_deleted_contracts == 1
    assert stats.contracts_by_status == {"COMPLETED": 1}
    assert stats.analyses_by_risk == {"LOW": 1}


@pytest.mark.asyncio
async def test_dashboard_stats_endpoint_returns_live_database_metrics(db_session):
    overrides_before = app.dependency_overrides.copy()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_admin] = lambda: SimpleNamespace(
        id=1,
        is_admin=True,
        is_active=True,
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/admin/dashboard/stats")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides_before)

    assert response.status_code == 200
    assert response.json() == {
        "total_users": 0,
        "active_users": 0,
        "admin_users": 0,
        "total_contracts": 0,
        "total_non_deleted_contracts": 0,
        "total_deleted_contracts": 0,
        "contracts_by_status": {},
        "analyses_by_risk": {},
    }


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
async def test_admin_username_change_checks_duplicates_and_notifies(db_session):
    user = User(
        username="old-name",
        email="username-user@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()
    service = AdminService()
    service.email_service = AsyncMock()

    result = await service.update_user_username(
        db_session, user.id, UpdateUsernameRequest(username=" new-name ")
    )

    assert result.username == "new-name"
    service.email_service.send_admin_change_notification.assert_awaited_once()
    assert service.email_service.send_admin_change_notification.await_args.kwargs[
        "email"
    ] == user.email


@pytest.mark.asyncio
async def test_admin_username_change_rolls_back_when_notification_fails(db_session):
    user = User(
        username="old-name-fail",
        email="username-fail@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()
    service = AdminService()
    service.email_service = AsyncMock()
    service.email_service.send_admin_change_notification.side_effect = HTTPException(
        status_code=502, detail="Email delivery failed"
    )

    with pytest.raises(HTTPException):
        await service.update_user_username(
            db_session, user.id, UpdateUsernameRequest(username="new-name-fail")
        )

    await db_session.refresh(user)
    assert user.username == "old-name-fail"


@pytest.mark.asyncio
async def test_admin_password_change_hashes_password_notifies_and_returns_user(
    db_session,
):
    user = User(
        username="password-change-user",
        email="password-change-user@example.com",
        password_hash="old-hash",
    )
    db_session.add(user)
    await db_session.commit()
    service = AdminService()
    service.email_service = AsyncMock()

    result = await service.update_user_password(
        db_session,
        user.id,
        AdminPasswordChangeRequest(new_password="NewSecurePass456!"),
    )

    await db_session.refresh(user)
    assert verify_password("NewSecurePass456!", user.password_hash)
    assert user.password_hash != "NewSecurePass456!"
    assert result.id == user.id
    assert "password" not in result.model_dump()
    service.email_service.send_password_changed_notification.assert_awaited_once_with(
        email=user.email,
        username=user.username,
    )


@pytest.mark.asyncio
async def test_admin_password_change_rolls_back_when_notification_fails(db_session):
    original_hash = "old-password-hash"
    user = User(
        username="password-change-fail-user",
        email="password-change-fail-user@example.com",
        password_hash=original_hash,
    )
    db_session.add(user)
    await db_session.commit()
    service = AdminService()
    service.email_service = AsyncMock()
    service.email_service.send_password_changed_notification.side_effect = (
        HTTPException(status_code=502, detail="Email delivery failed")
    )

    with pytest.raises(HTTPException):
        await service.update_user_password(
            db_session,
            user.id,
            AdminPasswordChangeRequest(new_password="NewSecurePass456!"),
        )

    await db_session.refresh(user)
    assert user.password_hash == original_hash


@pytest.mark.asyncio
async def test_admin_email_change_request_stores_pending_email_and_sends_otp(
    db_session, monkeypatch
):
    user = User(
        username="email-request-user",
        email="old-email@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()
    redis = FakeRedis()
    monkeypatch.setattr(admin_service_module, "get_redis", lambda: redis)
    service = AdminService()
    service.otp_service = AsyncMock()
    service.otp_service.generate_otp.return_value = "123456"
    service.otp_service.send_otp_email.return_value = None

    result = await service.request_user_email_change(
        db_session,
        user.id,
        RequestEmailChangeRequest(new_email=" New.Email@example.com "),
    )

    assert result["email"] == "new.email@example.com"
    assert redis.values[f"admin:email_change:{user.id}"] == "new.email@example.com"
    service.otp_service.generate_otp.assert_awaited_once_with(
        purpose="admin_email_change",
        identifier=f"{user.id}:new.email@example.com",
    )
    service.otp_service.send_otp_email.assert_awaited_once_with(
        email="new.email@example.com",
        otp_code="123456",
        purpose="email change",
    )
    assert user.email == "old-email@example.com"


@pytest.mark.asyncio
async def test_admin_email_change_request_cleans_redis_if_otp_send_fails(
    db_session, monkeypatch
):
    user = User(
        username="email-fail-user",
        email="email-fail-old@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()
    redis = FakeRedis()
    monkeypatch.setattr(admin_service_module, "get_redis", lambda: redis)
    service = AdminService()
    service.otp_service = AsyncMock()
    service.otp_service.generate_otp.return_value = "654321"
    service.otp_service.send_otp_email.side_effect = HTTPException(
        status_code=502, detail="Email delivery failed"
    )

    with pytest.raises(HTTPException):
        await service.request_user_email_change(
            db_session,
            user.id,
            RequestEmailChangeRequest(new_email="email-fail-new@example.com"),
        )

    assert f"admin:email_change:{user.id}" not in redis.values
    service.otp_service.invalidate_otp.assert_awaited_once_with(
        purpose="admin_email_change",
        identifier=f"{user.id}:email-fail-new@example.com",
    )


@pytest.mark.asyncio
async def test_admin_email_confirmation_updates_only_after_otp_and_notifies_both(
    db_session, monkeypatch
):
    user = User(
        username="email-confirm-user",
        email="confirm-old@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()
    redis = FakeRedis()
    redis.values[f"admin:email_change:{user.id}"] = "confirm-new@example.com"
    monkeypatch.setattr(admin_service_module, "get_redis", lambda: redis)
    service = AdminService()
    service.otp_service = AsyncMock()
    service.email_service = AsyncMock()

    result = await service.confirm_user_email_change(
        db_session,
        user.id,
        VerifyEmailChangeRequest(
            new_email="confirm-new@example.com",
            otp_code="123456",
        ),
    )

    assert result.email == "confirm-new@example.com"
    service.otp_service.verify_otp.assert_awaited_once_with(
        purpose="admin_email_change",
        identifier=f"{user.id}:confirm-new@example.com",
        input_otp="123456",
    )
    assert [
        call.kwargs["email"]
        for call in service.email_service.send_email_changed_notification.await_args_list
    ] == ["confirm-old@example.com", "confirm-new@example.com"]
    assert f"admin:email_change:{user.id}" not in redis.values


@pytest.mark.asyncio
async def test_admin_email_confirmation_keeps_old_email_when_otp_is_invalid(
    db_session, monkeypatch
):
    user = User(
        username="email-invalid-user",
        email="invalid-old@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()
    redis = FakeRedis()
    redis.values[f"admin:email_change:{user.id}"] = "invalid-new@example.com"
    monkeypatch.setattr(admin_service_module, "get_redis", lambda: redis)
    service = AdminService()
    service.otp_service = AsyncMock()
    service.email_service = AsyncMock()
    service.otp_service.verify_otp.side_effect = HTTPException(
        status_code=400, detail="OTP is invalid or has expired."
    )

    with pytest.raises(HTTPException):
        await service.confirm_user_email_change(
            db_session,
            user.id,
            VerifyEmailChangeRequest(
                new_email="invalid-new@example.com",
                otp_code="000000",
            ),
        )

    await db_session.refresh(user)
    assert user.email == "invalid-old@example.com"
    service.email_service.send_email_changed_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_email_confirmation_rolls_back_when_notice_fails(
    db_session, monkeypatch
):
    user = User(
        username="email-notice-fail-user",
        email="notice-fail-old@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    await db_session.commit()
    redis = FakeRedis()
    redis.values[f"admin:email_change:{user.id}"] = "notice-fail-new@example.com"
    monkeypatch.setattr(admin_service_module, "get_redis", lambda: redis)
    service = AdminService()
    service.otp_service = AsyncMock()
    service.email_service = AsyncMock()
    service.email_service.send_email_changed_notification.side_effect = HTTPException(
        status_code=502, detail="Email delivery failed"
    )

    with pytest.raises(HTTPException):
        await service.confirm_user_email_change(
            db_session,
            user.id,
            VerifyEmailChangeRequest(
                new_email="notice-fail-new@example.com",
                otp_code="123456",
            ),
        )

    await db_session.refresh(user)
    assert user.email == "notice-fail-old@example.com"


def test_new_admin_user_change_routes_are_rate_limited():
    from app.core.rate_limit import RateLimiter
    from app.api.admin import admin_router
    from app.dependencies.auth import get_current_admin
    from app.schemas.user import UserResponse

    expected_paths = {
        "/admin/users/{user_id}/username",
        "/admin/users/{user_id}/password",
        "/admin/users/{user_id}/email/request",
        "/admin/users/{user_id}/email/confirm",
    }
    routes = {
        route.path: route
        for route in admin_router.routes
        if route.path in expected_paths
    }

    assert set(routes) == expected_paths
    for route in routes.values():
        assert any(
            isinstance(dependency.call, RateLimiter)
            for dependency in route.dependant.dependencies
        )
        assert any(
            dependency.call is get_current_admin
            for dependency in route.dependant.dependencies
        )

    password_route = routes["/admin/users/{user_id}/password"]
    assert password_route.response_model is UserResponse


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
