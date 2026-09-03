from sqlalchemy.orm import Session
from sqlalchemy import select , func
from typing import Optional
from app.models.contract import Contract , ContractAnalysis , ContractStatus
from datetime import datetime , timezone

class ContractRepository:
    
    def create_contract(
        self,
        db: Session,
        contract: Contract
    ) -> Contract:
        db.add(contract)
        db.commit()
        db.refresh(contract)
        return contract
    
    def get_contract_by_id(
        self,
        db: Session,
        contract_id: int,
        user_id: Optional[int] = None
    ) -> Optional[Contract]:
        conditions = [
            Contract.id == contract_id,
            Contract.is_deleted.is_(False)
        ]
        if user_id is not None:
            conditions.append(Contract.user_id == user_id)
        statement = select(Contract).where(*conditions)
        return db.execute(statement=statement).scalar_one_or_none()
    
    def get_user_contracts(
        self,
        db: Session,
        user_id: int
    ) -> list[Contract]:
        statement = select(Contract).where(
            Contract.user_id == user_id, 
            Contract.is_deleted.is_(False)
        )
        return db.execute(statement=statement).scalars().all()
    
    def update_contract(
        self,
        db: Session,
        contract: Contract
    ) -> Contract:
        db.commit()
        db.refresh(contract)
        return contract
    
    def soft_delete_contract(
        self,
        db: Session,
        contract: Contract
    ) -> Contract:
        contract.is_deleted = True
        contract.deleted_at = datetime.now(timezone.utc)
        return self.update_contract(
            db=db,
            contract=contract
        )
    
    def get_next_analysis_version(
        self,
        db: Session,
        contract_id: int
    ) -> int:
        latest_version = (
            db.query(func.max(ContractAnalysis.analysis_version))
            .filter(ContractAnalysis.contract_id == contract_id)
            .scalar()
        )

        if latest_version is None:
            return 1

        return latest_version + 1
    
    def update_status(
        self,
        db: Session,
        contract: Contract,
        status: ContractStatus
    ) -> Contract:
        contract.status = status
        db.commit()
        db.refresh(contract)
        return contract

    def get_all_contracts(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 20,
        status: Optional[ContractStatus] = None,
        user_id: Optional[int] = None,
        search: Optional[str] = None
    ) -> list[Contract]:
        from app.models.user import User
        from sqlalchemy import or_
        statement = select(Contract).outerjoin(User, Contract.user_id == User.id).where(Contract.is_deleted.is_(False))
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
        return list(db.execute(statement).scalars().all())

    def count_all_contracts(
        self,
        db: Session,
        status: Optional[ContractStatus] = None,
        user_id: Optional[int] = None,
        search: Optional[str] = None
    ) -> int:
        from app.models.user import User
        from sqlalchemy import or_
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
        return db.execute(statement).scalar() or 0

    def count_contracts_by_status(self, db: Session) -> dict:
        results = (
            db.query(Contract.status, func.count(Contract.id))
            .filter(Contract.is_deleted.is_(False))
            .group_by(Contract.status)
            .all()
        )
        return {status.value if hasattr(status, 'value') else str(status): count for status, count in results}

    def count_analyses_by_risk(self, db: Session) -> dict:
        results = (
            db.query(ContractAnalysis.risk_level, func.count(ContractAnalysis.id))
            .group_by(ContractAnalysis.risk_level)
            .all()
        )
        return {
            (risk.value if hasattr(risk, 'value') else str(risk)) if risk is not None else "UNANALYZED": count
            for risk, count in results
        }