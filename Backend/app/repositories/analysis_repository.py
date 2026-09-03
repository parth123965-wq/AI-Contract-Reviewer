from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.contract import ContractAnalysis


class AnalysisRepository:

    def create_analysis(
        self,
        db: Session,
        analysis: ContractAnalysis
    ) -> ContractAnalysis:
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis

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