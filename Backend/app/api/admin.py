from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Annotated, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.dependencies.auth import get_current_admin
from app.models.user import User
from app.models.contract import ContractStatus
from app.services.admin_service import AdminService, get_admin_service
from app.schemas.user import UserResponse
from app.schemas.contract import ContractResponse
from app.schemas.admin import (
    AdminUserListResponse,
    AdminEmailChangeRequestResponse,
    AdminPasswordChangeRequest,
    AdminDiagnosticsResponse,
    AdminLogTailResponse,
    UserAdminDetailResponse,
    UserStatusUpdate,
    UserRoleUpdate,
    AdminContractListResponse,
    ContractAdminDetailResponse,
    ContractAdminActionResponse,
    ContractStatusUpdate,
    AdminDashboardStats
)
from app.schemas.user import (
    RequestEmailChangeRequest,
    UpdateUsernameRequest,
    VerifyEmailChangeRequest,
)
from app.core.rate_limit import RateLimiter
from app.services.health_diagnostics import get_log_tail, get_system_diagnostics


admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


@admin_router.get(
    "/diagnostics",
    response_model=AdminDiagnosticsResponse,
    summary="Get Backend Health Diagnostics",
    description="View this backend instance's uptime, CPU, memory, disk, database latency, active threads, and overall status.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="admin_diagnostics"))],
)
async def get_admin_diagnostics(
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminDiagnosticsResponse:
    return await get_system_diagnostics(db=db)


@admin_router.get(
    "/diagnostics/logs",
    response_model=AdminLogTailResponse,
    summary="Get Recent Backend Logs",
    description="View the latest structured logs held in memory by this running backend instance.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="admin_diagnostics_logs"))],
)
async def get_admin_log_tail(
    admin: Annotated[User, Depends(get_current_admin)],
    limit: int = Query(default=100, ge=50, le=100),
) -> AdminLogTailResponse:
    return get_log_tail(limit=limit)


# =======================================================
# DASHBOARD STATS
# =======================================================

@admin_router.get(
    "/dashboard/stats",
    response_model=AdminDashboardStats,
    summary="Get System Dashboard Metrics",
    description="Retrieve high-level metrics including total users, active users, total uploaded contracts, status breakdown, and risk distribution.",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="admin_stats"))]
)
async def get_dashboard_stats(
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> AdminDashboardStats:
    return await service.get_dashboard_stats(db=db)


# =======================================================
# USER MANAGEMENT
# =======================================================

@admin_router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="List All System Users (Paginated)",
    description="Retrieve paginated user list with optional search filter by email or username, and status filtering.",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="admin_users"))]
)
async def list_users(
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None)
) -> AdminUserListResponse:
    return await service.list_users(
        db=db, page=page, limit=limit, search=search, is_active=is_active
    )


@admin_router.get(
    "/users/{user_id}",
    response_model=UserAdminDetailResponse,
    summary="Get User Administrative Details",
    description="Retrieve detailed profile information, account status, and total uploaded contracts count for a target user ID.",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="admin_users"))]
)
async def get_user_detail(
    user_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> UserAdminDetailResponse:
    return await service.get_user_detail(db=db, user_id=user_id)


@admin_router.patch(
    "/users/{user_id}/status",
    response_model=UserResponse,
    summary="Update User Account Status",
    description="Activate or suspend a user account.",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="admin_users"))]
)
async def update_user_status(
    user_id: int,
    body: UserStatusUpdate,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> UserResponse:
    return await service.update_user_status(db=db, user_id=user_id, is_active=body.is_active)


@admin_router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
    summary="Update User Role",
    description="Grant or revoke administrative permissions for a target user account.",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="admin_users"))]
)
async def update_user_role(
    user_id: int,
    body: UserRoleUpdate,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> UserResponse:
    return await service.update_user_role(db=db, user_id=user_id, is_admin=body.is_admin)


@admin_router.patch(
    "/users/{user_id}/username",
    response_model=UserResponse,
    summary="Change User Username (Admin)",
    description="Change a user's username and notify them by email.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="admin_users"))]
)
async def update_user_username(
    user_id: int,
    body: UpdateUsernameRequest,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> UserResponse:
    return await service.update_user_username(
        db=db, user_id=user_id, request=body
    )


@admin_router.patch(
    "/users/{user_id}/password",
    response_model=UserResponse,
    summary="Change User Password (Admin)",
    description="Set a new password for a user and notify them by email. The password is never included in the response or notification.",
    dependencies=[Depends(RateLimiter(times=10, seconds=60, prefix="admin_user_password"))]
)
async def update_user_password(
    user_id: int,
    body: AdminPasswordChangeRequest,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> UserResponse:
    return await service.update_user_password(
        db=db, user_id=user_id, request=body
    )


@admin_router.post(
    "/users/{user_id}/email/request",
    response_model=AdminEmailChangeRequestResponse,
    summary="Request User Email Change (Admin)",
    description="Send an OTP to a proposed email address. The user's stored email is unchanged until the OTP is verified.",
    dependencies=[Depends(RateLimiter(times=5, seconds=60, prefix="admin_user_email_request"))]
)
async def request_user_email_change(
    user_id: int,
    body: RequestEmailChangeRequest,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> AdminEmailChangeRequestResponse:
    return await service.request_user_email_change(
        db=db, user_id=user_id, request=body
    )


@admin_router.post(
    "/users/{user_id}/email/confirm",
    response_model=UserResponse,
    summary="Confirm User Email Change (Admin)",
    description="Verify the OTP sent to the proposed email address and then update the user's stored email.",
    dependencies=[Depends(RateLimiter(times=10, seconds=60, prefix="admin_user_email_confirm"))]
)
async def confirm_user_email_change(
    user_id: int,
    body: VerifyEmailChangeRequest,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> UserResponse:
    return await service.confirm_user_email_change(
        db=db, user_id=user_id, request=body
    )


@admin_router.delete(
    "/users/{user_id}",
    summary="Delete User Account",
    description="Permanently delete a user account and associated resources.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="admin_users"))]
)
async def delete_user(
    user_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
):
    return await service.delete_user(db=db, user_id=user_id)


# =======================================================
# CONTRACT MANAGEMENT
# =======================================================

@admin_router.get(
    "/contracts",
    response_model=AdminContractListResponse,
    summary="List All Platform Contracts (Paginated)",
    description="Retrieve paginated list of all system contracts across all users with status, search, and user filtering.",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="admin_contracts"))]
)
async def list_contracts(
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    search: Optional[str] = Query(default=None)
) -> AdminContractListResponse:
    parsed_status = None
    if status and status.strip() and status.lower() != "all":
        try:
            parsed_status = ContractStatus(status.strip().upper())
        except ValueError:
            parsed_status = None

    return await service.list_contracts(
        db=db, page=page, limit=limit, status_filter=parsed_status, user_id=user_id, search=search
    )


@admin_router.get(
    "/contracts/{contract_id}",
    response_model=ContractAdminDetailResponse,
    summary="Get Contract Administrative Details",
    description="Retrieve contract document details along with owner username and email information.",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="admin_contracts"))]
)
async def get_contract_detail(
    contract_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> ContractAdminDetailResponse:
    return await service.get_contract_detail(db=db, contract_id=contract_id)


@admin_router.patch(
    "/contracts/{contract_id}/status",
    response_model=ContractResponse,
    summary="Update Contract Processing Status",
    description="Manually override or update contract processing status (e.g. processing, completed, error).",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="admin_contracts"))]
)
async def update_contract_status(
    contract_id: int,
    body: ContractStatusUpdate,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> ContractResponse:
    try:
        new_status = ContractStatus(body.status.strip().upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid contract status: {body.status}")
    return await service.update_contract_status(db=db, contract_id=contract_id, new_status=new_status)


@admin_router.delete(
    "/contracts/{contract_id}",
    response_model=ContractAdminActionResponse,
    summary="Delete Contract Document (Admin)",
    description="Permanently delete a contract, its analysis history, and its Supabase Storage file.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="admin_contracts"))]
)
async def delete_contract(
    contract_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> ContractAdminActionResponse:
    return await service.delete_contract(db=db, contract_id=contract_id)


@admin_router.patch(
    "/contracts/{contract_id}/soft-delete",
    response_model=ContractAdminActionResponse,
    summary="Soft-delete Contract Document (Admin)",
    description="Hide a contract from the user's active list while retaining its database record, analysis history, and Supabase Storage file.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="admin_contracts"))]
)
async def soft_delete_contract(
    contract_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> ContractAdminActionResponse:
    return await service.soft_delete_contract(db=db, contract_id=contract_id)


@admin_router.patch(
    "/contracts/{contract_id}/recover",
    response_model=ContractAdminActionResponse,
    summary="Recover Soft-deleted Contract (Admin)",
    description="Restore a soft-deleted contract to the user's active list without changing its analysis history or Supabase Storage file.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="admin_contracts"))]
)
async def recover_contract(
    contract_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> ContractAdminActionResponse:
    return await service.recover_contract(db=db, contract_id=contract_id)
