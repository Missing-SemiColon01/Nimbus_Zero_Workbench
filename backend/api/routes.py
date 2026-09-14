import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from backend.knowledge.retriever import KnowledgeRetriever, get_retriever
from backend.models.providers import ProviderError, ProviderRequestError
from backend.models.router import NoCompatibleModelError
from backend.schemas.knowledge import (
    IngestRequest,
    IngestResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ToolInfo,
)
from backend.schemas.tasks import TaskCreate, TaskResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# -- System & Health -----------------------------------------------------------

@router.get("/health")
async def health(request: Request):
    return {"status": "ok", "sovereign_mode": request.app.state.settings.sovereign_mode}


@router.get("/models")
async def models(request: Request):
    return [
        {
            "id": item.id,
            "capabilities": sorted(item.capabilities),
            "modalities": sorted(item.modalities),
            "priority": item.priority,
            "enabled": item.enabled,
        }
        for item in request.app.state.registry.models
    ]


@router.get("/tools", response_model=list[ToolInfo])
async def list_tools(request: Request):
    """List all registered sovereign tools and their execution parameters."""
    tools_registry = getattr(request.app.state, "tools", None)
    if not tools_registry:
        return []

    return [
        ToolInfo(
            name=tool.name,
            description=getattr(tool, "description", ""),
            parameters=getattr(tool, "parameters", {}),
        )
        for tool in (tools_registry.get(name) for name in tools_registry.names())
    ]


# -- Tasks API -----------------------------------------------------------------

@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(payload: TaskCreate, request: Request):
    try:
        state, model_response = await request.app.state.runtime.run(
            payload.request, payload.required_capabilities, payload.modality
        )
    except NoCompatibleModelError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ProviderRequestError as error:
        raise HTTPException(status_code=422, detail="Model generation request is invalid") from error
    except ProviderError as error:
        raise HTTPException(status_code=502, detail="Model generation failed") from error

    if state.status == "failed":
        raise HTTPException(status_code=502, detail="Model generation failed")

    return TaskResponse(
        task_id=state.task_id,
        status=state.status,
        selected_model=state.selected_model,
        provider=state.provider,
        fallback_used=state.fallback_used,
        attempted_models=state.attempted_models,
        plan=state.plan,
        response=state.final_response or model_response.content,
        execution_duration=state.execution_duration,
    )



# -- Knowledge & Ingest API (Day 2 — Task 2.5) ----------------------------------

@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_file_path(payload: IngestRequest, request: Request):
    """
    Ingest a PDF document from an accessible filesystem path.
    Runs parsing, OCR fallback, token chunking, and local vector indexing.
    """
    path = Path(payload.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {payload.file_path}")

    retriever: KnowledgeRetriever = get_retriever()
    result = retriever.ingest_document(
        source=path,
        document_id=payload.document_id,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
    )

    if result.status == "failed":
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {result.error}")

    return IngestResponse(**result.to_dict())


@router.post("/ingest/upload", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_upload(
    request: Request,
    file: UploadFile = File(...),
    document_id: str | None = Form(None),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
):
    """
    Upload and ingest a PDF file directly via multipart form data.
    Saves the file to the uploads directory and indexes its content.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for document ingestion.")

    uploads_dir: Path = request.app.state.settings.data_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    target_path = uploads_dir / file.filename

    # Save uploaded bytes to disk
    try:
        with target_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {exc}") from exc

    retriever: KnowledgeRetriever = get_retriever()
    result = retriever.ingest_document(
        source=target_path,
        document_id=document_id or target_path.stem,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if result.status == "failed":
        raise HTTPException(status_code=400, detail=f"Ingestion failed: {result.error}")

    return IngestResponse(**result.to_dict())


@router.post("/knowledge/search", response_model=KnowledgeSearchResponse)
async def search_knowledge(payload: KnowledgeSearchRequest, request: Request):
    """
    Semantic search across ingested sovereign documents.
    Returns matching text chunks with source filenames and exact page numbers.
    """
    retriever: KnowledgeRetriever = get_retriever()
    hits = retriever.search(
        query=payload.query,
        top_k=payload.top_k,
        score_threshold=payload.score_threshold,
        filter_doc_id=payload.document_id,
    )

    return KnowledgeSearchResponse(
        query=payload.query,
        total_results=len(hits),
        results=hits,
    )
