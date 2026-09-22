from datetime import datetime, timezone
import asyncio
import base64
import inspect
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse

from backend.knowledge.retriever import KnowledgeRetriever, get_retriever
from backend.agents.artifact_detection import detect_artifact_intent
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
from backend.schemas.chat import ChatMessage
from backend.agents.events import AgentEventStreamer

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


def _process_incoming_documents(documents: list[str], uploads_dir: Path) -> tuple[list[str], str]:
    """
    Process incoming documents:
    - Base64 data URLs (e.g. uploaded PDFs) are decoded and saved to uploads_dir.
    - Plain text is extracted from PDFs (via PyMuPDF) or text files so LLMs can read and summarize them.
    Returns (disk_document_paths, extracted_text_context).
    """
    uploads_dir.mkdir(parents=True, exist_ok=True)
    saved_paths: list[str] = []
    extracted_texts: list[str] = []

    for doc in documents:
        if not doc or not isinstance(doc, str):
            continue
        # Case 1: Base64 data URL
        if doc.startswith("data:") and ";base64," in doc:
            meta, b64_data = doc.split(";base64,", 1)
            ext = ".pdf"
            if "pdf" in meta:
                ext = ".pdf"
            elif "text" in meta or "plain" in meta:
                ext = ".txt"
            elif "csv" in meta:
                ext = ".csv"
            elif "image" in meta:
                ext = ".png"
            file_name = f"upload_{uuid.uuid4().hex[:8]}{ext}"
            file_path = uploads_dir / file_name
            try:
                file_bytes = base64.b64decode(b64_data)
                file_path.write_bytes(file_bytes)
                saved_paths.append(str(file_path.resolve()))
            except Exception as e:
                logger.warning("Failed to decode base64 document: %s", e)
                continue
        # Case 2: Raw base64 PDF
        elif doc.startswith("JVBERi0"):
            file_name = f"upload_{uuid.uuid4().hex[:8]}.pdf"
            file_path = uploads_dir / file_name
            try:
                file_bytes = base64.b64decode(doc)
                file_path.write_bytes(file_bytes)
                saved_paths.append(str(file_path.resolve()))
            except Exception as e:
                logger.warning("Failed to decode base64 PDF: %s", e)
                continue
        # Case 3: File path on disk
        else:
            p = Path(doc)
            if p.exists():
                saved_paths.append(str(p.resolve()))
            else:
                cand = uploads_dir / p.name
                if cand.exists():
                    saved_paths.append(str(cand.resolve()))
                else:
                    saved_paths.append(doc)

    for path_str in saved_paths:
        p = Path(path_str)
        if not p.exists():
            continue
        if p.suffix.lower() == ".pdf":
            try:
                import fitz
                pdf = fitz.open(str(p))
                pages = []
                for i, page in enumerate(pdf):
                    txt = page.get_text().strip()
                    if txt:
                        pages.append(f"[Page {i+1}]\n{txt}")
                pdf.close()
                if pages:
                    extracted_texts.append(f"--- Document Content: {p.name} ---\n" + "\n\n".join(pages))
                else:
                    extracted_texts.append(f"--- Document: {p.name} (scanned/image-only PDF located at {p}) ---")
            except Exception as e:
                logger.warning("Failed to extract text from PDF %s: %s", path_str, e)
                extracted_texts.append(f"--- Document located at {p} ---")
        elif p.suffix.lower() in {".txt", ".csv", ".md", ".json"}:
            try:
                content = p.read_text(errors="replace")
                if content:
                    extracted_texts.append(f"--- Document Content: {p.name} ---\n{content}")
            except Exception:
                pass

    doc_context = "\n\n".join(extracted_texts)
    return saved_paths, doc_context


def _process_incoming_images(images: list[str], uploads_dir: Path) -> tuple[list[str], list[str]]:
    """Save base64 images to uploads_dir and return (base64_images, disk_image_paths)."""
    uploads_dir.mkdir(parents=True, exist_ok=True)
    b64_list: list[str] = []
    disk_paths: list[str] = []
    for img in images:
        if not img or not isinstance(img, str):
            continue
        if img.startswith("data:") and ";base64," in img:
            meta, b64_data = img.split(";base64,", 1)
            ext = ".png"
            if "jpeg" in meta or "jpg" in meta:
                ext = ".jpg"
            elif "webp" in meta:
                ext = ".webp"
            file_name = f"image_{uuid.uuid4().hex[:8]}{ext}"
            file_path = uploads_dir / file_name
            try:
                file_bytes = base64.b64decode(b64_data)
                file_path.write_bytes(file_bytes)
                disk_paths.append(str(file_path.resolve()))
                b64_list.append(b64_data)
            except Exception as e:
                logger.warning("Failed to decode base64 image: %s", e)
        elif Path(img).exists():
            disk_paths.append(str(Path(img).resolve()))
        else:
            b64_list.append(img)
    return b64_list, disk_paths


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
    document_paths = []
    for document_path in payload.document_paths:
        try:
            document_paths.append(str(_resolve_inside(uploads_dir, document_path)))
        except HTTPException:
            document_paths.append(document_path)

    raw_docs = [*payload.documents, *document_paths]
    documents, doc_context = _process_incoming_documents(raw_docs, uploads_dir)
    images, image_paths = _process_incoming_images(payload.images or [], uploads_dir)

    user_request = payload.request
    if doc_context:
        user_request = f"{payload.request}\n\n[Attached Document Context]:\n{doc_context}"

    # Artifact detection is centralized with the agent's existing artifact
    # orchestration.  It honors task_type (report/artifact) and all supported
    # artifact formats rather than routing only PDF-shaped text specially.
    artifact_intent = detect_artifact_intent(payload.request, payload.task_type)
    generate_artifact = getattr(request.app.state.agent, "generate_artifact", None)
    if artifact_intent is not None and callable(generate_artifact):
        result = await generate_artifact(
            user_request,
            task_type=payload.task_type,
            approved_tools=payload.approved_tools,
            generation_mode=payload.generation_mode,
            session_id=payload.session_id,
        )
        return TaskResponse(
            task_id=result.task_id,
            status=result.status,
            selected_model=result.selected_model,
            provider=result.provider,
            fallback_used=result.fallback_used,
            attempted_models=result.attempted_models,
            plan=result.plan,
            response=result.response,
            execution_duration=result.execution_duration,
            artifacts=result.artifacts,
            generated_artifacts=_task_artifact_infos(request.app.state.settings, result.artifacts),
            tool_results=result.tool_results,
            errors=result.errors,
            approval_required=result.approval_required,
            approval_requests=result.approval_requests,
        )

    required_capabilities = payload.required_capabilities
    if documents and payload.task_type is None and not payload.capabilities:
        required_capabilities = {"document_understanding"}
    try:
        run_kwargs: dict[str, Any] = {
            "images": images or image_paths,
            "documents": documents,
            "approved_tools": payload.approved_tools,
        }
        sig = inspect.signature(request.app.state.agent.run)
        if "messages" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            messages = list(payload.messages or [])
            if messages and doc_context:
                for idx in range(len(messages) - 1, -1, -1):
                    m = messages[idx]
                    role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else "")
                    if role == "user":
                        if isinstance(m, ChatMessage):
                            messages[idx] = ChatMessage(role="user", content=user_request, images=m.images)
                        elif isinstance(m, dict):
                            messages[idx] = {**m, "content": user_request}
                        elif hasattr(m, "content"):
                            m.content = user_request
                        break
            run_kwargs["messages"] = messages
        if "session_id" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
            run_kwargs["session_id"] = payload.session_id

        state, model_response = await request.app.state.agent.run(
            user_request,
            required_capabilities,
            payload.modality,
            **run_kwargs,
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



# -- Streaming SSE endpoint ---------------------------------------------------

@router.post("/tasks/stream")
async def stream_task(payload: TaskCreate, request: Request) -> StreamingResponse:
    """
    Execute a task and stream real-time agent activity events via Server-Sent Events.

    Events are JSON-encoded ``data: {...}\\n\\n`` lines with the following types:
    ``task_init``, ``thought``, ``tool_call_start``, ``tool_call_log``,
    ``tool_call_end``, ``content_delta``, ``artifact_ready``, ``task_complete``,
    ``task_error``, ``done``.

    Clients should use ``fetch()`` with ``ReadableStream`` (not ``EventSource``)
    because this route requires a POST body.
    """
    streamer = AgentEventStreamer()
    agent = request.app.state.agent
    settings = request.app.state.settings

    async def _run_task() -> None:
        """Run in background — push events; always emit done on exit."""
        try:
            artifact_intent = detect_artifact_intent(payload.request, payload.task_type)
            generate_artifact = getattr(agent, "generate_artifact", None)

            if artifact_intent is not None and callable(generate_artifact):
                await generate_artifact(
                    payload.request,
                    task_type=payload.task_type,
                    approved_tools=payload.approved_tools,
                    generation_mode=payload.generation_mode,
                    streamer=streamer,
                    session_id=payload.session_id,
                )
            else:
                uploads_dir: Path = settings.data_dir / "uploads"
                document_paths = []
                for dp in payload.document_paths:
                    try:
                        document_paths.append(str(_resolve_inside(uploads_dir, dp)))
                    except HTTPException:
                        document_paths.append(dp)

                raw_docs = [*payload.documents, *document_paths]
                documents, doc_context = _process_incoming_documents(raw_docs, uploads_dir)
                images, image_paths = _process_incoming_images(payload.images or [], uploads_dir)

                user_request = payload.request
                if doc_context:
                    user_request = f"{payload.request}\n\n[Attached Document Context]:\n{doc_context}"

                required_capabilities = payload.required_capabilities
                if documents and payload.task_type is None and not payload.capabilities:
                    required_capabilities = {"document_understanding"}

                run_kwargs: dict[str, Any] = {
                    "images": images or image_paths,
                    "documents": documents,
                    "approved_tools": payload.approved_tools,
                    "streamer": streamer,
                }
                sig = inspect.signature(agent.run)
                if "messages" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    messages = list(payload.messages or [])
                    if messages and doc_context:
                        for idx in range(len(messages) - 1, -1, -1):
                            m = messages[idx]
                            role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else "")
                            if role == "user":
                                if isinstance(m, ChatMessage):
                                    messages[idx] = ChatMessage(role="user", content=user_request, images=m.images)
                                elif isinstance(m, dict):
                                    messages[idx] = {**m, "content": user_request}
                                elif hasattr(m, "content"):
                                    m.content = user_request
                                break
                    run_kwargs["messages"] = messages
                if "session_id" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    run_kwargs["session_id"] = payload.session_id

                state, model_response = await agent.run(
                    user_request,
                    required_capabilities,
                    payload.modality,
                    **run_kwargs,
                )

                streamer.emit_task_complete(
                    task_id=state.task_id,
                    model=state.selected_model,
                    provider=state.provider,
                    tool_count=len(state.tool_results or []),
                )
        except Exception as exc:
            streamer.emit_task_error(str(exc))
        finally:
            await streamer.emit_done()

    # Fire the agent task in the background; SSE drains the queue concurrently
    asyncio.create_task(_run_task())

    return StreamingResponse(
        content=streamer,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
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
    uploads_dir: Path = request.app.state.settings.data_dir / "uploads"
    path = _resolve_inside(uploads_dir, payload.file_path)

    retriever: KnowledgeRetriever = get_retriever()
    result = await asyncio.to_thread(
        retriever.ingest_document,
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
    result = await asyncio.to_thread(
        retriever.ingest_document,
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
