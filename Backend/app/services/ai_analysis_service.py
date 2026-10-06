import time
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import AsyncSessionLocal
from app.models.contract import ContractAnalysis , ContractStatus
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.contract_repository import ContractRepository
from app.services.contract_storage import ContractStorage

from ai_engine.graph.graph import ContractGraph
from ai_engine.schemas.analysis_result import AnalysisResult
from app.core.logger import get_app_logger

logger = get_app_logger("services.ai_analysis")


class AnalysisService:

    def __init__(self):
        self.contract_repository = ContractRepository()
        self.analysis_repository = AnalysisRepository()
        self.contract_storage = ContractStorage()

        # Compile only once
        self.graph = ContractGraph().compile_graph()

    async def analyze_contract(
        self,
        contract_id: int
    ) -> None:

        async with AsyncSessionLocal() as db:
            try:
                contract = await self.contract_repository.get_contract_by_id(
                    db=db,
                    contract_id=contract_id
                )

                if contract is None:
                    raise ValueError("Contract not found.")

                if contract.is_deleted:
                    raise ValueError("Contract has been deleted.")

                version = await self.analysis_repository.get_next_analysis_version(
                    db=db,
                    contract_id=contract.id
                )

                await self.contract_repository.update_status(
                    db=db,
                    contract=contract,
                    status=ContractStatus.PROCESSING
                )

                start_time = time.perf_counter()

                file_content = await self.contract_storage.download(
                    contract.file_path
                )
                final_state = self.graph.invoke(
                    {
                        "db": db,
                        "contract_id": contract.id,
                        "user_id": contract.user_id,
                        "file_content": file_content,
                        "analysis_version": version,

                        "status": ContractStatus.PROCESSING,
                        "error": None,

                        "extracted_text": "",
                        "chunks": [],
                        "embeddings": [],
                        "query_embedding": [],
                        "retrieved_chunks": [],

                        "summary": "",
                        "risk_score": 0,
                        "suggestions": [],

                        "prompt": "",
                        "llm_response": "",
                        "analysis_result": None,
                        "processing_time_ms": 0,
                    }
                )

                if final_state and (final_state.get("error") or final_state.get("status") == ContractStatus.FAILED):
                    err_msg = final_state.get("error") or "AI pipeline analysis failed."
                    contract.last_error = err_msg
                    await self.contract_repository.update_status(
                        db=db,
                        contract=contract,
                        status=ContractStatus.FAILED
                    )
                    raise RuntimeError(err_msg)

                processing_time = (
                    time.perf_counter() - start_time
                ) * 1000

                # Bug Fix: Await the analysis save here safely while the db session is open
                if final_state and final_state.get("analysis_result"):
                    from app.core.config import settings
                    await self.save_analysis(
                        db=db,
                        contract_id=contract.id,
                        version=version,
                        result=final_state["analysis_result"],
                        model_name=settings.AI_MODEL_NAME or "gemini",
                        processing_time=processing_time
                    )

                await self.contract_repository.update_status(
                    db=db,
                    contract=contract,
                    status=ContractStatus.COMPLETED
                )

                print(
                    f"Analysis completed in {processing_time:.2f} ms"
                )

            except Exception as exc:

                await db.rollback()

                contract = await self.contract_repository.get_contract_by_id(
                    db=db,
                    contract_id=contract_id
                )

                if contract is not None:

                    contract.last_error = str(exc)

                    await self.contract_repository.update_status(
                        db=db,
                        contract=contract,
                        status=ContractStatus.FAILED
                    )

                raise

            finally:
                await db.close()

    async def save_analysis(
        self,
        db: AsyncSession,
        contract_id: int,
        version: int,
        result: AnalysisResult,
        model_name: str,
        processing_time: float
    ):

        analysis = ContractAnalysis(
            contract_id=contract_id,
            analysis_version=version,
            summary=result.summary,
            risk_score=result.risk_score,
            risk_level=result.risk,
            recommendations="\n".join(result.suggestions),
            model_name=model_name,
            confidence_score=result.confidence,
            processing_time_ms=int(processing_time)
        )

        return await self.analysis_repository.create_analysis(
            db=db,
            analysis=analysis
        )


def get_analysis_service() -> AnalysisService:
    return AnalysisService()