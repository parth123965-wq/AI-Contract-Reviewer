from fastapi import APIRouter , Depends , UploadFile , File , BackgroundTasks, HTTPException
from typing import Annotated 
from app.database.database import get_db
from app.dependencies.auth import get_current_user
from app.services.contract_service import contract_service , ContractService
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.contract import ContractResponse , ContractListResponse
from app.services.ai_analysis_service import AnalysisService , get_analysis_service
from pydantic import BaseModel
from ai_engine.services.text_extractor import TextExtractor
from ai_engine.services.chunk_service import ChunkService
from ai_engine.services.embedding_service import EmbeddingService
from ai_engine.services.vector_store_service import VectorStoreService
from ai_engine.services.llm_service import LLMService

contract_router = APIRouter(
    prefix="/contracts",
    tags=['Contracts']
)

@contract_router.post('/upload')
async def upload(
    db: Annotated[AsyncSession,Depends(get_db)],
    current_user: Annotated[User,Depends(get_current_user)],
    contract_service: Annotated[ContractService,Depends(contract_service)],
    file: Annotated[UploadFile,File()],
    background_task: BackgroundTasks,
    ai_analysis_service: Annotated[AnalysisService,Depends(get_analysis_service)]
) -> ContractResponse:
    contract = await contract_service.upload_contract(
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
async def get_contracts(
    db: Annotated[AsyncSession,Depends(get_db)],
    current_user: Annotated[User,Depends(get_current_user)],
    service: Annotated[ContractService,Depends(contract_service)]
) -> ContractListResponse:
    contracts = await service.get_user_contracts(
        db=db,
        current_user=current_user
    )
    return {
        "contracts": contracts
    }
    
@contract_router.get('/{contract_id}',response_model=ContractResponse)
async def get_contract_by_id(
    db: Annotated[AsyncSession,Depends(get_db)],
    current_user: Annotated[User,Depends(get_current_user)],
    service: Annotated[ContractService,Depends(contract_service)],
    contract_id: int
) -> ContractResponse:
    return await service.get_contract_by_id(
        db=db,
        contract_id=contract_id,
        current_user=current_user   
    )
    
@contract_router.delete('/{id}')
async def delete_contract(
    db: Annotated[AsyncSession,Depends(get_db)],
    current_user: Annotated[User,Depends(get_current_user)],
    service: Annotated[ContractService,Depends(contract_service)],
    id: int
):
    await service.delete_contract(
        db=db,
        contract_id=id,
        current_user=current_user
    )
    return {"status":"success"}


class QuestionRequest(BaseModel):
    question: str

@contract_router.post('/{contract_id}/ask')
async def ask_question_on_contract(
    contract_id: int,
    body: QuestionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(contract_service)]
):
    contract = await service.get_contract_by_id(db=db, contract_id=contract_id, current_user=current_user)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

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