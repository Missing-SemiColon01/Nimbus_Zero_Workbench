# Frontend & Backend Step-by-Step Integration Plan

This document defines the comprehensive, phased integration roadmap for the **Sovereign AI Workbench** (`AgenticAI-Workbench`), connecting the React 19 / Vite frontend with the FastAPI sovereign backend.

---

## 1. System Architecture & Integration Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SOVEREIGN AI WORKBENCH ARCHITECTURE                     │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                 VITE + REACT 19 FRONTEND (PORT 8443)                    │
  ├──────────────┬──────────────┬──────────────┬──────────────┬─────────────┤
  │     Chat     │  Knowledge   │  Documents   │  Agents &    │  Status &   │
  │   (/) & SSE  │  (/knowledge)│ (/documents) │  Workflows   │  Security   │
  └───────┬──────┴───────┬──────┴───────┬──────┴───────┬──────┴──────┬──────┘
          │              │              │              │             │
          ▼              ▼              ▼              ▼             ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                       VITE REVERSE PROXY LAYER                          │
  │     /api/v1/* ────────► Forward to http://localhost:8000/api/v1/*       │
  └──────────────────────────────────┬──────────────────────────────────────┘
                                     │
                                     ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                      FASTAPI BACKEND (PORT 8000)                        │
  ├──────────────────────────────────┬──────────────────────────────────────┤
  │ REST & STREAMING ROUTER (/api/v1)│ SOVEREIGN SERVICE ENGINES            │
  │ • POST /tasks/stream (SSE)       │ • IndustrialWorkbenchAgent (LangGraph)│
  │ • POST /tasks                    │ • CodeArtifactWorkflow (Python Sandbox)│
  │ • POST /ingest/upload            │ • KnowledgeRetriever (Chroma / Embed)  │
  │ • POST /knowledge/search         │ • ModelRegistry & ModelRouter (Ollama) │
  │ • GET  /artifacts                │ • AuditLogger (Append-Only JSONL)      │
  │ • GET  /artifacts/{file}/download│ • ToolRegistry (RAG, Vision, Sandbox)  │
  │ • GET  /health, /models, /tools  │ • Path Confinement & Air-Gap Security  │
  └──────────────────────────────────┴──────────────────────────────────────┘
```

---

## 2. API Contracts & Endpoint Mapping Matrix

| Frontend Page / Feature | Frontend Service / Hook | Backend Endpoint | HTTP Method | Payload / Contract |
| :--- | :--- | :--- | :--- | :--- |
| **User Authentication** | `src/services/authService.ts`<br>`src/pages/Login.tsx` | `/api/auth/register`<br>`/api/auth/login`<br>`/api/auth/verify`<br>`/api/auth/me` | `POST`<br>`POST`<br>`POST`<br>`GET` | Register (email, password, name, org), Login (email, password -> JWT), Verify (Bearer token -> valid/claims), Me (user profile) |
| **Chat Assistant** | `src/services/sseClient.ts`<br>`src/hooks/useAgentStream.ts` | `/api/v1/tasks/stream` | `POST` (SSE) | `TaskCreate` (request, messages, session_id, images, document_paths) |
| **Deliverables & Downloads** | `src/pages/Documents.tsx`<br>`src/components/chat/ChatMessage.tsx` | `/api/v1/artifacts`<br>`/api/v1/artifacts/{filename}/download`<br>`/api/v1/artifacts/previews/{preview}` | `GET`<br>`GET`<br>`GET` | Returns `list[ArtifactInfo]`, binary file download, PNG thumbnail |
| **Document Ingestion** | `src/pages/Documents.tsx`<br>`src/pages/KnowledgeBase.tsx`<br>`src/components/chat/ChatComposer.tsx` | `/api/v1/ingest/upload` | `POST` (Multipart) | `file: UploadFile`, `document_id: str`, `chunk_size: int`, `chunk_overlap: int` |
| **Semantic Search** | `src/pages/KnowledgeBase.tsx` | `/api/v1/knowledge/search` | `POST` | `KnowledgeSearchRequest` (query, top_k, score_threshold) |
| **System Status & Telemetry** | `src/pages/SystemStatus.tsx` | `/api/v1/health`<br>`/api/v1/models`<br>`/api/v1/tools` | `GET`<br>`GET`<br>`GET` | Health status, list of local Ollama models, registered tool schemas |
| **Security & Audit Logs** | `src/pages/Security.tsx` | `/api/v1/audit/events` | `GET` | `limit: int` -> Recent audit trail JSON events |
| **Agent Execution** | `src/pages/Agents.tsx` | `/api/v1/tasks/stream` | `POST` (SSE) | Tailored agent prompt execution with real-time log steps |
| **Sandbox & Code Workflows** | `src/pages/Workflows.tsx` | `/api/v1/coding/run`<br>`/api/v1/sandbox/run` | `POST` | `CodingRunRequest` / `SandboxRunRequest` |

---

## 3. Step-by-Step Integration Plan

### Phase 0: Authentication & MongoDB Database Layer (MongoDB, JWT, Bcrypt)

**Goal:** Provide secure, production-grade user authentication and account persistence with MongoDB, JWT sessions, and Bcrypt password encryption.

- [ ] **Step 0.1: MongoDB Connection & Configuration**
  - Read `MONGODB_URI` from `.env.local`.
  - Connect to MongoDB with auto-reconnect and connection pooling.
  - Create `User` schema/model with fields:
    - `email: string` (unique, lowercase, indexed)
    - `password_hash: string` (encrypted via bcrypt with salt rounds >= 10)
    - `name: string`
    - `organization: string`
    - `role: string` (default: "operator", "engineer", "admin")
    - `created_at: Date`
    - `last_login: Date`
- [ ] **Step 0.2: Password Encryption & JWT Token Engine**
  - Implement password hashing with `bcrypt` / `bcryptjs` (salt generation + constant-time compare).
  - Implement JWT token generator and validator:
    - Payload: `{ userId, email, role, organization }`
    - Secret key from `JWT_SECRET` in `.env.local`
    - Expiration: configurable (default: 7d or 24h)
- [ ] **Step 0.3: Auth Endpoints**
  - `POST /api/auth/register`: Validate email format, check existing user, hash password, create document, return JWT + user profile.
  - `POST /api/auth/login`: Validate credentials against bcrypt hash, issue JWT token.
  - `POST /api/auth/verify`: Validate incoming `Bearer <token>` and return decoded user info.
  - `GET /api/auth/me`: Protected route returning authenticated user profile.
- [ ] **Step 0.4: Frontend Login & Session Persistence Integration**
  - Create `frontend/src/services/authService.ts` calling real auth endpoints.
  - Update `frontend/src/pages/Login.tsx`:
    - Replace simulated `setTimeout` and demo logins with real `authService.login()` and `authService.register()`.
    - Store JWT token in `localStorage` / HTTP-only cookie.
    - Handle invalid credentials, duplicate registration, and network errors gracefully.
  - In `frontend/src/services/apiClient.ts`:
    - Automatically inject `Authorization: Bearer <token>` header if a session token is present.
  - In `frontend/src/App.tsx`:
    - On app load, call `/api/auth/verify` to validate token before redirecting to `/login` or `/`.
  - In `frontend/src/components/layout/Header.tsx`:
    - Display authenticated user name and organization. Wire logout to clear JWT and redirect to `/login`.

---

### Phase 1: Network, Configuration & Reverse Proxy

**Goal:** Eliminate CORS issues, resolve URL path discrepancies, and ensure reliable local communication between Vite and FastAPI.

- [ ] **Step 1.1: Configure Vite Dev Server Proxy**
  - In `frontend/vite.config.ts`:
    - Add `server.proxy` mapping `/api/v1` to `http://localhost:8000` (or `process.env.VITE_BACKEND_URL`).
    - Enable `changeOrigin: true` and configure SSE headers buffering disablement (`X-Accel-Buffering: no`).
- [ ] **Step 1.2: Standardize Backend Configuration**
  - In `frontend/src/services/backendConfig.ts`:
    - Standardize `baseUrl`: default to `""` in development (using Vite proxy) or `import.meta.env.VITE_API_BASE_URL` if explicitly set.
    - Synchronize all endpoint routes strictly under `/api/v1/*`.
  - In `frontend/.env.local.example` and `frontend/.env.local`:
    - Set `VITE_API_BASE_URL=` (empty string for proxy) or `http://localhost:8000`.
- [ ] **Step 1.3: Update API Client Helper**
  - In `frontend/src/services/apiClient.ts`:
    - Ensure headers, query params, error handling, and JSON serialization are robust against non-200 responses.
    - Add support for multipart `FormData` uploads.

---

### Phase 2: Multi-Turn Conversational Chat & SSE Streaming

**Goal:** Full integration of multi-turn chat memory, real token streaming, and dynamic deliverable cards into the chat UI.

- [ ] **Step 2.1: Enhance SSE Client Contracts**
  - In `frontend/src/services/sseClient.ts`:
    - Update `TaskPayload` interface to support:
      ```typescript
      export interface TaskPayload {
        request: string;
        task_type?: string;
        modality?: string;
        images?: string[];
        documents?: string[];
        document_paths?: string[];
        approved_tools?: string[];
        generation_mode?: string;
        messages?: Array<{ role: 'user' | 'assistant' | 'system'; content: string }>;
        session_id?: string;
      }
      ```
    - Ensure SSE reader handles connection drops and network anomalies without crashing the React UI.
- [ ] **Step 2.2: Pass Full Conversation History in `aiService.ts`**
  - In `frontend/src/services/aiService.ts`:
    - When calling `streamTask`, map previous conversation messages to `payload.messages`:
      ```typescript
      const formattedMessages = messages.map(m => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      }));
      ```
    - Pass active `session_id` to enable persistent session tracking in the backend.
- [ ] **Step 2.3: Chat File Uploads & Multi-Modal Routing**
  - In `frontend/src/components/chat/ChatComposer.tsx` and `frontend/src/pages/Chat.tsx`:
    - For attached images: encode to base64 and pass in `payload.images`.
    - For attached documents (PDF/CSV/DOCX): automatically upload to `/api/v1/ingest/upload`, receive `document_path`, and append to `payload.document_paths`.
- [ ] **Step 2.4: Real Artifact Download & Preview Links**
  - In `frontend/src/components/chat/ChatMessage.tsx` and `frontend/src/types/index.ts`:
    - Ensure `GeneratedFile` download button uses `backendUrl(file.download_url)`.
    - Render thumbnail previews when `preview_url` is provided.

---

### Phase 3: Deliverables & Generated Artifacts (`/documents`)

**Goal:** Transform the Documents page from dummy mock items into a live deliverables browser for documents created by the agent.

- [ ] **Step 3.1: Implement Artifact Service**
  - Create `frontend/src/services/artifactService.ts`:
    - `fetchArtifacts(): Promise<ArtifactInfo[]>` -> calls `GET /api/v1/artifacts`.
    - `getDownloadUrl(filename: string): string` -> resolves `/api/v1/artifacts/${filename}/download`.
    - `getPreviewUrl(previewName: string): string` -> resolves `/api/v1/artifacts/previews/${previewName}`.
- [ ] **Step 3.2: Wire `Documents.tsx` to Live Artifacts**
  - In `frontend/src/pages/Documents.tsx`:
    - Replace `DEMO_KNOWLEDGE_DOCS` with state fetched from `fetchArtifacts()`.
    - Add loading skeleton and empty state ("No deliverables generated yet. Ask the agent in Chat to create a presentation, report, or spreadsheet").
    - Connect download buttons to trigger native file downloads.
    - Wire "Preview" modal to render high-resolution preview images from `preview_url`.
- [ ] **Step 3.3: Direct Ingestion from Documents View**
  - In `frontend/src/pages/Documents.tsx`:
    - Wire drag-and-drop file upload to `POST /api/v1/ingest/upload`.
    - Display toast notification upon successful ingestion and vector indexing.

---

### Phase 4: Knowledge Base & Semantic Search (`/knowledge`)

**Goal:** Connect enterprise document ingestion and semantic vector retrieval to the backend.

- [ ] **Step 4.1: Implement Knowledge Service**
  - Create `frontend/src/services/knowledgeService.ts`:
    - `uploadDocument(file: File, documentId?: string): Promise<IngestResponse>` -> `POST /api/v1/ingest/upload`.
    - `searchKnowledge(query: string, topK?: number): Promise<KnowledgeSearchResponse>` -> `POST /api/v1/knowledge/search`.
- [ ] **Step 4.2: Wire `KnowledgeBase.tsx` to Real Ingestion & Search**
  - In `frontend/src/pages/KnowledgeBase.tsx`:
    - Wire file input to `uploadDocument()` with progress feedback (Extracting text, OCR fallback, Chunking, Indexing).
    - Connect search bar to `searchKnowledge()`: display matched chunks, similarity scores, source file, and page citations.
    - Provide a toggle between "Catalog View" (all documents) and "Semantic Search View" (vector search results).

---

### Phase 5: System Status, Model Registry & Tool Telemetry (`/system`)

**Goal:** Display genuine on-premise infrastructure health, active Ollama LLMs, and registered sovereign tools.

- [ ] **Step 5.1: Implement System Service**
  - Create `frontend/src/services/systemService.ts`:
    - `getHealth(): Promise<{ status: string; sovereign_mode: boolean }>` -> `GET /api/v1/health`.
    - `getModels(): Promise<ModelInfo[]>` -> `GET /api/v1/models`.
    - `getTools(): Promise<ToolInfo[]>` -> `GET /api/v1/tools`.
- [ ] **Step 5.2: Wire `SystemStatus.tsx`**
  - In `frontend/src/pages/SystemStatus.tsx`:
    - Replace random mock generators with live data from `getHealth()`, `getModels()`, and `getTools()`.
    - Display cards for active Ollama models (e.g. `qwen2.5:7b`, `llama3.2-vision`), priority order, and enabled modalities.
    - Display registered sovereign tools: `sandbox.execute`, `rag.search`, `vision.analyze`, `artifact.validate`.
    - Add a "Refresh Status" button that polls backend endpoints.

---

### Phase 6: Live Audit Trail & Security Assurance (`/security`)

**Goal:** Provide full compliance visibility by streaming real-time immutable audit logs from the backend.

- [ ] **Step 6.1: Implement Audit Service**
  - Create `frontend/src/services/auditService.ts`:
    - `getAuditEvents(limit?: number): Promise<AuditEvent[]>` -> `GET /api/v1/audit/events?limit=100`.
- [ ] **Step 6.2: Wire `Security.tsx` with Live Event Viewer**
  - In `frontend/src/pages/Security.tsx`:
    - Add an "Audit Trail" tab displaying recent audit events (timestamp, event type, model used, tool invoked, execution status).
    - Add an event detail modal showing parameters and execution results.
    - Highlight on-premise security guarantees: network-isolated sandbox, zero cloud dependencies, local storage encryption.

---

### Phase 7: Real Agent Execution & Workflows (`/agents` & `/workflows`)

**Goal:** Turn preset agent cards into real agent task dispatchers and connect workflow canvases to backend execution.

- [ ] **Step 7.1: Wire Preset Agents to Real Tasks**
  - In `frontend/src/pages/Agents.tsx`:
    - Connect "Run Agent" modal to execute tasks via `streamTask` with domain-specific system prompts.
    - Stream real reasoning and tool call logs directly in the modal activity tracker.
    - Provide a "Continue in Chat" button that creates a chat session populated with the agent's task run.
- [ ] **Step 7.2: Wire Workflows to Coding / Sandbox Workflows**
  - In `frontend/src/pages/Workflows.tsx`:
    - Connect workflow execution triggers to `POST /api/v1/coding/run` and `POST /api/v1/sandbox/run`.

---

### Phase 8: Unified Tooling, Startup Scripts & End-to-End Verification

**Goal:** Single-command local startup across Windows and Linux, and automated end-to-end integration smoke tests.

- [ ] **Step 8.1: Create Linux/macOS Startup Script (`start-local.sh`)**
  - Provide a single bash script that:
    1. Verifies/creates data directories (`data/uploads`, `data/artifacts`, `data/tmp`).
    2. Starts the FastAPI backend with uvicorn on port 8000.
    3. Starts the Vite frontend on port 8443.
    4. Handles graceful termination on `SIGINT` / `Ctrl+C`.
- [ ] **Step 8.2: Update Windows Startup Script (`start-local.ps1`)**
  - Add an optional flag or concurrent job to launch frontend dev server alongside backend API.
- [ ] **Step 8.3: Create Integration Smoke Test Script**
  - Create `scripts/integration_smoke_test.py`:
    - Tests FastAPI health, model listing, tool listing.
    - Tests PDF upload and knowledge search.
    - Tests SSE task stream execution and verifies `task_init`, `content_delta`, and `done` events.
    - Tests artifact generation, listing, and download routes.

---

## 4. Verification & Testing Matrix

| Test ID | Area | Verification Method | Expected Outcome |
| :--- | :--- | :--- | :--- |
| **V1** | Reverse Proxy | `curl -i http://localhost:8443/api/v1/health` | HTTP 200 `{"status":"ok","sovereign_mode":true}` |
| **V2** | Chat SSE Stream | Send message in UI, inspect browser DevTools Network tab | `POST /api/v1/tasks/stream` returns SSE event stream with live tokens |
| **V3** | Multi-Turn Memory | Ask agent a question, then follow up with "Summarize what you just said" | Agent references the earlier message using `payload.messages` |
| **V4** | Deliverables Download | Ask agent "Create a 4-slide PPTX about safety", click download card | `.pptx` file downloads and opens cleanly |
| **V5** | Document Ingestion | Upload PDF via Knowledge Base / Documents page | File saved to `data/uploads`, indexed into vector store |
| **V6** | Semantic Search | Enter keyword query in Knowledge Base search | Relevant chunk excerpts with source page numbers returned |
| **V7** | System Status | Open `/system` in UI | Displays real Ollama models and tool count from backend |
| **V8** | Audit Trail | Open `/security` in UI after running tasks | Live audit entries appear with accurate timestamps and tool logs |

---

## 5. Rollout Timeline & Milestones

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          INTEGRATION TIMELINE                               │
├───────────────┬─────────────────────────────────────────────────────────────┤
│ Milestone 1   │ Phase 1: Vite Proxy & Network Configuration                 │
│ Milestone 2   │ Phase 2: Chat Multi-Turn & SSE Token Streaming              │
│ Milestone 3   │ Phase 3 & 4: Documents & Knowledge Base Ingestion           │
│ Milestone 4   │ Phase 5 & 6: System Status & Security Audit Trail           │
│ Milestone 5   │ Phase 7 & 8: Agents, Workflows & Unified Startup Scripts    │
└───────────────┴─────────────────────────────────────────────────────────────┘
```
