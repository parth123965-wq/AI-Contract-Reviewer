from fastapi import APIRouter, Depends, Response, Query, status
from typing import Annotated, Optional
from sqlalchemy.orm import Session

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

admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


# =======================================================
# ADMIN AUTHENTICATION
# =======================================================

@admin_router.post("/auth/login")
def admin_login(
    response: Response,
    credentials: AdminLoginRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
):
    login_response = service.admin_login(db=db, credentials=credentials)

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

@admin_router.get("/dashboard/stats", response_model=AdminDashboardStats)
def get_dashboard_stats(
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> AdminDashboardStats:
    return service.get_dashboard_stats(db=db)


# =======================================================
# USER MANAGEMENT
# =======================================================

@admin_router.get("/users", response_model=AdminUserListResponse)
def list_users(
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None),
    is_active: Optional[bool] = Query(default=None)
) -> AdminUserListResponse:
    return service.list_users(
        db=db, page=page, limit=limit, search=search, is_active=is_active
    )


@admin_router.get("/users/{user_id}", response_model=UserAdminDetailResponse)
def get_user_detail(
    user_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> UserAdminDetailResponse:
    return service.get_user_detail(db=db, user_id=user_id)


@admin_router.patch("/users/{user_id}/status", response_model=UserResponse)
def update_user_status(
    user_id: int,
    body: UserStatusUpdate,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> UserResponse:
    return service.update_user_status(db=db, user_id=user_id, is_active=body.is_active)


@admin_router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    body: UserRoleUpdate,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> UserResponse:
    return service.update_user_role(db=db, user_id=user_id, is_admin=body.is_admin)


@admin_router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
):
    return service.delete_user(db=db, user_id=user_id)


# =======================================================
# CONTRACT MANAGEMENT
# =======================================================

@admin_router.get("/contracts", response_model=AdminContractListResponse)
def list_contracts(
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
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

    return service.list_contracts(
        db=db, page=page, limit=limit, status_filter=parsed_status, user_id=user_id, search=search
    )


@admin_router.get("/contracts/{contract_id}", response_model=ContractAdminDetailResponse)
def get_contract_detail(
    contract_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> ContractAdminDetailResponse:
    return service.get_contract_detail(db=db, contract_id=contract_id)


@admin_router.patch("/contracts/{contract_id}/status", response_model=ContractResponse)
def update_contract_status(
    contract_id: int,
    body: ContractStatusUpdate,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
) -> ContractResponse:
    try:
        new_status = ContractStatus(body.status.strip().upper())
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid contract status: {body.status}")
    return service.update_contract_status(db=db, contract_id=contract_id, new_status=new_status)


@admin_router.delete("/contracts/{contract_id}")
def delete_contract(
    contract_id: int,
    admin: Annotated[User, Depends(get_current_admin)],
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[AdminService, Depends(get_admin_service)]
):
    return service.delete_contract(db=db, contract_id=contract_id)
