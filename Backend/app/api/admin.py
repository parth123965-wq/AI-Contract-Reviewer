from fastapi import APIRouter, Depends, Response, Query, status, HTTPException
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
    AdminLoginRequest,
    AdminUserListResponse,
    UserAdminDetailResponse,
    UserStatusUpdate,
    UserRoleUpdate,
    AdminContractListResponse,
    ContractAdminDetailResponse,
    ContractStatusUpdate,
    AdminDashboardStats
)
from app.core.rate_limit import RateLimiter
from fastapi.responses import HTMLResponse
from pathlib import Path


admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


# =======================================================
# ADMIN AUTHENTICATION
# =======================================================

@admin_router.post(
    "/auth/login",
    summary="Admin User Login",
    description="Authenticate system administrator with email and password. Grants administrative JWT token and sets secure session cookie.",
    dependencies=[Depends(RateLimiter(times=5, seconds=60, prefix="admin_login"))]
)
async def admin_login(
    response: Response,
    credentials: AdminLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
):
    login_response = await service.admin_login(db=db, credentials=credentials)

    response.set_cookie(
        key="ai_contract_session",
        value=login_response.access_token,
        httponly=True,
        samesite="lax",
        secure=False
    )

    return {
        "message": "Admin login successful",
        "access_token": login_response.access_token,
        "token_type": "bearer",
        "user": login_response.user
    }


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
    summary="Delete Contract Document (Admin)",
    description="Administrative deletion of any contract document from the system.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="admin_contracts"))]
)
async def delete_contract(
    contract_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
):
    return await service.delete_contract(db=db, contract_id=contract_id)


# =======================================================
# SYSTEM MONITORING (ADMIN ONLY)
# =======================================================

from app.core.monitoring import get_full_monitoring_report, get_db_health, get_redis_health

@admin_router.get(
    "/monitoring/system",
    summary="Get System Resource & Health Monitoring Report (Admin Only)",
    description="Retrieve comprehensive system resources (CPU, RAM, Disk), application process metrics, database connectivity, and Redis health status.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="admin_monitoring_system"))]
)
async def get_system_monitoring(
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    return await get_full_monitoring_report(db=db)


@admin_router.get(
    "/monitoring/health",
    summary="Get Subsystem Health Summary (Admin Only)",
    description="Quick operational health check of database and Redis services.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="admin_monitoring_health"))]
)
async def get_subsystem_health(
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    db_health = await get_db_health(db=db)
    redis_health = await get_redis_health()
    return {
        "status": "healthy" if db_health.get("connected") and redis_health.get("status") in ["healthy", "disabled"] else "degraded",
        "database": db_health,
        "redis": redis_health
    }

@admin_router.get(
    "/monitoring/dashboard",
    response_class=HTMLResponse,
    summary="Get System Monitoring Visual GUI Dashboard (Admin Only)",
    description="Interactive visual HTML dashboard displaying real-time CPU, RAM, Disk, process metrics, and DB/Redis latency graphs.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="admin_monitoring_dashboard"))]
)
async def get_monitoring_dashboard(
    admin: Annotated[User, Depends(get_current_admin)]
):
    template_path = Path(__file__).resolve().parent.parent / "templates" / "monitoring_dashboard.html"
    if not template_path.exists():
        raise HTTPException(status_code=500, detail="Monitoring dashboard template missing")
    return HTMLResponse(content=template_path.read_text(encoding="utf-8"))


