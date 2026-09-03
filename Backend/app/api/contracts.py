from fastapi import APIRouter , Depends , UploadFile , File , BackgroundTasks
from typing import Annotated 
from app.database.database import get_db
from app.dependencies.auth import get_current_user
from app.services.contract_service import contract_service , ContractService
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.contract import ContractResponse , ContractListResponse
from app.services.ai_analysis_service import AnalysisService , get_analysis_service

contract_router = APIRouter(
    prefix="/contracts",
    tags=['Contracts']
)

@contract_router.post('/upload')
def upload(
    db: Annotated[Session,Depends(get_db)],
    current_user: Annotated[User,Depends(get_current_user)],
    contract_service: Annotated[ContractService,Depends(contract_service)],
    file: Annotated[UploadFile,File()],
    background_task: BackgroundTasks,
    ai_analysis_service: Annotated[AnalysisService,Depends(get_analysis_service)]
) -> ContractResponse:
    contract = contract_service.upload_contract(
        db=db,
        current_user=current_user,
        file=file
    )
    background_task.add_task(
        ai_analysis_service.analyze_contract,
        contract.id
    )
    return contract
    
@contract_router.get('',response_model=ContractListResponse)
def get_contracts(
    db: Annotated[Session,Depends(get_db)],
    current_user: Annotated[User,Depends(get_current_user)],
    service: Annotated[ContractService,Depends(contract_service)]
) -> ContractListResponse:
    contracts = service.get_user_contracts(
        db=db,
        current_user=current_user
    )
    return {
        "contracts": contracts
    }
    
@contract_router.get('/{contract_id}',response_model=ContractResponse)
def get_contract_by_id(
    db: Annotated[Session,Depends(get_db)],
    current_user: Annotated[User,Depends(get_current_user)],
    service: Annotated[ContractService,Depends(contract_service)],
    contract_id: int
) -> ContractResponse:
    return service.get_contract_by_id(
        db=db,
        contract_id=contract_id,
        current_user=current_user   
    )
    
@contract_router.delete('/{id}')
def delete_contract(
    db: Annotated[Session,Depends(get_db)],
    current_user: Annotated[User,Depends(get_current_user)],
    service: Annotated[ContractService,Depends(contract_service)],
    id: int
):
    service.delete_contract(
        db=db,
        contract_id=id,
        current_user=current_user
    )
    return {"status":"success"}


from pydantic import BaseModel

class QuestionRequest(BaseModel):
    question: str

@contract_router.post('/{contract_id}/ask')
def ask_question_on_contract(
    contract_id: int,
    body: QuestionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(contract_service)]
):
    contract = service.get_contract_by_id(db=db, contract_id=contract_id, current_user=current_user)
    if not contract:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Contract not found")

    from ai_engine.services.embedding_service import EmbeddingService
    from ai_engine.services.vector_store_service import VectorStoreService
    from ai_engine.services.llm_service import LLMService

    emb_service = EmbeddingService()
    vector_store = VectorStoreService()
    llm_service = LLMService()

    chunks = []

    # 1. Search RAG Vector Store
    try:
        q_embeddings = emb_service.create_embeddings([body.question])
        query_emb = q_embeddings[0] if q_embeddings else []
        if query_emb:
            chunks = vector_store.search(
                contract_id=contract_id,
                user_id=current_user.id,
                query_embedding=query_emb,
                top_k=5
            )
    except Exception:
        pass

    # 2. Fallback: Extract directly from contract file if vector store returned empty chunks
    if not chunks:
        from ai_engine.services.text_extractor import TextExtractor
        from ai_engine.services.chunk_service import ChunkService
        if hasattr(contract, "file_path") and contract.file_path:
            try:
                extractor = TextExtractor()
                chunker = ChunkService()
                raw_text = extractor.extract_text(contract.file_path)
                if raw_text:
                    chunks = chunker.chunk_text(raw_text)
            except Exception:
                pass

    answer = llm_service.ask_question(question=body.question, context_chunks=chunks)

    return {
        "question": body.question,
        "answer": answer,
        "context_retrieved": chunks
    }