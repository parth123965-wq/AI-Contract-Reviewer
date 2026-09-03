import time

from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.models.contract import ContractAnalysis , ContractStatus
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.contract_repository import ContractRepository

from ai_engine.graph.graph import ContractGraph
from ai_engine.schemas.analysis_result import AnalysisResult


class AnalysisService:

    def __init__(self):
        self.contract_repository = ContractRepository()
        self.analysis_repository = AnalysisRepository()

        # Compile only once
        self.graph = ContractGraph().compile_graph()

    def analyze_contract(
        self,
        contract_id: int
    ) -> None:

        db: Session = SessionLocal()

        try:
            contract = self.contract_repository.get_contract_by_id(
                db=db,
                contract_id=contract_id
            )

            if contract is None:
                raise ValueError("Contract not found.")

            if contract.is_deleted:
                raise ValueError("Contract has been deleted.")

            version = self.analysis_repository.get_next_analysis_version(
                db=db,
                contract_id=contract.id
            )

            self.contract_repository.update_status(
                db=db,
                contract=contract,
                status=ContractStatus.PROCESSING
            )

            start_time = time.perf_counter()

            self.graph.invoke(
                {
                    "db": db,
                    "contract_id": contract.id,
                    "user_id": contract.user_id,
                    "file_path": contract.file_path,
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

            processing_time = (
                time.perf_counter() - start_time
            ) * 1000

            self.contract_repository.update_status(
                db=db,
                contract=contract,
                status=ContractStatus.COMPLETED
            )

            print(
                f"Analysis completed in {processing_time:.2f} ms"
            )

        except Exception as exc:

            db.rollback()

            contract = self.contract_repository.get_contract_by_id(
                db=db,
                contract_id=contract_id
            )

            if contract is not None:

                contract.last_error = str(exc)

                self.contract_repository.update_status(
                    db=db,
                    contract=contract,
                    status=ContractStatus.FAILED
                )

            raise

        finally:
            db.close()

    def save_analysis(
        self,
        db: Session,
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

        return self.analysis_repository.create_analysis(
            db=db,
            analysis=analysis
        )


def get_analysis_service() -> AnalysisService:
    return AnalysisService()