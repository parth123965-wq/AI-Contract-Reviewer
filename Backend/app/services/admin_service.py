from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from typing import Optional

from app.repositories.user_repository import UserRepository
from app.repositories.contract_repository import ContractRepository
from app.services.contract_storage import ContractStorage
from app.schemas.user import UserResponse
from app.schemas.admin import (
    AdminUserListResponse,
    UserAdminDetailResponse,
    AdminContractListResponse,
    ContractAdminDetailResponse,
    AdminDashboardStats
)
from app.models.contract import ContractStatus
from app.core.logger import get_app_logger
from app.services.email_service import email_service

logger = get_app_logger("services.admin")

class AdminService:
    def __init__(self):
        self.user_repository = UserRepository()
        self.contract_repository = ContractRepository()
        self.contract_storage = ContractStorage()
        self.email_service = email_service

    async def _notify_admin_change(
        self,
        db: AsyncSession,
        email: str,
        username: str,
        action: str,
        details: str,
    ) -> None:
        try:
            await self.email_service.send_admin_change_notification(
                email=email,
                username=username,
                action=action,
                details=details,
            )
        except Exception:
            await db.rollback()
            logger.exception(
                "Failed to notify user about an admin change.",
                extra={"action": action},
            )
            raise

    async def _commit_admin_change(self, db: AsyncSession) -> None:
        try:
            await db.commit()
        except Exception:
            await db.rollback()
            raise

    async def get_dashboard_stats(self, db: AsyncSession) -> AdminDashboardStats:
        user_stats = await self.user_repository.get_user_summary_stats(db=db)
        total_contracts = await self.contract_repository.count_all_contracts(db=db)
        contracts_by_status = await self.contract_repository.count_contracts_by_status(db=db)
        analyses_by_risk = await self.contract_repository.count_analyses_by_risk(db=db)

        return AdminDashboardStats(
            total_users=user_stats["total_users"],
            active_users=user_stats["active_users"],
            admin_users=user_stats["admin_users"],
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

        user_ids = [user.id for user in users]
        contract_counts_map = await self.contract_repository.get_contract_counts_by_user_ids(db=db, user_ids=user_ids)

        user_details = [
            UserAdminDetailResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                is_verified=user.is_verified,
                is_active=user.is_active,
                is_admin=user.is_admin,
                created_at=user.created_at,
                updated_at=user.updated_at,
                total_contracts=contract_counts_map.get(user.id, 0)
            )
            for user in users
        ]

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
            is_verified=user.is_verified,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            updated_at=user.updated_at,
            total_contracts=contract_count
        )

    async def update_user_status(self, db: AsyncSession, user_id: int, is_active: bool) -> UserResponse:
        user = await self.user_repository.get_user_by_id(db=db, user_id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.is_active == is_active:
            return UserResponse.model_validate(user)

        await self.user_repository.update_user_status(
            db=db, user_id=user_id, is_active=is_active, commit=False
        )
        state = "active" if is_active else "suspended"
        await self._notify_admin_change(
            db=db,
            email=user.email,
            username=user.username,
            action="An administrator changed your account status.",
            details=f"Your account is now {state}.",
        )
        await self._commit_admin_change(db)
        await db.refresh(user)
        return UserResponse.model_validate(user)

    async def update_user_role(self, db: AsyncSession, user_id: int, is_admin: bool) -> UserResponse:
        user = await self.user_repository.get_user_by_id(db=db, user_id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.is_admin == is_admin:
            return UserResponse.model_validate(user)

        await self.user_repository.update_user_role(
            db=db, user_id=user_id, is_admin=is_admin, commit=False
        )
        role = "administrator" if is_admin else "standard user"
        await self._notify_admin_change(
            db=db,
            email=user.email,
            username=user.username,
            action="An administrator changed your account role.",
            details=f"Your account role is now {role}.",
        )
        await self._commit_admin_change(db)
        await db.refresh(user)
        return UserResponse.model_validate(user)

    async def delete_user(self, db: AsyncSession, user_id: int) -> dict:
        user = await self.user_repository.get_user_by_id(db=db, user_id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        object_paths = await self.contract_repository.get_storage_paths_by_user_id(
            db=db,
            user_id=user_id,
        )
        await self._notify_admin_change(
            db=db,
            email=user.email,
            username=user.username,
            action="An administrator requested permanent deletion of your account.",
            details="Your account and its associated contract data are being permanently deleted.",
        )
        try:
            await self.contract_storage.remove_many(object_paths)
        except Exception as exc:
            await db.rollback()
            logger.exception(
                "Failed to remove contract files before deleting user.",
                extra={"user_id": user_id, "file_count": len(object_paths)},
            )
            raise HTTPException(
                status_code=502,
                detail="Failed to remove the user's contract files; the account was not deleted.",
            ) from exc

        success = await self.user_repository.delete_user(
            db=db, user_id=user_id, commit=False
        )
        if not success:
            await db.rollback()
            raise HTTPException(status_code=404, detail="User not found")
        await self._commit_admin_change(db)
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
            db=db, skip=skip, limit=limit, status=status_filter, user_id=user_id,
            search=search, include_deleted=True
        )
        total = await self.contract_repository.count_all_contracts(
            db=db, status=status_filter, user_id=user_id, search=search,
            include_deleted=True
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
        contract = await self.contract_repository.get_contract_by_id(
            db=db, contract_id=contract_id, include_deleted=True
        )
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        resp = ContractAdminDetailResponse.model_validate(contract)
        if contract.user:
            resp.username = contract.user.username
            resp.user_email = contract.user.email
        return resp

    async def update_contract_status(self, db: AsyncSession, contract_id: int, new_status: ContractStatus):
        contract = await self.contract_repository.get_contract_by_id(
            db=db, contract_id=contract_id, include_deleted=True
        )
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        if contract.status == new_status:
            return contract

        old_status = contract.status.value
        await self.contract_repository.update_status(
            db=db, contract=contract, status=new_status, commit=False
        )
        if not contract.user:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Contract owner is unavailable; the change was not applied.",
            )
        await self._notify_admin_change(
            db=db,
            email=contract.user.email,
            username=contract.user.username,
            action=f'An administrator changed the status of your contract "{contract.original_filename}".',
            details=f"The contract status changed from {old_status} to {new_status.value}.",
        )
        await self._commit_admin_change(db)
        await db.refresh(contract)
        return contract

    async def delete_contract(self, db: AsyncSession, contract_id: int) -> dict:
        contract = await self.contract_repository.get_contract_by_id(
            db=db, contract_id=contract_id, include_deleted=True
        )
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")

        await self.contract_repository.permanently_delete_contract(
            db=db, contract_id=contract_id, commit=False
        )
        if not contract.user:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Contract owner is unavailable; the contract was not deleted.",
            )
        await self._notify_admin_change(
            db=db,
            email=contract.user.email,
            username=contract.user.username,
            action=f'An administrator requested permanent deletion of your contract "{contract.original_filename}".',
            details="The contract, its analysis history, and its stored PDF are being permanently deleted.",
        )
        try:
            await self.contract_storage.remove(contract.file_path)
        except Exception as exc:
            await db.rollback()
            logger.exception(
                "Failed to remove contract file before permanent deletion.",
                extra={"contract_id": contract_id},
            )
            raise HTTPException(
                status_code=502,
                detail="Failed to remove the contract file; the contract was not deleted.",
            ) from exc

        await self._commit_admin_change(db)
        return {
            "message": "Contract permanently deleted successfully",
            "contract_id": contract_id,
        }

    async def soft_delete_contract(
        self, db: AsyncSession, contract_id: int
    ) -> dict:
        contract = await self.contract_repository.get_contract_by_id(
            db=db, contract_id=contract_id, include_deleted=True
        )
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        if contract.is_deleted:
            raise HTTPException(
                status_code=409, detail="Contract is already soft-deleted"
            )

        if not contract.user:
            raise HTTPException(
                status_code=409,
                detail="Contract owner is unavailable; the change was not applied.",
            )
        await self.contract_repository.soft_delete_contract(
            db=db, contract=contract, commit=False
        )
        await self._notify_admin_change(
            db=db,
            email=contract.user.email,
            username=contract.user.username,
            action=f'An administrator moved your contract "{contract.original_filename}" to deleted contracts.',
            details="The contract can be recovered by an administrator. Its PDF and analysis history remain stored.",
        )
        await self._commit_admin_change(db)
        return {
            "message": "Contract soft-deleted successfully",
            "contract_id": contract_id,
        }

    async def recover_contract(self, db: AsyncSession, contract_id: int) -> dict:
        contract = await self.contract_repository.get_contract_by_id(
            db=db, contract_id=contract_id, include_deleted=True
        )
        if not contract:
            raise HTTPException(status_code=404, detail="Contract not found")
        if not contract.is_deleted:
            raise HTTPException(
                status_code=409, detail="Contract is not soft-deleted"
            )

        if not contract.user:
            raise HTTPException(
                status_code=409,
                detail="Contract owner is unavailable; the change was not applied.",
            )
        await self.contract_repository.recover_contract(
            db=db, contract=contract, commit=False
        )
        await self._notify_admin_change(
            db=db,
            email=contract.user.email,
            username=contract.user.username,
            action=f'An administrator recovered your contract "{contract.original_filename}".',
            details="The contract is available in your active contracts again.",
        )
        await self._commit_admin_change(db)
        return {
            "message": "Contract recovered successfully",
            "contract_id": contract_id,
        }

def get_admin_service() -> AdminService:
    return AdminService()
