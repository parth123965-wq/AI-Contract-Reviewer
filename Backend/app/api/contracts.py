from fastapi import APIRouter , Depends , UploadFile , File , BackgroundTasks, HTTPException, Response, Query
from typing import Annotated 
from app.database.database import get_db
from app.dependencies.auth import get_current_user
from app.services.contract_service import contract_service , ContractService
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.schemas.contract import ContractResponse , ContractListResponse, QuestionRequest, ClauseRewriteRequest, ClauseRewriteResponse
from app.services.ai_analysis_service import AnalysisService , get_analysis_service
from pydantic import BaseModel
from ai_engine.services.text_extractor import TextExtractor
from ai_engine.services.chunk_service import ChunkService
from ai_engine.services.embedding_service import EmbeddingService
from ai_engine.services.vector_store_service import VectorStoreService
from ai_engine.services.llm_service import LLMService
from fastapi.responses import StreamingResponse
import json
from app.core.rate_limit import RateLimiter
from app.services.report_export_service import export_service

contract_router = APIRouter(
    prefix="/contracts",
    tags=['Contracts']
)

@contract_router.post(
    '/upload',
    response_model=ContractResponse,
    status_code=201,
    summary="Upload Contract PDF File",
    description="Upload a new legal contract PDF document. Automatically queues an asynchronous AI engine analysis task for clause risk evaluation.",
    dependencies=[Depends(RateLimiter(times=10, seconds=60, prefix="contracts_upload"))]
)
async def upload(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    contract_service: Annotated[ContractService, Depends(contract_service)],
    file: Annotated[UploadFile, File()],
    background_task: BackgroundTasks,
    ai_analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)]
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
    
@contract_router.get(
    '',
    response_model=ContractListResponse,
    summary="Get User Contracts List",
    description="Retrieve all contract documents uploaded by the authenticated user, including latest analysis risk scores.",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="contracts_list"))]
)
async def get_contracts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(contract_service)]
) -> ContractListResponse:
    contracts = await service.get_user_contracts(
        db=db,
        current_user=current_user
    )
    return {
        "contracts": contracts
    }
    
@contract_router.get(
    '/{contract_id}',
    response_model=ContractResponse,
    summary="Get Contract Details by ID",
    description="Retrieve full contract details, file metadata, historical analysis runs, and key risk findings by contract ID.",
    dependencies=[Depends(RateLimiter(times=60, seconds=60, prefix="contracts_detail"))]
)
async def get_contract_by_id(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(contract_service)],
    contract_id: int
) -> ContractResponse:
    return await service.get_contract_by_id(
        db=db,
        contract_id=contract_id,
        current_user=current_user   
    )
    
@contract_router.post(
    '/{contract_id}/retry',
    response_model=ContractResponse,
    summary="Retry Failed Contract Analysis",
    description="Re-queue an AI analysis pipeline job for a failed or stuck contract document without having to re-upload the original PDF.",
    dependencies=[Depends(RateLimiter(times=5, seconds=60, prefix="contracts_retry"))]
)
async def retry_analysis(
    contract_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(contract_service)],
    background_task: BackgroundTasks,
    ai_analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)]
) -> ContractResponse:
    contract = await service.retry_contract_analysis(
        db=db,
        contract_id=contract_id,
        current_user=current_user
    )
    background_task.add_task(
        ai_analysis_service.analyze_contract,
        contract.id
    )
    return contract

@contract_router.delete(
    '/{id}',
    summary="Delete Contract Document",
    description="Soft-delete the contract from the user's active list. The record, analysis history, and private Supabase Storage object are retained.",
    dependencies=[Depends(RateLimiter(times=30, seconds=60, prefix="contracts_delete"))]
)
async def delete_contract(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(contract_service)],
    id: int
):
    await service.delete_contract(
        db=db,
        contract_id=id,
        current_user=current_user
    )
    return {"status": "success"}

@contract_router.post(
    '/{contract_id}/ask',
    summary="Ask Question on Contract (RAG SSE Stream)",
    description="Perform RAG (Retrieval-Augmented Generation) query against contract clause vector embeddings. Returns Server-Sent Events (SSE) stream of AI response tokens.",
    dependencies=[Depends(RateLimiter(times=10, seconds=60, prefix="contracts_ask"))]
)
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
        q_embeddings = emb_service.create_embeddings(
            [body.question],
            task_type="RETRIEVAL_QUERY"
        )
        query_emb = q_embeddings[0] if q_embeddings else []
        if query_emb:
            chunks = vector_store.search(
                contract_id=contract_id,
                user_id=current_user.id,
                query_embedding=query_emb,
                top_k=5
            )
    except Exception as exc:
        # Gracefully fall back to direct file extraction if vector store is unavailable
        chunks = []

    # 2. Fallback: Extract directly from contract file if vector store returned empty chunks
    if not chunks:
        if hasattr(contract, "file_path") and contract.file_path:
            try:
                file_content = await service.contract_storage.download(
                    contract.file_path
                )
                extractor = TextExtractor()
                chunker = ChunkService()
                raw_text = extractor.extract_text(file_content)
                if raw_text:
                    chunks = chunker.chunk_text(raw_text)
            except Exception as exc:
                raise HTTPException(
                    status_code=502,
                    detail="Failed to read the contract file from storage.",
                ) from exc

    def event_generator():
        try:
            for text_chunk in llm_service.ask_question_stream(question=body.question, context_chunks=chunks):
                data = json.dumps({"chunk": text_chunk})
                yield f"data: {data}\n\n"
        except Exception as err:
            err_data = json.dumps({"error": str(err)})
            yield f"data: {err_data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@contract_router.post(
    '/{contract_id}/clauses/rewrite',
    response_model=ClauseRewriteResponse,
    summary="Suggest Safe Clause Redline / Revision",
    description="Rewrite a specific high-risk contract clause under a selected negotiation stance (neutral, customer-favorable, vendor-favorable).",
    dependencies=[Depends(RateLimiter(times=15, seconds=60, prefix="contracts_rewrite"))]
)
async def rewrite_clause(
    contract_id: int,
    body: ClauseRewriteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(contract_service)]
) -> ClauseRewriteResponse:
    # Ensure contract exists and belongs to current user
    await service.get_contract_by_id(
        db=db,
        contract_id=contract_id,
        current_user=current_user
    )

    llm = LLMService()
    result = llm.rewrite_clause(
        clause_text=body.clause_text,
        stance=body.stance,
        instructions=body.instructions
    )
    return ClauseRewriteResponse(**result)


@contract_router.get(
    '/{contract_id}/export',
    summary="Export Contract Review Audit Report",
    description="Export a printable executive audit report for the contract in HTML, Markdown, or JSON formats.",
    dependencies=[Depends(RateLimiter(times=20, seconds=60, prefix="contracts_export"))]
)
async def export_contract_report(
    contract_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[ContractService, Depends(contract_service)],
    format: str = Query(default="html", regex="^(html|json|md|markdown)$", description="Export format: html, md, or json")
):
    contract = await service.get_contract_by_id(
        db=db,
        contract_id=contract_id,
        current_user=current_user
    )

    filename_base = contract.original_filename.rsplit(".", 1)[0] if contract.original_filename else f"contract_{contract_id}"

    if format == "json":
        data = export_service.generate_json_report(contract)
        return data

    if format in ("md", "markdown"):
        content = export_service.generate_markdown_report(contract)
        return Response(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}_audit.md"'}
        )

    # Default: Printable modern HTML report
    content = export_service.generate_html_report(contract)
    return Response(
        content=content,
        media_type="text/html",
        headers={"Content-Disposition": f'inline; filename="{filename_base}_audit.html"'}
    )
