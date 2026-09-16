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
from backend.sandbox.coding_workflow import CodingWorkflow
from backend.schemas.artifacts import ArtifactInfo
from backend.schemas.coding import CodingRunRequest, CodingRunResponse
from backend.schemas.knowledge import (
    IngestRequest,
    IngestResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    ToolInfo,
)
from backend.schemas.sandbox import SandboxRunRequest, SandboxRunResponse
from backend.schemas.tasks import TaskCreate, TaskResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_inside(base_dir: Path, requested_path: str) -> Path:
    """Resolve a caller-provided path while ensuring it stays inside base_dir."""
    resolved_base = base_dir.resolve()
    candidate = Path(requested_path)
    if not candidate.is_absolute():
        candidate = resolved_base / candidate
    resolved_path = candidate.resolve()
    if not resolved_path.is_file() or not resolved_path.is_relative_to(resolved_base):
        raise HTTPException(status_code=404, detail=f"Document not found: {requested_path}")
    return resolved_path


def _safe_upload_target(uploads_dir: Path, filename: str) -> Path:
    """Return a safe upload destination for a user-supplied filename."""
    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Uploaded file must have a valid filename.")
    return uploads_dir / safe_name


def _sandbox_response(output: dict[str, Any], *, success: bool, error: str | None = None) -> SandboxRunResponse:
    return SandboxRunResponse(
        exit_code=int(output.get("exit_code", -1)),
        stdout=str(output.get("stdout", "")),
        stderr=str(output.get("stderr", error or "")),
        test_passed=bool(output.get("test_passed", False)),
        timed_out=bool(output.get("timed_out", False)),
        success=success,
        summary=str(output.get("summary", error or "")),
    )


def _artifact_info(file_path: Path, *, artifacts_dir: Path, previews_dir: Path) -> ArtifactInfo:
    """Build API download metadata for a generated artifact path."""
    ext = file_path.suffix.lstrip(".").lower()
    stat = file_path.stat()
    preview_url = None
    preview_candidate = previews_dir / f"{file_path.stem}-page-1.png"
    if preview_candidate.exists():
        preview_url = f"/api/v1/artifacts/previews/{preview_candidate.name}"

    return ArtifactInfo(
        filename=file_path.name,
        file_type=ext,
        size_bytes=stat.st_size,
        download_url=f"/api/v1/artifacts/{file_path.name}/download",
        preview_url=preview_url,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
    )


def _task_artifact_infos(settings: Any, artifact_paths: list[str]) -> list[ArtifactInfo]:
    """Convert task artifact paths to downloadable metadata, ignoring stale paths."""
    artifacts_dir: Path = settings.data_dir / "artifacts"
    previews_dir: Path = settings.data_dir / "tmp" / "artifact-previews"
    items: list[ArtifactInfo] = []
    for artifact_path in artifact_paths:
        try:
            file_path = _safe_resolve(artifacts_dir, Path(artifact_path).name)
        except HTTPException:
            continue
        items.append(_artifact_info(file_path, artifacts_dir=artifacts_dir, previews_dir=previews_dir))
    return items


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


@router.get("/audit/events")
async def audit_events(request: Request, limit: int = 100):
    """Return recent local audit events for demo and verification."""
    bounded_limit = max(1, min(limit, 500))
    return request.app.state.audit.tail(bounded_limit)


# -- Tasks API -----------------------------------------------------------------

@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(payload: TaskCreate, request: Request):
    uploads_dir: Path = request.app.state.settings.data_dir / "uploads"
    document_paths = [
        str(_resolve_inside(uploads_dir, document_path))
        for document_path in payload.document_paths
    ]

    documents = [*payload.documents, *document_paths]
    required_capabilities = payload.required_capabilities
    if documents and payload.task_type is None and not payload.capabilities:
        required_capabilities = {"document_understanding"}
    try:
        state, model_response = await request.app.state.agent.run(
            payload.request,
            required_capabilities,
            payload.modality,
            images=payload.images,
            documents=documents,
            approved_tools=payload.approved_tools,
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
        artifacts=state.artifacts,
        generated_artifacts=_task_artifact_infos(request.app.state.settings, state.artifacts),
        tool_results=state.tool_results,
        errors=state.errors,
        approval_required=state.approval_required,
        approval_requests=state.approval_requests,
    )



# -- Knowledge & Ingest API (Day 2 — Task 2.5) ----------------------------------

@router.post("/sandbox/run", response_model=SandboxRunResponse)
async def run_sandbox(payload: SandboxRunRequest, request: Request):
    """Directly execute Python code through the registered sandbox tool."""
    try:
        tool = request.app.state.tools.get("sandbox.execute")
    except KeyError as error:
        raise HTTPException(status_code=503, detail="Sandbox tool is not registered.") from error

    result = await tool.execute(
        {
            "code": payload.code,
            "test_code": payload.test_code,
            "language": payload.language,
            "timeout_seconds": payload.timeout_seconds,
        },
        context={},
    )
    response = _sandbox_response(result.output or {}, success=result.success, error=result.error)
    request.app.state.audit.record(
        "sandbox.run",
        {
            "language": payload.language,
            "timeout_seconds": payload.timeout_seconds,
            "network_disabled": True,
            "success": response.success,
            "exit_code": response.exit_code,
            "test_passed": response.test_passed,
            "timed_out": response.timed_out,
            "error": result.error,
        },
    )
    return response


@router.post("/coding/run", response_model=CodingRunResponse)
async def run_coding_workflow(payload: CodingRunRequest, request: Request):
    """Generate code, verify it in the sandbox, and retry with failure feedback."""
    workflow = CodingWorkflow(
        router=request.app.state.runtime.router,
        providers=request.app.state.runtime.providers,
        tools=request.app.state.tools,
        max_retries=request.app.state.settings.sandbox_max_retries,
        timeout_seconds=request.app.state.settings.sandbox_timeout_seconds,
    )
    result = await workflow.run(
        payload.requirement,
        payload.test_code,
        max_retries=payload.max_retries,
        timeout_seconds=payload.timeout_seconds,
    )
    request.app.state.audit.record(
        "coding.run",
        {
            "status": result.status,
            "selected_model": result.selected_model,
            "provider": result.provider,
            "attempted_models": result.attempted_models,
            "attempt_count": len(result.attempts),
            "test_passed": any(attempt.test_passed for attempt in result.attempts),
            "errors": result.errors,
        },
        task_id=result.task_id,
    )
    return result


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

    return IngestResponse(**result.to_dict(), document_path=str(path.resolve()))


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
    target_path = _safe_upload_target(uploads_dir, file.filename)

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

    return IngestResponse(**result.to_dict(), document_path=str(target_path.resolve()))


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
            items.append(_artifact_info(file_path, artifacts_dir=artifacts_dir, previews_dir=previews_dir))

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
