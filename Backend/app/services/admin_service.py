from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from typing import Optional
from sqlalchemy import select, func

from app.auth.password import verify_password
from app.auth.jwt import create_access_token
from app.repositories.user_repository import UserRepository
from app.repositories.contract_repository import ContractRepository
from app.schemas.user import UserResponse, LoginResponse
from app.schemas.admin import (
    AdminLoginRequest,
    AdminUserListResponse,
    UserAdminDetailResponse,
    AdminContractListResponse,
    ContractAdminDetailResponse,
    AdminDashboardStats
)
from app.models.contract import ContractStatus
from app.models.user import User

class AdminService:
    def __init__(self):
        self.user_repository = UserRepository()
        self.contract_repository = ContractRepository()

    async def admin_login(self, db: AsyncSession, credentials: AdminLoginRequest) -> LoginResponse:
        user = await self.user_repository.get_user_by_email(db=db, email=credentials.email)
        if user is None or not verify_password(password=credentials.password, password_hash_value=user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )

        if not getattr(user, "is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Admin privileges required"
            )

        token = create_access_token(data={"sub": str(user.id)})
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user)
        )

    async def get_dashboard_stats(self, db: AsyncSession) -> AdminDashboardStats:
        total_users = await self.user_repository.count_users(db=db)
        active_users = await self.user_repository.count_users(db=db, is_active=True)

        result = await db.execute(
            select(func.count(User.id)).where(User.is_admin.is_(True))
        )
        admin_users_count = result.scalar() or 0

        total_contracts = await self.contract_repository.count_all_contracts(db=db)
        contracts_by_status = await self.contract_repository.count_contracts_by_status(db=db)
        analyses_by_risk = await self.contract_repository.count_analyses_by_risk(db=db)

        return AdminDashboardStats(
            total_users=total_users,
            active_users=active_users,
            admin_users=admin_users_count,
            total_contracts=total_contracts,
            contracts_by_status=contracts_by_status,
            analyses_by_risk=analyses_by_risk
        )

    async def list_users(
        self,
        db: AsyncSession,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> AdminUserListResponse:
        skip = (page - 1) * limit
        users = await self.user_repository.get_all_users(
            db=db, skip=skip, limit=limit, search=search, is_active=is_active
        )
        total = await self.user_repository.count_users(db=db, search=search, is_active=is_active)

        user_details = []
        for user in users:
            contract_count = await self.contract_repository.count_all_contracts(db=db, user_id=user.id)
            user_details.append(
                UserAdminDetailResponse(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    is_active=user.is_active,
                    is_admin=user.is_admin,
                    created_at=user.created_at,
                    updated_at=user.updated_at,
                    total_contracts=contract_count
                )
            )

        pages = max(1, (total + limit - 1) // limit) if limit > 0 else 1
        return AdminUserListResponse(
            total=total,
            page=page,
            pages=pages,
            limit=limit,
            users=user_details
        )

    async def get_user_detail(self, db: AsyncSession, user_id: int) -> UserAdminDetailResponse:
        user = await self.user_repository.get_user_by_id(db=db, user_id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        contract_count = await self.contract_repository.count_all_contracts(db=db, user_id=user.id)
        return UserAdminDetailResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            updated_at=user.updated_at,
            total_contracts=contract_count
        )

    async def update_user_status(self, db: AsyncSession, user_id: int, is_active: bool) -> UserResponse:
        user = await self.user_repository.update_user_status(db=db, user_id=user_id, is_active=is_active)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse.model_validate(user)

    async def update_user_role(self, db: AsyncSession, user_id: int, is_admin: bool) -> UserResponse:
        user = await self.user_repository.update_user_role(db=db, user_id=user_id, is_admin=is_admin)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse.model_validate(user)

    async def delete_user(self, db: AsyncSession, user_id: int) -> dict:
        success = await self.user_repository.delete_user(db=db, user_id=user_id)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        return {"message": "User deleted successfully", "user_id": user_id}

    async def list_contracts(
        self,
        db: AsyncSession,
        page: int = 1,
        limit: int = 20,
        status_filter: Optional[ContractStatus] = None,
        user_id: Optional[int] = None,
        search: Optional[str] = None
    ) -> AdminContractListResponse:
        skip = (page - 1) * limit
        contracts = await self.contract_repository.get_all_contracts(
            db=db, skip=skip, limit=limit, status=status_filter, user_id=user_id, search=search
        )
        total = await self.contract_repository.count_all_contracts(
            db=db, status=status_filter, user_id=user_id, search=search
        )

        contract_responses = []
        for c in contracts:
            resp = ContractAdminDetailResponse.model_validate(c)
            if c.user:
                resp.username = c.user.username
                resp.user_email = c.user.email
            contract_responses.append(resp)

        pages = max(1, (total + limit - 1) // limit) if limit > 0 else 1
        return AdminContractListResponse(
            total=total,
            page=page,
            pages=pages,
            limit=limit,
            contracts=contract_responses
        )

    async def get_contract_detail(self, db: AsyncSession, contract_id: int) -> ContractAdminDetailResponse:
        contract = await self.contract_repository.get_contract_by_id(db=db, contract_id=contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        resp = ContractAdminDetailResponse.model_validate(contract)
        if contract.user:
            resp.username = contract.user.username
            resp.user_email = contract.user.email
        return resp

    async def update_contract_status(self, db: AsyncSession, contract_id: int, new_status: ContractStatus):
        contract = await self.contract_repository.get_contract_by_id(db=db, contract_id=contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        updated = await self.contract_repository.update_status(db=db, contract=contract, status=new_status)
        return updated

    async def delete_contract(self, db: AsyncSession, contract_id: int) -> dict:
        contract = await self.contract_repository.get_contract_by_id(db=db, contract_id=contract_id)
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        await self.contract_repository.soft_delete_contract(db=db, contract=contract)
        return {"message": "Contract deleted successfully", "contract_id": contract_id}

def get_admin_service() -> AdminService:
    return AdminService()
