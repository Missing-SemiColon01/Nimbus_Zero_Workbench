# Phase 3 Implementation Plan: Conversational Chat & Real Token Streaming

## Objective
Enable multi-turn conversational chat with true token-by-token streaming from Ollama,
while preserving the existing ability to generate artifacts and use tools when requested.

## Current State (as read from codebase)

| Component | File | Key Findings |
|---|---|---|
| Model contracts | `backend/models/contracts.py:23` | `ModelRequest` has `prompt: str` only; no `messages` history |
| Providers | `backend/models/providers.py:70` | `OllamaProvider.generate` builds payload from `request.prompt` only; no streaming; `ModelProvider` ABC has `generate` only |
| Registry | `backend/models/registry.py` | All models use `runtime: ollama` (single provider) |
| API routes | `backend/api/routes.py:229` | `/tasks/stream` has fake 30-char chunk loop at lines 282-288; `create_task` uses non-streaming `agent.run()` |
| Task schema | `backend/schemas/tasks.py:24` | `TaskCreate` has no `messages` or `session_id` |
| Agent runtime | `backend/agents/runtime.py:87` | `AgentGraphState.messages: list[str]`; stores `self._streamer` (Phase 4 race fix pending); `_generate_response` calls non-streaming `generate` |
| Agent | `backend/agents/industrial_workbench.py:190` | `run()` delegates to `runtime.run()`; no `messages` param; imports `select_artifact_generation_mode` (Phase 2 removes) |
| State | `backend/agents/state.py:99` | `AgentState.messages: list[str]`; `validate_state` checks messages are non-empty strings |
| Events | `backend/agents/events.py:131` | `AgentEventStreamer` already has `emit_content_delta`, `emit_done`, `__aiter__` — ready for use |

## Dependencies on Phase 2

Phase 2 (currently "Planned" in tasks.md) must complete first or in parallel:
- **Task 2.1**: `artifact_detection.py` — remove `select_artifact_generation_mode()`, simplify `ArtifactIntent`
- **Task 2.2**: `industrial_workbench.py` — remove `_generate_structured_artifact()` and helpers, fix line 415 crash
- **Task 2.3**: `code_workflow.py` — enhance self-contained script prompts

Phase 3 code in `industrial_workbench.py` must not import `select_artifact_generation_mode` after Phase 2 removes it.

---

## Task 3.1: Conversational Model Contracts

### Files to modify
1. `backend/models/contracts.py`
2. `backend/schemas/chat.py` (new file)
3. `backend/models/providers.py`

### Changes

#### 1.1 Add `ChatMessage` dataclass — `backend/models/contracts.py`

Add after existing imports (after `ToolExecutionResult`, before `ModelRequest`):

```python
@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant", "system"]
    content: str
    images: list[str] = field(default_factory=list)
```

Update imports: add `from typing import Any, Literal`.

#### 1.2 Update `ModelRequest` — `backend/models/contracts.py:23`

Add `messages` field alongside existing `prompt`:

```python
@dataclass(frozen=True)
class ModelRequest:
    prompt: str = ""
    messages: list[ChatMessage] = field(default_factory=list)
    required_capabilities: set[str] = field(default_factory=set)
    required_modality: str = "text"
    images: list[str] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolExecutionResult] = field(default_factory=list)
```

Key design decision: `prompt` becomes optional (default `[]`) to maintain backward compatibility with callers that still construct `ModelRequest(prompt=...)`.

#### 1.3 Add Pydantic `ChatMessage` schema — `backend/schemas/chat.py` (new)

```python
from pydantic import BaseModel, Field

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str = Field(min_length=1)
    images: list[str] = Field(default_factory=list)
```

This mirrors the dataclass but is Pydantic-compatible for API input validation.

#### 1.4 Update `OllamaProvider.generate` — `backend/models/providers.py:74`

Modify message construction to use `request.messages` when available:

```python
async def generate(self, model, request: ModelRequest) -> ModelResponse:
    if request.messages:
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        # Attach images to the last user message if present
        if request.images and messages:
            for msg in reversed(messages):
                if msg["role"] == "user":
                    msg["images"] = request.images
                    break
    else:
        messages = []
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})
        if request.images:
            if messages:
                messages[-1]["images"] = request.images
            else:
                messages.append({"role": "user", "content": "", "images": request.images})

    # ... rest of payload construction (tools) stays the same
```

---

## Task 3.2: True Token-by-Token Streaming from Ollama

### Files to modify
1. `backend/models/providers.py` — add `stream_generate` to ABC and `OllamaProvider`
2. `backend/agents/runtime.py` — integrate streaming into `_generate_response`
3. `backend/api/routes.py` — eliminate fake chunking

### Changes

#### 2.1 Add `stream_generate` to `ModelProvider` ABC — `backend/models/providers.py:17`

```python
class ModelProvider(ABC):
    @abstractmethod
    async def generate(self, model, request) -> ModelResponse: ...

    async def stream_generate(self, model, request) -> AsyncIterator[str]:
        """Default: fall back to non-streaming, yield full content as one token."""
        response = await self.generate(model, request)
        if response.content:
            yield response.content
```

Add `from collections.abc import AsyncIterator, Mapping` to imports (already imports `Mapping`, add `AsyncIterator`).

#### 2.2 Implement `stream_generate` in `OllamaProvider`

```python
async def stream_generate(self, model, request) -> AsyncIterator[str]:
    messages, payload = self._build_chat_payload(model, request, stream=True)
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
            async for line in response.aiter_lines():
                if not line or not line.strip():
                    continue
                data = json.loads(line)
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
```

Extract a shared `_build_chat_payload` helper from the message-building logic shared between `generate` and `stream_generate`.

**Ollama streaming protocol**: Each line is a JSON object with `message.content` (incremental), `message.tool_calls` (final chunk only if tools used), and `done: true` on the last line.

#### 2.3 Add `stream_generate` to `ModelProviderRegistry` — `backend/models/providers.py:40`

```python
async def stream_generate(self, model, request) -> AsyncIterator[str]:
    return self.get(model.runtime).stream_generate(model, request)
```

Note: This returns an async generator; callers must `async for` over it.

#### 2.4 Integrate streaming into `AgentRuntime._generate_response` — `backend/agents/runtime.py:390`

When a streamer is available, use `stream_generate` to emit tokens in real-time:

```python
async def _generate_response(self, state: AgentGraphState) -> dict[str, Any]:
    streamer = getattr(self, "_streamer", None)
    # ... existing setup (candidates, retry loop) ...

    for i, model in enumerate(candidates):
        model_request = ModelRequest(
            prompt=self._model_prompt(state),
            messages=self._build_request_messages(state),  # NEW: full history
            required_capabilities=state["required_capabilities"],
            # ... same as current ...
        )

        try:
            if streamer is not None:
                # Stream tokens directly to SSE
                async for token in self.providers.stream_generate(model, model_request):
                    streamer.emit_content_delta(token)
                accumulated = self._drain_stream_buffer(model, model_request)  # OR use non-streaming for tool detection
            else:
                response = await self.providers.generate(model, model_request)
                accumulated = response.content
        except ...
```

**Simplification decision**: For Phase 3, when a streamer is active:
- Stream text tokens via `emit_content_delta` for the agent's text response
- After streaming, if the model has tool capabilities AND tools are configured, call `generate` (non-streaming) once to detect tool calls
- This avoids needing to parse Ollama's tool_calls from streaming JSON

Rationale: Tool-call streaming requires parsing JSON lines for `tool_calls` which is more complex. Phase 3 focuses on conversational text streaming (the common case). Tool call rounds fall back to non-streaming but still emit content directly (no fake chunking).

#### 2.5 Eliminate fake chunking in routes.py — `backend/api/routes.py:282-288`

Remove the entire fake chunking block:
```python
# REMOVE:
if state.final_response or model_response.content:
    final_text = state.final_response or model_response.content
    chunk_size = 30
    for i in range(0, len(final_text), chunk_size):
        streamer.emit_content_delta(final_text[i:i + chunk_size])
        await asyncio.sleep(0)
```

Streaming now happens inside `agent.run()` via the runtime. The SSE endpoint just drains the streamer queue.

---

## Task 3.3: Multi-Turn Conversation History in API & Agent State

### Files to modify
1. `backend/schemas/tasks.py` — add `messages`, `session_id` to `TaskCreate`
2. `backend/agents/runtime.py` — accept and use conversation history
3. `backend/agents/industrial_workbench.py` — pass `messages` through
4. `backend/agents/state.py` — update `AgentState.messages` type
5. `backend/api/routes.py` — pass `messages` and `session_id`

### Changes

#### 3.1 Update `TaskCreate` — `backend/schemas/tasks.py:24`

```python
from backend.schemas.chat import ChatMessage  # NEW import

class TaskCreate(BaseModel):
    request: str = Field(min_length=1, max_length=20000)
    messages: list[ChatMessage] = Field(default_factory=list)
    session_id: str | None = None
    # ... rest unchanged ...
```

#### 3.2 Update `AgentGraphState.messages` — `backend/agents/runtime.py:63`

Change type from `list[str]` to `list[ChatMessage]`:
```python
from backend.models.contracts import ChatMessage  # ADD import

class AgentGraphState(TypedDict):
    # ...
    messages: list[ChatMessage]  # was list[str]
    # ...
```

#### 3.3 Update `AgentRuntime.run()` signature — `backend/agents/runtime.py:114`

Add `messages` parameter:
```python
async def run(
    self,
    user_request: str,
    capabilities: set[str],
    modality: str = "text",
    *,
    task_id: str | None = None,
    messages: list[ChatMessage] | None = None,  # NEW
    ...
) -> tuple[AgentState, ModelResponse]:
```

Convert incoming messages into graph state:
```python
# Replace line 133:
# OLD: initial_messages = [user_request] if isinstance(user_request, str) and user_request.strip() else []
# NEW:
user_msg = ChatMessage(role="user", content=user_request) if user_request.strip() else None
initial_messages: list[ChatMessage] = list(messages or [])  # historical messages
if user_msg is not None:
    initial_messages.append(user_msg)
```

Add new method `_build_request_messages` to convert state messages to `ChatMessage` list for `ModelRequest`:
```python
@staticmethod
def _build_request_messages(state: AgentGraphState) -> list[ChatMessage]:
    """Convert graph state messages to ModelRequest ChatMessage list."""
    msgs = state.get("messages", [])
    if not msgs:
        return []
    return msgs if all(isinstance(m, ChatMessage) for m in msgs) else []
```

#### 3.4 Update `ModelRequest` construction — `backend/agents/runtime.py:397`

In `_generate_response`, add `messages`:
```python
model_request = ModelRequest(
    prompt=self._model_prompt(state),    # retained for backward compat
    messages=state.get("messages", []),  # NEW
    required_capabilities=state["required_capabilities"],
    ...
)
```

In `_generate_with_tools`, also add `messages` to the retry `ModelRequest` construction (line 501-509).

#### 3.5 Update `AgentState` — `backend/agents/state.py:99`

Change `messages: list[str]` to `messages: list[ChatMessage]`:
```python
from backend.models.contracts import ChatMessage  # ADD import

@dataclass
class AgentState:
    # ...
    messages: list[ChatMessage] = field(default_factory=list)
    # ...
```

#### 3.6 Update `validate_state` — `backend/agents/state.py:34`

Allow `ChatMessage` objects in the messages list:
```python
# In validate_state, replace the messages check:
if not isinstance(messages, list) or len(messages) == 0:
    raise StateValidationError("Field 'messages' must be a non-empty list")
for i, msg in enumerate(messages):
    if isinstance(msg, str):
        if not msg.strip():
            raise StateValidationError(f"Field 'messages[{i}]' must be non-empty")
    elif hasattr(msg, 'content') and hasattr(msg, 'role'):
        if not msg.content or not msg.content.strip():
            raise StateValidationError(f"Field 'messages[{i}].content' must be non-empty")
    else:
        raise StateValidationError(f"Field 'messages[{i}]' must be a string or ChatMessage")
```

#### 3.7 Update `IndustrialWorkbenchAgent.run()` — `backend/agents/industrial_workbench.py:190`

Add `messages` parameter and pass through:
```python
async def run(
    self,
    user_request: str,
    capabilities: set[str],
    modality: str = "text",
    *,
    task_id: str | None = None,
    messages: list[ChatMessage] | None = None,  # NEW
    images: list[str] | None = None,
    ...
) -> tuple[AgentState, ModelResponse]:
    return await self.runtime.run(
        user_request,
        capabilities,
        modality,
        task_id=task_id,
        messages=messages,  # NEW
        ...
    )
```

Add import: `from backend.models.contracts import ChatMessage`

#### 3.8 Update routes.py — `backend/api/routes.py`

In `create_task` (line 147) and `stream_task` (line 229), pass `messages` and `session_id`:
```python
state, model_response = await request.app.state.agent.run(
    payload.request,
    required_capabilities,
    payload.modality,
    images=payload.images,
    documents=documents,
    approved_tools=payload.approved_tools,
    streamer=streamer,
    messages=payload.messages,  # NEW
)
```

---

## Task 3.4: Dynamic Mode Routing (Chat vs. Artifact Generation)

### Files to modify
1. `backend/api/routes.py` — restructure routing logic in `create_task` and `stream_task`
2. `backend/agents/industrial_workbench.py` — add conversational chat method

### Changes

### 4.1 Refine `detect_artifact_intent` — `backend/agents/artifact_detection.py`

No new detection logic needed (already exists). The routing is:
- If `detect_artifact_intent()` returns non-None → artifact generation path (`generate_artifact`)
- If returns None → conversational chat path (`agent.run()`)

Current code in routes.py already has this branching (lines 158-183 and 249-279). The key change for Phase 3 is ensuring the conversational path properly streams.

### 4.2 Add `chat` method to `IndustrialWorkbenchAgent` — `backend/agents/industrial_workbench.py`

Add a lightweight conversational method that wraps `run()` without artifact detection:

```python
async def chat(
    self,
    user_request: str,
    *,
    capabilities: set[str] | None = None,
    messages: list[ChatMessage] | None = None,
    tool_ids: str | None = None,
    streamer: AgentEventStreamer | None = None,
    **kwargs,
) -> tuple[AgentState, ModelResponse]:
    """Conversational turn: run the agent without artifact-generation routing."""
    caps = capabilities or {"reasoning"}
    return await self.run(
        user_request,
        caps,
        modality="text",
        messages=messages,
        streamer=streamer,
        **kwargs,
    )
```

### 4.3 Restructure routes.py routing logic

In both `create_task` and `stream_task`, replace the current detection-and-route pattern with a cleaner structure:

```python
# Current pattern (already mostly in place):
artifact_intent = detect_artifact_intent(payload.request, payload.task_type)
if artifact_intent is not None and callable(generate_artifact):
    # Artifact path
    result = await generate_artifact(...)
else:
    # Conversational path
    state, model_response = await agent.run(...)
```

The change for Phase 3: ensure the conversational path always uses streaming when a streamer is present (which is the `/tasks/stream` endpoint), and ensure `messages` and `session_id` are passed through.

For `/tasks/stream`, the `_run_task` inner function must:
1. Check `detect_artifact_intent` → if artifact, call `generate_artifact` (existing behavior)
2. If no artifact intent → call `agent.run()` with `streamer` and `messages` (streaming path)
3. The streaming now happens inside the runtime (Task 3.2), so no fake chunking after

### 4.4 Optional: emit `session_id` in task_init event

In `AgentEventStreamer.emit_task_init`, add optional `session_id`:
```python
@dataclass
class TaskInitPayload:
    task_id: str
    model: str | None = None
    intent: str | None = None
    capabilities: list[str] = field(default_factory=list)
    session_id: str | None = None  # NEW
```

Update `emit_task_init` signature and call site in runtime.

---

## Implementation Order

1. **Task 3.1** (contracts first) — no breaking changes, additive only
2. **Task 3.2** (streaming infrastructure) — depends on 3.1's `ModelRequest.messages`
3. **Task 3.3** (state & API) — depends on 3.1, modifies state types
4. **Task 3.4** (routing) — depends on all above

## Testing & Verification

- `python -m pytest backend/tests/` (if tests exist)
- `python -c "from backend.models.contracts import ChatMessage, ModelRequest; print('OK')"`
- `python -c "from backend.models.providers import OllamaProvider; assert hasattr(OllamaProvider, 'stream_generate')"`
- `python -c "from backend.schemas.tasks import TaskCreate; assert 'messages' in TaskCreate.model_fields"`
- Lint: `python -m ruff check backend/` (if configured)

## Known Limitations / Future Work

- **Tool-call streaming**: Phase 3 streams text tokens but falls back to non-streaming for tool-call detection. Parsing Ollama's `tool_calls` from streaming JSON is a Phase 4 optimization.
- **Streamer race condition**: `AgentRuntime` still stores `self._streamer` as instance state (Task 4.2 in Phase 4 fixes this by passing streamer through state/context dicts).
- **`emit_done` queue-full**: `AgentEventStreamer.emit_done` silently drops the sentinel if the queue is full (Task 4.3 in Phase 4 fixes this).
- **Session state**: `session_id` is accepted but not yet persisted to a session store. In-memory conversation history is passed per-request via `messages`.
