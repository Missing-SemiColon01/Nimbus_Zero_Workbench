# Phased Remediation Tasks (`bus_task.md`)
**Direct Mapping to:** [`ARCHITECTURAL_AUDIT_AND_FIXES.md`](file:///home/sanmesh/AgenticAI-Workbench/ARCHITECTURAL_AUDIT_AND_FIXES.md)  
**Scope:** Architectural Audit Issues (Flaws 1.1 through 7.1)  
**Phasing:** 3 Structured Phases  

---

```
┌────────────────────────────────────────────────────────────────────────┐
│  Phase 1: Runtime Engine, Agent Loop & Routing Fixes                   │
│  [Flaws 1.1, 1.2, 1.3, 1.4, 2.1, 2.2]                                  │
│  • Eliminate triple Ollama generation in streaming                     │
│  • Fix streaming desynchronization & suppress raw tool JSON leakage    │
│  • Markdown fence support for tool parsing                             │
│  • Graceful answer synthesis on max tool rounds limit                  │
│  • Resolve [reasoning, vision] routing deadlock & orchestrator pattern │
│  • Refactor linear LangGraph pipeline into cyclic tool graph           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Phase 2: Prompts, Memory, Multimodal & RAG Stability                  │
│  [Flaws 1.5, 3.1, 4.1, 4.2, 4.3, 5.1]                                  │
│  • Harden system prompt injection across chat history                  │
│  • Full document & image attachment extraction pipeline                │
│  • Base64 data URI sanitization for Ollama vision API                  │
│  • Persist intermediate tool calls/results into conversation memory    │
│  • Migrate embedder to quantized INT8 ONNX (optimum runtime)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  Phase 3: Session Persistence & Artifact Workflow Unification          │
│  [Flaws 6.1, 7.1]                                                      │
│  • Sync chat sessions & messages to MongoDB (replace localStorage)     │
│  • Unify fragmented artifact generation into standard tool registry    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Runtime Engine, Agent Loop & Routing Fixes
*Addresses Section 1 (Flaws 1.1–1.4) and Section 2 (Flaws 2.1–2.2) of the Architectural Audit.*

- [x] **Task 1.1 [Audit Flaw 1.2]: Fix Streaming Desync & Eliminate 3x Ollama Generation**
  - **Target File:** `backend/agents/runtime.py` (`_generate_response`)
  - **Audit Finding:** Streaming currently invokes `stream_generate()`, then `generate()`, and then `_generate_with_tools()`, causing 3 separate LLM calls per turn. Raw tool JSON leaks to the chat UI, while the post-tool synthesis is never streamed.
  - **Fix:** Unify streaming inside the generation loop. Buffer model output to verify whether it is conversational text or a tool call. If a tool call is detected, emit `tool_call_start` without streaming the JSON to chat. After tool execution, stream the final synthesized response to `streamer.emit_content_delta()`.
  - **Acceptance Criteria:** Exactly one LLM inference pass occurs on conversational turns; tool turns execute tools first and stream the final answer cleanly to the UI.

- [x] **Task 1.2 [Audit Flaw 1.3]: Markdown Code-Fence Parsing for Tool Calls**
  - **Target File:** `backend/agents/runtime.py` (`_detect_tool_calls`)
  - **Audit Finding:** `json.loads()` crashes with `JSONDecodeError` when models wrap tool calls in markdown code blocks (` ```json ... ``` `), terminating without tool execution.
  - **Fix:** Add regex fence stripping (`r"```(?:json)?\s*([\s\S]*?)\s*```"`) prior to `json.loads` parsing.
  - **Acceptance Criteria:** Tool calls wrapped in markdown code blocks are parsed and executed successfully.

- [x] **Task 1.3 [Audit Flaw 1.4]: Graceful Answer Synthesis on Max Tool Rounds Limit**
  - **Target File:** `backend/agents/runtime.py` (`_generate_with_tools`)
  - **Audit Finding:** Reaching `max_tool_rounds` (default: 3) raises an unhandled `ProviderError("Maximum tool rounds exceeded")`, causing a `502` task failure.
  - **Fix:** Replace the exception with a forced final synthesis pass: strip `tools` from `ModelRequest`, prompt the model to formulate a final response using evidence collected so far, and return the answer.
  - **Acceptance Criteria:** Hitting tool limits produces a best-effort response with an advisory note instead of throwing a 502 error.

- [x] **Task 1.4 [Audit Flaw 2.1 & 2.2]: Resolve `[reasoning, vision]` Routing Deadlock & Formalize Orchestrator Pattern**
  - **Target Files:** `configs/models.yaml`, `backend/agents/runtime.py`, `backend/api/routes.py`
  - **Audit Finding:** The router uses strict subset matching (`capabilities <= model.capabilities`). Image attachments mutate requirements to `{"reasoning", "vision"}` and `modality="image"`. Since `qwen3:14b` is text-only and `qwen2.5-vl:7b` only listed `[vision, document_understanding]`, routing crashes with `NoCompatibleModelError`.
  - **Fix:**
    1. Add `reasoning` capability to `qwen2.5-vl:7b` in `configs/models.yaml`.
    2. In `runtime.py`, formalize the Orchestrator-Worker pattern: route user chat turns to the Reasoning Agent (`qwen3:14b`) and let it call `vision.analyze` as a tool (delegating to `qwen2.5-vl:7b`), rather than mutating the top-level orchestrator requirements to an impossible filter.
  - **Acceptance Criteria:** Image and document queries route successfully without `NoCompatibleModelError`.

- [x] **Task 1.5 [Audit Flaw 1.1]: Refactor Linear LangGraph Pipeline into a Cyclic Tool Graph**
  - **Target File:** `backend/agents/runtime.py` (`AgentRuntime.__init__`)
  - **Audit Finding:** The LangGraph `StateGraph` is currently a 1-pass linear pipe (`START -> validate -> generate -> output -> END`), bypassing LangGraph's cyclic state management and step limits.
  - **Fix:** Rebuild the graph with cyclic routing: `validate_input -> model_node -> conditional_edge (has_tool_calls? -> tools_node -> model_node | no -> validate_output -> END)`.
  - **Acceptance Criteria:** Tool cycles execute across LangGraph edges, respecting step limits and checkpointing.

---

## Phase 2: Prompts, Memory, Multimodal & RAG Stability
*Addresses Section 1 (Flaw 1.5), Section 3 (Flaw 3.1), Section 4 (Flaws 4.1–4.3), and Section 5 (Flaw 5.1) of the Architectural Audit.*

- [x] **Task 2.1 [Audit Flaws 3.1, 4.1, 4.2, 4.3]: Harden System Prompt & Multimodal Ingestion Pipeline**
  - **Target Files:** `backend/models/contracts.py`, `backend/models/providers.py`, `backend/api/routes.py`, `frontend/src/components/chat/ChatComposer.tsx`
  - **Audit Finding:** 
    - System prompts were discarded in `normalize_messages()` whenever chat history existed.
    - `ChatComposer.tsx` only populated `dataUrl` for images, leaving PDFs/DOCX `undefined` (`documents: []`).
    - Ollama `/api/chat` was sent an unsupported `"documents"` field which it silently dropped.
    - Data URI prefixes (`data:image/...;base64,`) caused Ollama's vision decoder to fail.
  - **Fix:**
    1. Ensure `ChatMessage(role="system", content=system_prompt)` is prepended at the root of `request.messages` and preserved in `normalize_messages()`.
    2. Populate `dataUrl` and `url` for all attachment types in `ChatComposer.tsx`.
    3. Decode base64 document attachments in `routes.py`, save them to `data/uploads/`, extract plain text via PyMuPDF (`fitz`), and inject the extracted text into the prompt context.
    4. Strip data URI schemes (`data:image/...;base64,`) in `OllamaProvider._build_payload()` before sending to Ollama.
  - **Acceptance Criteria:** Model correctly identifies as "Industrial Workbench Agent"; uploaded PDFs and images are extracted and summarized without asking for manual file paths.

- [x] **Task 2.2 [Audit Flaw 1.5]: Retain Tool Invocations and Results in Conversational Memory**
  - **Target File:** `backend/agents/runtime.py`
  - **Audit Finding:** Intermediate tool calls and tool outputs are excluded from `state["messages"]`. On subsequent turns, the agent has no memory of what tools it called or what evidence it found.
  - **Fix:** Append structured assistant `tool_calls` and corresponding `tool_results` into `state["messages"]` so subsequent turns retain evidence in context.
  - **Acceptance Criteria:** Asking follow-up questions about previously analyzed tools, images, or documents succeeds without re-executing tools.

- [x] **Task 2.3 [Audit Flaw 5.1]: Migrate Knowledge Embedder to Quantized INT8 ONNX**
  - **Target Files:** `backend/knowledge/embedder.py`, `backend/main.py`
  - **Audit Finding:** `embedder.py` loads PyTorch eager models via `AutoModel.from_pretrained()`, causing high RAM usage and triggering PyTorch compiler polyfill bugs (`torch._dynamo`).
  - **Fix:** Transition `embedder.py` to `optimum.onnxruntime.ORTModelForFeatureExtraction` with `all-MiniLM-L6-v2` in INT8. Keep `TORCHDYNAMO_DISABLE=1` in `backend/main.py`.
  - **Acceptance Criteria:** RAG embeddings initialize rapidly (<2s), run purely on CPU via ONNX, and never import `torch._dynamo`.

---

## Phase 3: Session Persistence & Artifact Workflow Unification
*Addresses Section 6 (Flaw 6.1) and Section 7 (Flaw 7.1) of the Architectural Audit.*

- [ ] **Task 3.1 [Audit Flaw 6.1]: Wire MongoDB Session & Message Persistence**
  - **Target Files:** `backend/api/routes.py`, `backend/core/database.py`, `frontend/src/services/aiService.ts`, `frontend/src/hooks/useSessions.ts`
  - **Audit Finding:** MongoDB is initialized in `backend/main.py` but only used for user authentication. Chat sessions and messages are stored exclusively in browser `localStorage`. Clearing cache or switching devices wipes out all conversations.
  - **Fix:**
    1. Implement session CRUD endpoints in backend (`/api/v1/sessions`, `/api/v1/sessions/{id}/messages`).
    2. Store sessions and conversation messages in MongoDB `sessions` collection.
    3. Update `useSessions.ts` to sync with backend session endpoints rather than relying only on `localStorage`.
  - **Acceptance Criteria:** Refreshing the browser, clearing local storage, or logging in from another device/browser restores all past sessions, messages, and artifact links.

- [ ] **Task 3.2 [Audit Flaw 7.1]: Unify Fragmented Artifact Workflows into Standard Tool Calls**
  - **Target Files:** `backend/artifacts/code_workflow.py`, `backend/agents/industrial_workbench.py`, `backend/tools/registry.py`, `backend/api/routes.py`
  - **Audit Finding:** Artifact generation currently splits into two divergent pipelines: direct python generation in `IndustrialWorkbenchAgent.generate_artifact()` and sandbox code execution in `CodeArtifactWorkflow`, with `detect_artifact_intent()` arbitrarily hijacking requests in `routes.py`.
  - **Fix:** Register deliverable generation tools (`artifact.document.create`, `artifact.spreadsheet.create`, `artifact.presentation.create`, `artifact.pdf.create`) directly in `ToolRegistry`. Allow the reasoning agent to invoke them as standard tools within its normal reasoning loop.
  - **Acceptance Criteria:** Artifact creation operates seamlessly through the standard agent loop without bespoke route-level hijacking.
