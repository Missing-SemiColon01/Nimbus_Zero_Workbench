# Comprehensive Architectural Audit & Remediation Plan
**Sovereign AI Workbench**  
**Document Version:** 1.0  
**Scope:** Agent Loop, Model Routing, Multimodal/RAG Pipelines, State & Session Management, Tool Integration  

---

## Executive Summary

A comprehensive architectural audit of the Sovereign AI Workbench was performed across the frontend, backend API, LangGraph runtime, model routing layer, and tool execution boundaries. 

The audit identified **7 major architectural flaws** causing system instability, including:
1. **Agent Loop Desynchronization & Multi-Call Bugs** (streaming token leaks, triple generation, dropped tool memory).
2. **Model Router Rigid Subset Matching & Broken Orchestration** (`[reasoning, vision]` crashes, bypassing the agent tool pattern).
3. **System Prompt & Identity Loss** (system instructions completely discarded in chat turns).
4. **Disconnected Multimodal & Document Pipeline** (PDFs never read in frontend, Ollama API document protocol mismatches).
5. **PyTorch TorchDynamo Compiler Crash in RAG Embedder** (unintended compiler polyfill triggers during Transformers import).
6. **Ephemeral Client-Side Session Storage** (MongoDB initialized but unused for chat; state trapped in browser `localStorage`).
7. **Bypassed Agent Method Abstractions** (`inspect_multimodal` built for orchestration but bypassed by API routes).

Below is the exhaustive architectural breakdown with root-cause analyses and technical remediation specifications for each.

---

```
                                  ARCHITECTURAL OVERVIEW & PROBLEM FLOW

┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                             FRONTEND (React)                                           │
│  [ChatComposer.tsx]                                                                                    │
│   • Bug: Only reads images to dataUrl; PDFs/DOCX left undefined                                        │
│   • Bug: Raw data URIs ("data:image/png;base64,...") passed without sanitization                      │
└───────────────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                                    │ POST /api/tasks/stream
                                                    ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                            BACKEND API (FastAPI)                                       │
│  [routes.py]                                                                                           │
│   • Bug: Disconnected from agent.inspect_multimodal(); calls agent.run() directly                     │
│   • Bug: Payload documents bypassed text extraction; passed raw to runtime                             │
└───────────────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       AGENT RUNTIME & ORCHESTRATION                                    │
│  [runtime.py]                                                                                          │
│   • Bug: Linear LangGraph pipeline (START -> validate -> generate -> output -> END)                   │
│          Actual loop is hidden inside a hardcoded Python `for` loop.                                   │
│   • Bug: Streaming performs 3 Ollama calls per turn (stream_generate -> generate -> with_tools).       │
│   • Bug: Tool calls streamed as raw JSON to user UI; final synthesized answer never streamed.         │
│   • Bug: Tool results appended to prompt string, but ignored because messages history exists.          │
│   • Bug: Tool execution history never recorded into conversational messages state.                     │
└───────────────────────┬───────────────────────────────────────────────────┬────────────────────────────┘
                        │                                                   │
                        ▼                                                   ▼
┌───────────────────────────────────────────────┐   ┌────────────────────────────────────────────────────┐
│          MODEL ROUTER & REGISTRY              │   │               TOOLS & MULTIMODAL                   │
│  [router.py / registry.py / models.yaml]      │   │  [vision_tool.py / rag_tool.py / embedder.py]      │
│   • Bug: Strict subset check (req <= model)   │   │   • Bug: Runtime bypasses vision.analyze tool;     │
│   • Bug: Mutually exclusive capabilities:     │   │          tries to force reasoning model into image │
│          qwen3:14b = text reasoning only      │   │   • Bug: Ollama /api/chat receives "documents"     │
│          qwen2.5-vl:7b = vision only          │   │          field which Ollama silently ignores       │
│   • Bug: Images force req={"reasoning","vision"}│   │   • Bug: TorchDynamo compiler collision crashes    │
│          -> No compatible model exists!       │   │          AutoModel embedder on BERT imports        │
└───────────────────────────────────────────────┘   └────────────────────────────────────────────────────┘
```

---

## 1. Agent Loop & LangGraph Runtime Architecture

### Flaw 1.1: Pseudomorphic LangGraph Implementation (Linear Pipeline vs. Agentic Graph)
* **Location:** `backend/agents/runtime.py` (`AgentRuntime.__init__`)
* **Problem:**  
  The runtime instantiates a LangGraph `StateGraph(AgentGraphState)`, but wires it as a strict single-pass linear pipe:
  ```python
  workflow.add_edge(START, "validate_input")
  workflow.add_edge("validate_input", "generate_response")
  workflow.add_edge("generate_response", "validate_output")
  workflow.add_edge("validate_output", END)
  ```
  The actual cyclic execution (tool invocation, validation, reflection, re-prompting) is trapped in a hardcoded `for _ in range(self.config.max_tool_rounds)` inside `_generate_with_tools()`. As a result, LangGraph's step limits (`max_steps=15`), recursion controls, and loop detection (`detect_cycle`) are never exercised by the tool rounds.
* **Fix:**  
  Refactor the LangGraph graph into an actual cyclic state graph:
  ```mermaid
  graph TD
      START --> validate_input
      validate_input --> model_node
      model_node --> condition{Has Tool Calls?}
      condition -- Yes --> tools_node
      tools_node --> model_node
      condition -- No --> validate_output
      validate_output --> END
  ```
  Each node transitions through LangGraph edges, enabling checkpointing, fine-grained streaming, and genuine loop limits.

---

### Flaw 1.2: Triple Generation & Streaming Desync Bug
* **Location:** `backend/agents/runtime.py` (`_generate_response` lines 446–520)
* **Problem:**  
  When requests arrive via the SSE endpoint (`/tasks/stream`), `streamer` is not None. The code executes:
  1. `stream_generate(model, model_request)`: Streams LLM tokens directly to the SSE queue.
  2. `if model_request.tools: generate(model, model_request)`: Executes a **second** generation call synchronously.
  3. `_generate_with_tools()`: Executes a **third** generation call synchronously inside the tool loop.
  
  **Consequences:**
  - 3x latency and compute overhead per turn.
  - If Call #1 outputs a tool invocation, raw JSON like `{"name": "rag.search", ...}` is streamed to the user's chat bubble.
  - The final answer produced after tools finish in Call #3 is **never streamed** because `_generate_with_tools()` uses non-streaming calls and never emits `content_delta` events. The user's screen is left frozen displaying raw tool JSON.
* **Fix:**  
  Remove Call #1 and Call #2. Unify streaming inside the tool loop:
  - If the model generates content deltas, buffer them until a complete token or tool-call block is verified.
  - If a tool call is detected, emit `tool_call_start` and execute the tool.
  - On the final synthesis turn, stream the tokens directly to `streamer.emit_content_delta()`.

---

### Flaw 1.3: Brittle Tool-Call Parsing (Markdown Code-Block Failure)
* **Location:** `backend/agents/runtime.py` (`_detect_tool_calls` lines 609–630)
* **Problem:**  
  The parser only accepts raw JSON objects:
  ```python
  stripped = response.content.strip()
  payload = json.loads(stripped)
  ```
  Open-source models like Qwen frequently wrap structured outputs in markdown code blocks:
  ````markdown
  ```json
  {"name": "rag.search", "arguments": {"query": "safety valves"}}
  ```
  ````
  `json.loads()` immediately raises `json.JSONDecodeError` on markdown fences. The tool call is ignored, and the agent exits without executing the tool.
* **Fix:**  
  Add regex-based fence stripping prior to parsing:
  ```python
  def _clean_json_content(content: str) -> str:
      match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
      return match.group(1).strip() if match else content.strip()
  ```

---

### Flaw 1.4: Hard Crash on Max Tool Rounds
* **Location:** `backend/agents/runtime.py` (`_generate_with_tools` line 616)
* **Problem:**  
  If the model executes tools for 3 rounds (the default `max_tool_rounds`), it crashes with an unhandled exception:
  ```python
  raise ProviderError(f"Maximum tool rounds ({self.config.max_tool_rounds}) exceeded")
  ```
  This causes the entire user request to fail with a `502 Bad Gateway` error instead of formulating an answer with the evidence gathered so far.
* **Fix:**  
  When `max_tool_rounds` is reached, strip tool definitions from `ModelRequest` and make one final call to the model:
  ```python
  final_request = ModelRequest(
      prompt="Synthesize a final response based solely on the tool results gathered so far.",
      messages=round_messages,
      tools=[],  # Disable further tool calling
  )
  return await self.providers.generate(model, final_request)
  ```

---

### Flaw 1.5: Tool Context Evaporation in Conversational History
* **Location:** `backend/agents/runtime.py` (`_generate_response` line 511)
* **Problem:**  
  When tool calling concludes, the state is finalized with:
  ```python
  "messages": [*state["messages"], ChatMessage(role="assistant", content=final_content)]
  ```
  Intermediate tool calls and tool outputs are excluded from `state["messages"]`. On subsequent turns, the agent has no memory of previous tool findings, causing repetitive tool queries or hallucinations.
* **Fix:**  
  Persist tool calls and tool execution outputs in `messages`:
  ```python
  persisted_messages = [
      *state["messages"],
      ChatMessage(role="assistant", content=tool_call_summary, tool_calls=tool_calls),
      ChatMessage(role="user", content=f"Tool Execution Results:\n{tool_results_json}"),
      ChatMessage(role="assistant", content=final_content),
  ]
  ```

---

## 2. Model Routing & Orchestration Architecture

### Flaw 2.1: Subset Matching Deadlock (`capabilities <= model.capabilities`)
* **Location:** `backend/models/registry.py` (`candidates` line 30) & `configs/models.yaml`
* **Problem:**  
  The registry filters candidates strictly by subset matching:
  ```python
  model for model in self.models if capabilities <= model.capabilities and modality in model.modalities
  ```
  In `configs/models.yaml`:
  - `qwen3:14b`: `capabilities: [reasoning, planning, tool_calling]`, `modalities: [text]`
  - `qwen2.5-vl:7b`: `capabilities: [vision, document_understanding]`, `modalities: [text, image, document]`
  
  When an image is attached to chat, `capabilities` becomes `{"reasoning", "vision"}` and `modality` becomes `"image"`.
  - `qwen3:14b` fails the `vision` capability and `image` modality checks.
  - `qwen2.5-vl:7b` fails the `reasoning` capability check.
  
  The candidate list evaluates to empty `[]`, raising `NoCompatibleModelError: No compatible model exists for modality 'image' with capabilities: reasoning, vision`.
* **Fix:**  
  1. Add `reasoning` to `qwen2.5-vl:7b` capabilities in `configs/models.yaml`.
  2. Implement capability scoring instead of hard subset equality, prioritizing models that best satisfy primary modalities and capabilities with fallback weights.

---

### Flaw 2.2: Architectural Identity Crisis: Monolithic Model vs. Orchestrator-Worker
* **Location:** `backend/agents/runtime.py` vs. `backend/agents/industrial_workbench.py`
* **Problem:**  
  The codebase has two mutually conflicting concepts of vision handling:
  - **Concept A (Orchestrator-Worker via Tools):** `qwen3:14b` is the reasoning agent. It uses `vision.analyze` as a tool. `vision.analyze` calls `qwen2.5-vl:7b` under the hood, and returns text findings to `qwen3:14b`.
  - **Concept B (End-to-End Multimodal Model):** The top-level agent is replaced by `qwen2.5-vl:7b` whenever an image is uploaded.
  
  When an image was uploaded, `runtime.py` executed Concept B by modifying the top-level request to `modality="image"`, while `routes.py` and `industrial_workbench.py` assumed Concept A.
* **Fix:**  
  Explicitly formalize the architecture:
  - Standardize on **Orchestrator-Worker**:
    Chat turns always route to the Reasoning Agent (`qwen3:14b`).
    Images uploaded by users are saved to disk, and the reasoning agent is instructed to invoke `vision.analyze(image_path=...)` to inspect them.
    Alternatively, pre-execute `vision.analyze` on image inputs prior to calling the reasoning agent (as `inspect_multimodal` does).

---

## 3. System Prompt & Identity Delivery Architecture

### Flaw 3.1: System Instructions Lost Due to History Priority
* **Location:** `backend/agents/runtime.py` (`_build_request_messages`) & `backend/models/contracts.py` (`normalize_messages`)
* **Problem:**  
  - In `IndustrialWorkbenchAgentConfig`, the system prompt is defined: `"You are the Industrial Workbench Agent..."`.
  - In `runtime.py`, `_model_prompt()` formatted it into `request.prompt = f"System instructions:\n{system_prompt}\n\nUser request:\n{user_prompt}"`.
  - But `_build_request_messages()` created `request.messages` with only user/assistant turns (no system message).
  - In `contracts.py`:
    ```python
    if messages:
        normalized = list(messages)  # <--- prompt is completely ignored!
    ```
  - Whenever chat history existed, `request.prompt` was discarded. Ollama received `[{"role": "user", "content": "..."}]` with zero system instructions, causing Qwen to revert to its default identity: *"I am Qwen, a large language model developed by Alibaba Cloud."*
* **Fix:**  
  Always inject a `ChatMessage(role="system", content=system_prompt)` at the root of `request.messages`, and update `normalize_messages()` to never discard system instructions.

---

## 4. Multimodal & Document Processing Architecture

### Flaw 4.1: Frontend Attachment Omission for Non-Images
* **Location:** `frontend/src/components/chat/ChatComposer.tsx` (`processFile` lines 87–94)
* **Problem:**  
  ```typescript
  if (type === "image") {
    att.dataUrl = await readAsDataURL(file)
  }
  return att
  ```
  `dataUrl` was only populated for images. For PDFs, DOCX, and text files, `dataUrl` and `url` were left `undefined`. In `Chat.tsx`:
  ```typescript
  documents: attachments.filter((a) => a.type !== "image" && (a.dataUrl || a.url))
  ```
  This evaluated to `[]` (empty list). The PDF was never uploaded or sent to the backend. The backend received `documents: []` and the LLM received only `"summarize this pdf"`, naturally replying: *"Please specify the path of the PDF."*
* **Fix:**  
  Read all valid files using `FileReader.readAsDataURL()` in `ChatComposer.tsx` so `att.dataUrl` and `att.url` are always populated.

---

### Flaw 4.2: Ollama `/api/chat` Top-Level Document Incompatibility
* **Location:** `backend/models/providers.py` (`_build_payload` line 194)
* **Problem:**  
  ```python
  if request.documents:
      payload["documents"] = request.documents
  ```
  Ollama's `/api/chat` API only accepts `model`, `messages`, `tools`, `format`, and `options`. It has no support for a top-level `"documents"` array and silently ignores it.
* **Fix:**  
  The backend must unpack document attachments:
  1. Save Base64 documents to `data/uploads/`.
  2. Extract plain text using PyMuPDF (`fitz`).
  3. Prepend document text to the user's turn:
     ```
     [Attached Document Content: filename.pdf]
     [Page 1] ...
     ```

---

### Flaw 4.3: Raw Base64 vs. Data URI Incompatibility
* **Location:** `frontend/src/pages/Chat.tsx` vs. `backend/models/providers.py`
* **Problem:**  
  The browser creates Data URIs (`data:image/png;base64,iVBORw...`). Ollama's vision API expects pure Base64 strings. Passing Data URIs directly causes Ollama's Go base64 decoder to fail with parsing errors.
* **Fix:**  
  Sanitize all image payloads before transmitting to Ollama:
  ```python
  def _clean_base64_image(data: str) -> str:
      return data.split(",", 1)[1] if (data.startswith("data:") and "," in data) else data
  ```

---

## 5. RAG & Vector Store Stability Architecture

### Flaw 5.1: TorchDynamo Polyfill Registry Collision
* **Location:** `.venv/lib/python3.11/site-packages/torch/_dynamo/decorators.py` (line 972)
* **Problem:**  
  When `embedder.py` executes `from transformers import AutoModel`, Hugging Face `transformers` imports its BERT attention integration:
  `transformers/integrations/flex_attention.py` $\rightarrow$ `@torch.compiler.disable(recursive=False)` $\rightarrow$ `import torch._dynamo`.
  
  During TorchDynamo's built-in polyfill registration, PyTorch registers graph substitutions for `sys.intern`. Under Python 3.11 with conflicting PyTorch versions, `id(sys.intern)` is registered twice in `VariableBuilder`, triggering:
  ```
  ValueError: Duplicate dispatch rule for <built-in function intern>: already registered in VariableBuilder's id dispatch map
  ```
  This immediately crashes any endpoint invoking RAG (`rag_tool.py`).
* **Fix:**  
  1. Set environment variables at startup in `backend/main.py`:
     ```python
     os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
     os.environ.setdefault("TORCH_COMPILE_DISABLE", "1")
     ```
  2. Transition `backend/knowledge/embedder.py` from PyTorch eager loading to the intended INT8 ONNX runtime via `optimum[onnxruntime]`, avoiding PyTorch compiler imports entirely.

---

## 6. State & Session Persistence Architecture

### Flaw 6.1: Ephemeral LocalStorage vs. Unused Database Layer
* **Location:** `frontend/src/hooks/useSessions.ts` vs. `backend/core/database.py`
* **Problem:**  
  - MongoDB is configured and initialized in `backend/main.py`, but it is only used by `backend/api/auth.py` for user credentials.
  - Chat sessions, messages, and execution traces are stored exclusively in the browser's `localStorage` (`sovereign-sessions`).
  - If a user clears cookies, uses another browser, or accesses the application from a mobile device, all chat sessions and artifacts are lost.
  - The backend has no visibility into conversation context across sessions.
* **Fix:**  
  Implement a backend MongoDB collection `sessions` and endpoints:
  - `GET /api/v1/sessions`: List sessions for current user.
  - `POST /api/v1/sessions`: Create new session.
  - `GET /api/v1/sessions/{id}/messages`: Fetch session messages.
  - `POST /api/v1/sessions/{id}/messages`: Append turn to session history.

---

## 7. Artifact Workflow Duplication Architecture

### Flaw 7.1: Fragmented Artifact Generation Logic
* **Location:** `backend/artifacts/code_workflow.py` vs. `backend/agents/industrial_workbench.py` (`generate_artifact`)
* **Problem:**  
  Artifact generation currently has two parallel paths:
  1. `IndustrialWorkbenchAgent.generate_artifact()`: Directly builds docx/pptx/xlsx/pdf using local python libraries (`reportlab`, `python-docx`, `python-pptx`, `openpyxl`).
  2. `CodeArtifactWorkflow`: Prompts a coding model (`qwen2.5-coder:14b`) to write a python script, executes it in a Docker sandbox, and validates the file.
  
  In `routes.py`, `detect_artifact_intent()` arbitrarily intercepts requests and routes them to `generate_artifact()`, bypassing the standard agent conversation and tool loop.
* **Fix:**  
  Unify artifact generation into standard tool calls:
  Register `artifact.document.create`, `artifact.spreadsheet.create`, `artifact.presentation.create`, and `artifact.pdf.create` as regular tools in `ToolRegistry`. Allow the reasoning agent to decide when and how to generate deliverables as part of its normal reasoning loop.

---

## Summary Matrix of Issues & Fix Status

| ID | Component | Architectural Issue | Severity | Status |
|:---|:---|:---|:---|:---|
| **1.1** | Runtime | Pseudomorphic LangGraph pipeline (linear pipe instead of loop) | High | Audited |
| **1.2** | Runtime | Triple Ollama call bug & tool output stream desync in SSE | Critical | Audited |
| **1.3** | Runtime | Brittle tool parser breaks on ` ```json ` markdown fences | High | Audited |
| **1.4** | Runtime | Hard crash with `ProviderError` on tool round limit | Medium | Audited |
| **1.5** | Runtime | Intermediate tool calls dropped from conversation state | High | Patched |
| **2.1** | Routing | Subset matching deadlock on multi-capabilities (`[reasoning, vision]`) | Critical | Root-caused |
| **2.2** | Orchestration | Broken agent architecture (bypassing `vision.analyze` tool pattern) | High | Root-caused |
| **3.1** | Prompts | System prompt discarded whenever chat history exists | Critical | Patched |
| **4.1** | Frontend | PDF attachments never read into memory by `ChatComposer.tsx` | Critical | Patched |
| **4.2** | Providers | Ollama `/api/chat` sent unsupported `"documents"` field | High | Patched |
| **4.3** | Providers | Raw Base64 vs. Data URI mismatch for Ollama vision | High | Patched |
| **5.1** | RAG / Torch | PyTorch `torch._dynamo` duplicate dispatch crash on BERT imports | Critical | Patched |
| **6.1** | Storage | Chat sessions stored only in browser `localStorage`; MongoDB unused | Medium | Audited |
| **7.1** | Artifacts | Fragmented artifact pipelines (direct python vs Docker sandbox) | Medium | Audited |

---

## Recommended Next Steps

1. **Implement True LangGraph Tool Loop:**  
   Replace the linear LangGraph pipeline with a cyclic state graph that natively transitions between `model_node` and `tools_node` with token streaming.
2. **Standardize Orchestrator-Worker Pattern:**  
   Always route user chat turns to the primary reasoning agent (`qwen3:14b`) with `vision.analyze` registered as a tool, instead of attempting to replace the orchestrator with specialized worker models.
3. **Persist Sessions to MongoDB:**  
   Migrate chat session state from client-side `localStorage` to the existing MongoDB database connection pool.
