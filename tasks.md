# Backend Architectural Overhaul & Roadmap: Tasks & Milestones

This document tracks the phased refactoring of the `AgenticAI-Workbench` backend.
The goals are:
1. **Retire the initial legacy structured artifact generator** (`ApprovalNoteSpec`, `DocxGenerator`, etc.) and standardize 100% on the **sandbox helper-driven code execution pipeline** (`pptx_helpers`, `docx_helpers`, `pdf_helpers`, `openpyxl`).
2. **Support conversational multi-turn chat interactions with true token streaming** (ChatGPT and Gemini style back-and-forth chat experience).
3. **Streamline backend architecture**, eliminate dead code, fix event loop blocking, and remove concurrency race conditions.

---

## Architecture Blueprint: Two Pillars

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       SOVEREIGN AI WORKBENCH BACKEND                        │
├──────────────────────────────────────┬──────────────────────────────────────┤
│ PILLAR 1: Conversational Chat        │ PILLAR 2: Unified Sandbox Artifacts  │
│ (ChatGPT / Gemini style)             │ (pptx_helpers, docx_helpers, etc.)   │
│                                      │                                      │
│ • Multi-turn conversational context  │ • Auto-detect deliverable intent     │
│ • Real token streaming from Ollama   │ • Inject design skills (markdown)    │
│ • Natural back-and-forth dialogue    │ • LLM writes executable Python code  │
│ • Conversational tool invocation     │ • Execute in network-disabled sandbox│
│   (RAG, Vision, Code when needed)    │ • Harvest files & validate integrity │
│ • No forced deliverable generation   │ • Automated traceback repair loop    │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

---

## Phase 1: Retire Legacy Artifact Generators & Eliminate Dead Code

**Objective:** Clean out the rigid, duplicate Pydantic-based generator system and remove dead code/folders.

- [x] **Task 1.1: Delete legacy artifact generator files**
  - Remove `backend/artifacts/docx_generator.py` (legacy Word generator)
  - Remove `backend/artifacts/pptx_generator.py` (legacy PowerPoint generator)
  - Remove `backend/artifacts/pdf_generator.py` (legacy PDF approval note generator)
  - Remove `backend/artifacts/xlsx_generator.py` (legacy Excel spreadsheet generator)
  - Remove `backend/artifacts/tools.py` (legacy tool adapters: `DocumentCreateTool`, `PresentationCreateTool`, `PdfCreateTool`, `SpreadsheetCreateTool`)
  - Remove `backend/artifacts/deck_workflow.py` (unused dead compatibility stub)

- [ ] **Task 1.2: Delete empty packages & directories**
  - Remove `backend/db/` (empty package containing only `__init__.py`)
  - Remove `prompts/` (empty directory with `.gitkeep`)
  - Remove `templates/` and subdirectories (`approval_notes/`, `docx/`, `pptx/`)

- [ ] **Task 1.3: Strip legacy schemas from `backend/artifacts/contracts.py`**
  - Remove `ApprovalNoteSpec`
  - Remove `SlideLayout`, `ChartSeries`, `SlideSpec`, `PresentationSpec`
  - Remove `ColumnDef`, `SheetSpec`, `SpreadsheetSpec`
  - Retain `Artifact`, `ArtifactValidation`, and `artifact_from_path` (used by validators and storage tracking)

- [ ] **Task 1.4: Update Tool Registry & Configuration files**
  - In `backend/tools/setup.py`: Remove imports and registrations for `DocumentCreateTool`, `PresentationCreateTool`, `PdfCreateTool`, and `SpreadsheetCreateTool`
  - In `configs/agents.yaml`: Remove the 4 retired tools; retain only `rag.search`, `vision.analyze`, `sandbox.execute`, and `artifact.validate`
  - In `configs/tools.yaml`: Synchronize tool list with registered tools

---

## Phase 2: Consolidate on Sandbox Code-Driven Artifact Generation

**Objective:** Make `CodeArtifactWorkflow` with helper primitives the single, authoritative artifact creation engine.

- [ ] **Task 2.1: Refactor `backend/agents/artifact_detection.py`**
  - Remove `select_artifact_generation_mode()` (mode selection is obsolete)
  - Simplify `ArtifactIntent` to carry `artifact_type` (e.g. `pdf`, `pptx`, `docx`, `xlsx`) without needing synthetic tool names like `document.create`
  - Update intent regex patterns to cleanly classify artifact types

- [ ] **Task 2.2: Streamline `backend/agents/industrial_workbench.py`**
  - Remove `_generate_structured_artifact()` and its helper methods (`_extract_tool_arguments`, `_find_tool_result`, `_tool_parameter_schema`)
  - Route all artifact generation calls directly through `_generate_code_artifact()` via `CodeArtifactWorkflow`
  - Fix runtime crash bug on line 415: change `model_response` to `model_response.content` in regex search
  - Ensure skill files (`sandbox/skills/pptx_skill.md`, `sandbox/skills/docx_skill.md`, `sandbox/skills/pdf_skill.md`) and helpers are correctly resolved

- [ ] **Task 2.3: Enhance `backend/artifacts/code_workflow.py`**
  - Ensure robust self-contained script prompts for all 4 deliverable formats (`pptx`, `docx`, `pdf`, `xlsx`)
  - Ensure error feedback and tracebacks are fed back into repair attempts for up to `max_iterations`
  - Update `OfficeArtifactValidator` to include Word tables (`document.tables`) in content checks so valid documents don't fail validation

---

## Phase 3: Conversational Chat Interface & Real Token Streaming (ChatGPT / Gemini Style)

**Objective:** Enable the agent to conduct natural multi-turn conversations with true token streaming while retaining the ability to use tools and build artifacts when requested.

- [ ] **Task 3.1: Conversational Model Contracts**
  - In `backend/models/contracts.py`:
    - Add `ChatMessage` dataclass: `role: Literal["user", "assistant", "system"]`, `content: str`, `images: list[str] = []`
    - Update `ModelRequest` to accept `messages: list[ChatMessage]` alongside the single `prompt` field
  - In `backend/models/providers.py` (`OllamaProvider`):
    - Format full message history `[{"role": msg.role, "content": msg.content}]` for the Ollama chat payload

- [ ] **Task 3.2: True Token-by-Token Streaming from Ollama**
  - In `backend/models/providers.py`:
    - Add `stream_generate(model, request) -> AsyncIterator[str]` using `httpx.AsyncClient.stream("POST", ...)` with `"stream": True`
    - Yield real tokens as they are produced by Ollama instead of waiting for the full response
  - In `backend/api/routes.py`:
    - Connect Ollama's real token generator directly to `AgentEventStreamer.emit_content_delta()`
    - Eliminate the fake post-generation 30-character chunk slicing loop

- [ ] **Task 3.3: Multi-Turn Conversation History in API & Agent State**
  - In `backend/schemas/tasks.py`:
    - Add `messages: list[ChatMessage] = Field(default_factory=list)` to `TaskCreate`
    - Add optional `session_id: str | None = None`
  - In `backend/agents/runtime.py` and `backend/agents/industrial_workbench.py`:
    - Populate graph state messages with full conversation history from `payload.messages`
    - Enable the agent to respond to conversational prompts (clarifications, questions, coding queries, brainstorming) as a direct chat assistant without forcing deliverable workflows

- [ ] **Task 3.4: Dynamic Mode Routing (Chat vs. Artifact Generation)**
  - When the user asks general questions, requests analysis, or asks for code explanations:
    - Route as conversational chat turn with optional RAG/Vision retrieval
  - When the user explicitly requests a deliverable (e.g. "make a 6-slide presentation", "generate a PDF report", "create an Excel model"):
    - Seamlessly trigger `CodeArtifactWorkflow`, run the sandbox, harvest the file, and return the deliverable card within the conversation

---

## Phase 4: Async Concurrency & Backend Reliability

**Objective:** Eliminate event loop freezes, fix singleton race conditions, and secure backend endpoints.

- [ ] **Task 4.1: Offload synchronous blocking operations with `asyncio.to_thread`**
  - `backend/tools/sandbox_tool.py`: Wrap `self.executor.run(request)` in `asyncio.to_thread()`
  - `backend/tools/rag_tool.py`: Wrap `self.retriever.search(...)` in `asyncio.to_thread()`
  - `backend/tools/vision_tool.py`: Wrap `ocr_image()` and `render_pdf_page_to_image()` in `asyncio.to_thread()`
  - `backend/api/routes.py`: Wrap `retriever.ingest_document(...)` in `asyncio.to_thread()`
  - `backend/artifacts/office_renderer.py`: Wrap `subprocess.run(["soffice", ...])` in `asyncio.to_thread()`

- [ ] **Task 4.2: Fix `AgentRuntime` singleton streamer race condition**
  - Remove `self._streamer = streamer` mutation from `AgentRuntime`
  - Pass `streamer` through execution context dictionaries and graph state so concurrent requests never leak events to other sessions

- [ ] **Task 4.3: Harden SSE streamer termination**
  - In `backend/agents/events.py`: Ensure `emit_done()` never silently drops `_DONE_SENTINEL` if the queue is full, preventing hanging HTTP connections

- [ ] **Task 4.4: Autonomous Policy Standardization**
  - In `backend/security/policy.py`: Formally define default policy as autonomous `ALLOW` without breaking interfaces or causing unwanted pipeline blocks
  - Clean up dead approval error branches

- [ ] **Task 4.5: Secure `/api/v1/ingest` against arbitrary file paths**
  - In `backend/api/routes.py`: Enforce path confinement on `payload.file_path` using `_resolve_inside(uploads_dir, ...)` to prevent unauthorized host file access

- [ ] **Task 4.6: Add FastAPI CORS Middleware**
  - In `backend/main.py`: Add `CORSMiddleware` with configurable allowed origins (`["*"]` for development)

---

## Phase 5: Dependencies, Paths & Docker Infrastructure

**Objective:** Clean up dependency definitions, fix relative path bugs, and configure production-ready container builds.

- [ ] **Task 5.1: Clean up `requirements.txt`**
  - Remove duplicate lines for `langchain`, `langchain-ollama`, and `Pillow`
  - Add missing `reportlab>=4.2,<5`

- [ ] **Task 5.2: Fix path resolution in `backend/core/config.py`**
  - Define `data_dir`, `models_config`, and `agents_config` relative to the project root (`Path(__file__).resolve().parent.parent.parent`) rather than CWD

- [ ] **Task 5.3: Add `.dockerignore` file**
  - Exclude `.git`, `.venv`, `node_modules`, `data/*`, `.pytest_cache`, and `tests`

- [ ] **Task 5.4: Fix root `Dockerfile`**
  - Add `COPY sandbox ./sandbox` so helper scripts and skills exist inside the backend container
  - Remove `COPY data ./data` so local test artifacts and vector stores aren't baked into image layers

---

## Phase Progress Summary

| Phase | Description | Status |
| :--- | :--- | :--- |
| **Phase 1** | Retire Legacy Artifact Generators & Dead Code | `Planned` |
| **Phase 2** | Consolidate on Sandbox Code-Driven Artifacts | `Planned` |
| **Phase 3** | Conversational Chat Interface & Real Token Streaming | `Planned` |
| **Phase 4** | Async Concurrency & Backend Reliability | `Planned` |
| **Phase 5** | Dependencies, Paths & Docker Infrastructure | `Planned` |
