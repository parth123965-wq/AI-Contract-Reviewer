from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from typing import Optional
from app.models.contract import Contract, ContractAnalysis, ContractStatus
from datetime import datetime, timezone
from app.models.user import User

class ContractRepository:
    
    async def create_contract(
        self,
        db: AsyncSession,
        contract: Contract
    ) -> Contract:
        db.add(contract)
        await db.commit()
        await db.refresh(contract)
        return contract
    
    async def get_contract_by_id(
        self,
        db: AsyncSession,
        contract_id: int,
        user_id: Optional[int] = None
    ) -> Optional[Contract]:
        conditions = [
            Contract.id == contract_id,
            Contract.is_deleted.is_(False)
        ]
        if user_id is not None:
            conditions.append(Contract.user_id == user_id)
        statement = select(Contract).options(
            selectinload(Contract.user),
            selectinload(Contract.analyses)
        ).where(*conditions)
        result = await db.execute(statement=statement)
        return result.scalar_one_or_none()
    
    async def get_user_contracts(
        self,
        db: AsyncSession,
        user_id: int
    ) -> list[Contract]:
        statement = select(Contract).options(
            selectinload(Contract.user),
            selectinload(Contract.analyses)
        ).where(
            Contract.user_id == user_id, 
            Contract.is_deleted.is_(False)
        )
        result = await db.execute(statement=statement)
        return list(result.scalars().all())
    
    async def update_contract(
        self,
        db: AsyncSession,
        contract: Contract
    ) -> Contract:
        await db.commit()
        await db.refresh(contract)
        return contract
    
    async def soft_delete_contract(
        self,
        db: AsyncSession,
        contract: Contract
    ) -> Contract:
        contract.is_deleted = True
        contract.deleted_at = datetime.now(timezone.utc)
        return await self.update_contract(
            db=db,
            contract=contract
        )
    
    async def get_next_analysis_version(
        self,
        db: AsyncSession,
        contract_id: int
    ) -> int:
        statement = select(func.max(ContractAnalysis.analysis_version)).where(
            ContractAnalysis.contract_id == contract_id
        )
        result = await db.execute(statement)
        latest_version = result.scalar()

        if latest_version is None:
            return 1

        return latest_version + 1
    
    async def update_status(
        self,
        db: AsyncSession,
        contract: Contract,
        status: ContractStatus
    ) -> Contract:
        contract.status = status
        await db.commit()
        await db.refresh(contract)
        return contract

    async def get_all_contracts(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        status: Optional[ContractStatus] = None,
        user_id: Optional[int] = None,
        search: Optional[str] = None
    ) -> list[Contract]:
        statement = select(Contract).options(
            selectinload(Contract.user),
            selectinload(Contract.analyses)
        ).outerjoin(User, Contract.user_id == User.id).where(Contract.is_deleted.is_(False))

        if status:
            statement = statement.where(Contract.status == status)
        if user_id:
            statement = statement.where(Contract.user_id == user_id)
        if search and search.strip():
            clean_search = search.strip()
            search_pattern = f"%{clean_search}%"
            conditions = [
                Contract.original_filename.ilike(search_pattern),
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern)
            ]
            if clean_search.isdigit():
                conditions.append(Contract.id == int(clean_search))
            statement = statement.where(or_(*conditions))
        statement = statement.order_by(Contract.id.desc()).offset(skip).limit(limit)
        result = await db.execute(statement)
        return list(result.scalars().all())

    async def count_all_contracts(
        self,
        db: AsyncSession,
        status: Optional[ContractStatus] = None,
        user_id: Optional[int] = None,
        search: Optional[str] = None
    ) -> int:
        statement = select(func.count(Contract.id)).outerjoin(User, Contract.user_id == User.id).where(Contract.is_deleted.is_(False))
        if status:
            statement = statement.where(Contract.status == status)
        if user_id:
            statement = statement.where(Contract.user_id == user_id)
        if search and search.strip():
            clean_search = search.strip()
            search_pattern = f"%{clean_search}%"
            conditions = [
                Contract.original_filename.ilike(search_pattern),
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern)
            ]
            if clean_search.isdigit():
                conditions.append(Contract.id == int(clean_search))
            statement = statement.where(or_(*conditions))
        result = await db.execute(statement)
        return result.scalar() or 0

    async def count_contracts_by_status(self, db: AsyncSession) -> dict:
        statement = select(Contract.status, func.count(Contract.id)).where(
            Contract.is_deleted.is_(False)
        ).group_by(Contract.status)
        results = (await db.execute(statement)).all()
        return {status.value if hasattr(status, 'value') else str(status): count for status, count in results}

    async def count_analyses_by_risk(self, db: AsyncSession) -> dict:
        statement = select(ContractAnalysis.risk_level, func.count(ContractAnalysis.id)).group_by(ContractAnalysis.risk_level)
        results = (await db.execute(statement)).all()
        return {
            (risk.value if hasattr(risk, 'value') else str(risk)) if risk is not None else "UNANALYZED": count
            for risk, count in results
        }