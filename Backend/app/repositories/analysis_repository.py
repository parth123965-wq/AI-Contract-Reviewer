from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.contract import ContractAnalysis


class AnalysisRepository:

    async def create_analysis(
        self,
        db: AsyncSession,
        analysis: ContractAnalysis
    ) -> ContractAnalysis:
        db.add(analysis)
        await db.commit()
        await db.refresh(analysis)
        return analysis

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