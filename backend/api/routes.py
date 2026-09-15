from datetime import datetime, timezone
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from backend.knowledge.retriever import KnowledgeRetriever, get_retriever
from backend.models.providers import ProviderError, ProviderRequestError
from backend.models.router import NoCompatibleModelError
from backend.schemas.artifacts import ArtifactInfo
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
            payload.request,
            payload.required_capabilities,
            payload.modality,
            images=payload.images,
            documents=payload.documents,
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


# -- Artifacts API (Day 3) ----------------------------------------------------

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".png": "image/png",
}


def _safe_resolve(base_dir: Path, requested_filename: str) -> Path:
    """Resolve requested_filename inside base_dir and protect against path traversal."""
    resolved_base = base_dir.resolve()
    target_path = (resolved_base / requested_filename).resolve()
    if not target_path.is_file() or not target_path.is_relative_to(resolved_base):
        raise HTTPException(status_code=404, detail=f"File not found: {requested_filename}")
    return target_path


@router.get("/artifacts", response_model=list[ArtifactInfo])
async def list_artifacts(request: Request):
    """List all locally generated deliverables stored in data/artifacts."""
    settings = request.app.state.settings
    artifacts_dir: Path = settings.data_dir / "artifacts"
    previews_dir: Path = settings.data_dir / "tmp" / "artifact-previews"

    if not artifacts_dir.exists():
        return []

    items: list[ArtifactInfo] = []
    for file_path in artifacts_dir.iterdir():
        if file_path.is_file():
            ext = file_path.suffix.lstrip(".").lower()
            stat = file_path.stat()
            preview_url = None
            if previews_dir.exists():
                preview_candidate = previews_dir / f"{file_path.stem}-page-1.png"
                if preview_candidate.exists():
                    preview_url = f"/api/v1/artifacts/previews/{preview_candidate.name}"

            items.append(
                ArtifactInfo(
                    filename=file_path.name,
                    file_type=ext,
                    size_bytes=stat.st_size,
                    download_url=f"/api/v1/artifacts/{file_path.name}/download",
                    preview_url=preview_url,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                )
            )

    items.sort(key=lambda item: item.modified_at, reverse=True)
    return items


@router.get("/artifacts/{filename}/download")
async def download_artifact(filename: str, request: Request):
    """Download a locally generated artifact with path traversal protection."""
    settings = request.app.state.settings
    artifacts_dir: Path = settings.data_dir / "artifacts"
    target_path = _safe_resolve(artifacts_dir, filename)

    media_type = MIME_TYPES.get(target_path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        path=str(target_path),
        filename=target_path.name,
        media_type=media_type,
    )


@router.get("/artifacts/previews/{preview_name}")
async def get_artifact_preview(preview_name: str, request: Request):
    """Serve a locally generated PNG preview thumbnail for an artifact."""
    settings = request.app.state.settings
    previews_dir: Path = settings.data_dir / "tmp" / "artifact-previews"
    target_path = _safe_resolve(previews_dir, preview_name)

    return FileResponse(
        path=str(target_path),
        filename=target_path.name,
        media_type="image/png",
    )
