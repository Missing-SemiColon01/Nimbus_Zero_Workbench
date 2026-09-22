from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import time
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.state import (
    AgentState,
    InfiniteLoopError,
    StateValidationError,
    StepLimitExceededError,
    WorkflowTimeoutError,
    validate_state,
)
from backend.models.contracts import ChatMessage, ModelRequest, ModelResponse, ToolCall, ToolExecutionResult
from backend.models.providers import ModelProviderRegistry, ProviderError, ProviderRequestError
from backend.models.router import ModelRouter
from backend.security.policy import PolicyDecision, PolicyEngine
from backend.tools.contracts import ToolResult
from backend.tools.registry import ToolRegistry
from backend.agents.events import AgentEventStreamer


@dataclass(frozen=True)
class RuntimeConfig:
    timeout: float = 300.0
    tool_timeout: float = 120.0
    tool_allowlist: frozenset[str] | None = None
    max_retries: int = 3
    max_steps: int = 30
    max_tool_rounds: int = 15


def detect_cycle(history: list[str], min_repetitions: int = 3) -> bool:
    """Detect if a sequence of node names repeats min_repetitions times at the end of history."""
    n = len(history)
    for cycle_len in range(1, (n // min_repetitions) + 1):
        candidate = history[-cycle_len:]
        is_cycle = True
        for rep in range(1, min_repetitions):
            start_idx = n - (rep + 1) * cycle_len
            end_idx = n - rep * cycle_len
            if history[start_idx:end_idx] != candidate:
                is_cycle = False
                break
        if is_cycle:
            return True
    return False


class AgentGraphState(TypedDict):
    """The minimal, provider-agnostic state passed through the agent graph."""

    task_id: str
    user_prompt: str
    system_prompt: str | None
    selected_model: str | None
    messages: list[ChatMessage]
    images: list[str]
    documents: list[str]
    final_response: str | None
    errors: list[str]
    attempted_models: list[str]
    provider: str | None
    fallback_used: bool
    model_response: ModelResponse | None
    required_capabilities: set[str]
    modality: str
    status: str
    execution_duration: float | None
    step_count: int
    node_history: list[str]
    max_retries: int
    max_steps: int
    tool_results: list[ToolExecutionResult]
    tool_allowlist: set[str] | None
    approved_tools: set[str]
    approval_required: bool
    approval_requests: list[dict[str, Any]]
    streamer: AgentEventStreamer | None


class AgentRuntime:
    """Minimal LangGraph orchestration over the model routing boundary with reliability controls."""

    def __init__(
        self,
        router: ModelRouter,
        providers: ModelProviderRegistry,
        tools: ToolRegistry | None = None,
        config: RuntimeConfig | None = None,
        policy: PolicyEngine | None = None,
    ):
        self.router = router
        self.providers = providers
        self.tools = tools
        self.config = config or RuntimeConfig()
        self.policy = policy or PolicyEngine()

        workflow = StateGraph(AgentGraphState)
        workflow.add_node("validate_input", self._validate_input)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("validate_output", self._validate_output)
        workflow.add_edge(START, "validate_input")
        workflow.add_edge("validate_input", "generate_response")
        workflow.add_edge("generate_response", "validate_output")
        workflow.add_edge("validate_output", END)
        self.graph = workflow.compile()

    async def run(
        self,
        user_request: str,
        capabilities: set[str],
        modality: str = "text",
        *,
        task_id: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        max_steps: int | None = None,
        tool_allowlist: set[str] | None = None,
        approved_tools: set[str] | None = None,
        images: list[str] | None = None,
        documents: list[str] | None = None,
        system_prompt: str | None = None,
        streamer: AgentEventStreamer | None = None,
        messages: list[ChatMessage] | None = None,
        session_id: str | None = None,
    ) -> tuple[AgentState, ModelResponse]:
        """Run the agent workflow for one task with reliability controls."""
        start_time = time.perf_counter()
        resolved_task_id = task_id or str(uuid.uuid4())
        user_msg = ChatMessage(role="user", content=user_request) if user_request.strip() else None
        initial_messages: list[ChatMessage] = []
        for m in (messages or []):
            if isinstance(m, ChatMessage):
                initial_messages.append(m)
            elif hasattr(m, "role") and hasattr(m, "content"):
                initial_messages.append(ChatMessage(role=m.role, content=m.content, images=getattr(m, "images", []) or []))
            elif isinstance(m, dict):
                initial_messages.append(ChatMessage(role=m.get("role", "user"), content=m.get("content", ""), images=m.get("images", []) or []))
        if user_msg is not None:
            initial_messages.append(user_msg)
        resolved_images = self._validate_attachments(images, "images")
        resolved_documents = self._validate_attachments(documents, "documents")
        resolved_capabilities = set(capabilities)
        resolved_modality = modality
        if resolved_images:
            resolved_capabilities.add("vision")
            resolved_modality = "image"
        if resolved_documents:
            resolved_capabilities.add("document_understanding")
            # Image-capable document models commonly handle both inputs. A
            # document-only request uses the explicit document modality.
            if not resolved_images:
                resolved_modality = "document"

        effective_timeout = timeout if timeout is not None else self.config.timeout
        effective_max_retries = max_retries if max_retries is not None else self.config.max_retries
        effective_max_steps = max_steps if max_steps is not None else self.config.max_steps
        effective_tool_allowlist = self._effective_tool_allowlist(tool_allowlist)

        if streamer is not None:
            streamer.emit_task_init(
                task_id=resolved_task_id,
                capabilities=sorted(resolved_capabilities),
                session_id=session_id,
            )
            streamer.emit_thought("Validating request and routing to best available model...")

        initial_state: AgentGraphState = {
            "task_id": resolved_task_id,
            "user_prompt": user_request,
            "system_prompt": system_prompt.strip() if isinstance(system_prompt, str) and system_prompt.strip() else None,
            "selected_model": None,
            "messages": initial_messages,
            "images": resolved_images,
            "documents": resolved_documents,
            "final_response": None,
            "errors": [],
            "attempted_models": [],
            "provider": None,
            "fallback_used": False,
            "model_response": None,
            "required_capabilities": resolved_capabilities,
            "modality": resolved_modality,
            "status": "queued",
            "execution_duration": None,
            "step_count": 0,
            "node_history": [],
            "max_retries": effective_max_retries,
            "max_steps": effective_max_steps,
            "tool_results": [],
            "tool_allowlist": effective_tool_allowlist,
            "approved_tools": set(approved_tools or ()),
            "approval_required": False,
            "approval_requests": [],
            "streamer": streamer,
        }

        # Pre-validate input state before invoking workflow
        validate_state(initial_state, require_model=False)

        try:
            graph_call = self.graph.ainvoke(
                initial_state,
                config={"recursion_limit": max(effective_max_steps * 2, 25)},
            )
            if effective_timeout is not None and effective_timeout > 0:
                result = await asyncio.wait_for(graph_call, timeout=effective_timeout)
            else:
                result = await graph_call
        except (TimeoutError, asyncio.TimeoutError):
            execution_duration = round(time.perf_counter() - start_time, 4)
            error_msg = f"Task execution timed out after {effective_timeout}s"
            predictable_content = f"Model generation failed: {error_msg}"
            error_msg_chat = ChatMessage(role="assistant", content=predictable_content)
            state = AgentState(
                task_id=resolved_task_id,
                user_request=user_request,
                user_prompt=user_request,
                plan=["generate_response"],
                messages=[*initial_messages, error_msg_chat],
                images=resolved_images,
                documents=resolved_documents,
                selected_model=None,
                final_response=predictable_content,
                errors=[error_msg],
                provider=None,
                fallback_used=False,
                attempted_models=[],
                status="failed",
                execution_duration=execution_duration,
                step_count=0,
            )
            model_response = ModelResponse(
                content=predictable_content,
                model_id="timeout",
                raw={"error": error_msg},
            )
            return state, model_response
        except StepLimitExceededError as exc:
            execution_duration = round(time.perf_counter() - start_time, 4)
            error_msg = str(exc)
            predictable_content = f"Model generation failed: {error_msg}"
            error_msg_chat = ChatMessage(role="assistant", content=predictable_content)
            state = AgentState(
                task_id=resolved_task_id,
                user_request=user_request,
                user_prompt=user_request,
                plan=["generate_response"],
                messages=[*initial_messages, error_msg_chat],
                images=resolved_images,
                documents=resolved_documents,
                selected_model=None,
                final_response=predictable_content,
                errors=[error_msg],
                provider=None,
                fallback_used=False,
                attempted_models=[],
                status="failed",
                execution_duration=execution_duration,
                step_count=effective_max_steps,
            )
            model_response = ModelResponse(
                content=predictable_content,
                model_id="step_limit_exceeded",
                raw={"error": error_msg},
            )
            return state, model_response
        except InfiniteLoopError as exc:
            execution_duration = round(time.perf_counter() - start_time, 4)
            error_msg = str(exc)
            predictable_content = f"Model generation failed: {error_msg}"
            error_msg_chat = ChatMessage(role="assistant", content=predictable_content)
            state = AgentState(
                task_id=resolved_task_id,
                user_request=user_request,
                user_prompt=user_request,
                plan=["generate_response"],
                messages=[*initial_messages, error_msg_chat],
                images=resolved_images,
                documents=resolved_documents,
                selected_model=None,
                final_response=predictable_content,
                errors=[error_msg],
                provider=None,
                fallback_used=False,
                attempted_models=[],
                status="failed",
                execution_duration=execution_duration,
                step_count=effective_max_steps,
            )
            model_response = ModelResponse(
                content=predictable_content,
                model_id="infinite_loop",
                raw={"error": error_msg},
            )
            return state, model_response

        execution_duration = round(time.perf_counter() - start_time, 4)

        model_response = result.get("model_response")
        assert model_response is not None

        status = result.get("status")
        if not status:
            is_failure = result.get("provider") is None and bool(result.get("errors"))
            status = "failed" if is_failure else "completed"

        state = AgentState(
            task_id=result["task_id"],
            user_request=result["user_prompt"],
            user_prompt=result["user_prompt"],
            plan=["generate_response"],
            messages=result["messages"],
            images=result.get("images", []),
            documents=result.get("documents", []),
            selected_model=result["selected_model"],
            final_response=result["final_response"],
            errors=result["errors"],
            provider=result["provider"],
            fallback_used=result["fallback_used"],
            attempted_models=result["attempted_models"],
            approval_required=result.get("approval_required", False),
            approval_requests=result.get("approval_requests", []),
            status=status,
            execution_duration=execution_duration,
            step_count=result.get("step_count", 0),
            tool_results=[
                {
                    "tool": tool_result.name,
                    "success": tool_result.success,
                    "output": tool_result.output,
                    "error": tool_result.error,
                    "artifacts": tool_result.artifacts,
                    "id": tool_result.id,
                }
                for tool_result in result.get("tool_results", [])
            ],
            artifacts=[
                artifact
                for tool_result in result.get("tool_results", [])
                for artifact in tool_result.artifacts
            ],
        )
        return state, model_response

    @staticmethod
    def _validate_attachments(values: list[str] | None, field_name: str) -> list[str]:
        """Normalize optional encoded attachments before they enter graph state."""
        if values is None:
            return []
        if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
            raise StateValidationError(f"Field '{field_name}' must be a list of non-empty strings")
        return list(values)

    def _effective_tool_allowlist(self, user_allowlist: set[str] | None) -> set[str] | None:
        """Combine the agent-level and caller-level scopes without allowing escalation."""
        agent_allowlist = self.config.tool_allowlist
        if agent_allowlist is None:
            return set(user_allowlist) if user_allowlist is not None else None
        if user_allowlist is None:
            return set(agent_allowlist)
        return set(agent_allowlist).intersection(user_allowlist)

    def _track_step(self, state: AgentGraphState, node_name: str) -> tuple[int, list[str]]:
        """Increment step count, update history, and check limits and loops."""
        step_count = state.get("step_count", 0) + 1
        max_steps = state.get("max_steps", self.config.max_steps)
        if step_count > max_steps:
            raise StepLimitExceededError(f"Maximum workflow steps ({max_steps}) exceeded")

        node_history = [*state.get("node_history", []), node_name]
        if detect_cycle(node_history):
            raise InfiniteLoopError("Infinite loop detected: recurring execution cycle")

        return step_count, node_history

    async def _validate_input(self, state: AgentGraphState) -> dict[str, Any]:
        """Validate input state fields inside the graph workflow and transition to running."""
        step_count, node_history = self._track_step(state, "validate_input")
        validate_state(state, require_model=False)
        streamer: AgentEventStreamer | None = state.get("streamer")
        if streamer is not None:
            streamer.emit_thought("Selecting model and preparing request...")
        return {
            "status": "running",
            "step_count": step_count,
            "node_history": node_history,
        }

    async def _validate_output(self, state: AgentGraphState) -> dict[str, Any]:
        """Validate output state fields including selected_model."""
        step_count, node_history = self._track_step(state, "validate_output")
        validate_state(state, require_model=True)
        streamer: AgentEventStreamer | None = state.get("streamer")
        if streamer is not None:
            streamer.emit_thought("Finalizing response...")
        return {
            "step_count": step_count,
            "node_history": node_history,
        }

    async def _generate_response(self, state: AgentGraphState) -> dict[str, Any]:
        """Route and generate through the existing provider abstraction with retry limits."""
        step_count, node_history = self._track_step(state, "generate_response")
        streamer: AgentEventStreamer | None = state.get("streamer")
        if streamer is not None:
            streamer.emit_thought("Generating response...")

        model_request = ModelRequest(
            prompt=self._model_prompt(state),
            messages=self._build_request_messages(state),
            required_capabilities=state["required_capabilities"],
            required_modality=state["modality"],
            images=state.get("images", []),
            documents=state.get("documents", []),
            tools=self._tool_schemas(state.get("tool_allowlist")),
            tool_results=state.get("tool_results", []),
        )
        candidates = self.router.candidates(model_request)
        if not candidates:
            # Preserve the router's established public error for this case.
            self.router.select(model_request)

        last_error: ProviderError | None = None
        attempted_models = list(state.get("attempted_models") or [])
        errors = list(state.get("errors") or [])
        max_retries = state.get("max_retries", self.config.max_retries)

        retries_used = 0
        for i, model in enumerate(candidates):
            if i > 0:
                if retries_used >= max_retries:
                    errors.append(f"Provider retry limit ({max_retries}) reached")
                    break
                retries_used += 1

            attempted_models.append(model.id)
            try:
                if streamer is not None:
                    # Stream tokens directly to SSE and accumulate
                    accumulated = ""
                    async for token in self.providers.stream_generate(model, model_request):
                        accumulated += token
                        streamer.emit_content_delta(token)
                    if model_request.tools:
                        response = await self.providers.generate(model, model_request)
                    else:
                        response = ModelResponse(content=accumulated, model_id=model.id)
                else:
                    response, tool_results, approval_requests = await self._generate_with_tools(model, model_request, state)
                    final_content = response.content.strip() or "Task execution completed."
                    return {
                        "selected_model": model.id,
                        "provider": model.runtime,
                        "fallback_used": len(attempted_models) > 1,
                        "attempted_models": attempted_models,
                        "messages": [*state["messages"], ChatMessage(role="assistant", content=final_content)],
                        "final_response": final_content,
                        "errors": errors,
                        "model_response": response,
                        "tool_results": tool_results,
                        "approval_required": bool(approval_requests),
                        "approval_requests": approval_requests,
                        "status": "awaiting_approval" if approval_requests else "completed",
                        "step_count": step_count,
                        "node_history": node_history,
                    }
            except ProviderRequestError:
                # A malformed request must not be retried against another model.
                raise
            except ProviderError as error:
                last_error = error
                errors.append(str(error))
                continue

            # For streaming path without tools, we need to handle the response
            if streamer is not None and not model_request.tools:
                final_content = response.content.strip() or "Task execution completed."
                return {
                    "selected_model": model.id,
                    "provider": model.runtime,
                    "fallback_used": len(attempted_models) > 1,
                    "attempted_models": attempted_models,
                    "messages": [*state["messages"], ChatMessage(role="assistant", content=final_content)],
                    "final_response": final_content,
                    "errors": errors,
                    "model_response": response,
                    "tool_results": [],
                    "approval_required": False,
                    "approval_requests": [],
                    "status": "completed",
                    "step_count": step_count,
                    "node_history": node_history,
                }
            elif streamer is not None and model_request.tools:
                # Tools case: fall through to _generate_with_tools
                response, tool_results, approval_requests = await self._generate_with_tools(model, model_request, state)
                final_content = response.content.strip() or "Task execution completed."
                return {
                    "selected_model": model.id,
                    "provider": model.runtime,
                    "fallback_used": len(attempted_models) > 1,
                    "attempted_models": attempted_models,
                    "messages": [*state["messages"], ChatMessage(role="assistant", content=final_content)],
                    "final_response": final_content,
                    "errors": errors,
                    "model_response": response,
                    "tool_results": tool_results,
                    "approval_required": bool(approval_requests),
                    "approval_requests": approval_requests,
                    "status": "awaiting_approval" if approval_requests else "completed",
                    "step_count": step_count,
                    "node_history": node_history,
                }

        # If all candidates fail or retry limit reached:
        # Capture errors in the errors field and return a predictable failure response
        assert last_error is not None
        predictable_response = f"Model generation failed: {last_error}"
        failed_model_id = attempted_models[-1] if attempted_models else candidates[0].id
        fallback_used = len(attempted_models) > 1
        model_response = ModelResponse(
            content=predictable_response,
            model_id=failed_model_id,
            raw={"error": str(last_error), "errors": errors},
        )
        return {
            "selected_model": failed_model_id,
            "provider": None,
            "fallback_used": fallback_used,
            "attempted_models": attempted_models,
            "messages": [*state["messages"], ChatMessage(role="assistant", content=predictable_response)],
            "final_response": predictable_response,
            "errors": errors,
            "model_response": model_response,
            "status": "failed",
            "step_count": step_count,
            "node_history": node_history,
        }

    @staticmethod
    def _build_request_messages(state: AgentGraphState) -> list[ChatMessage]:
        """Convert graph state messages to ModelRequest ChatMessage list."""
        msgs = state.get("messages", [])
        if not msgs:
            return []
        result: list[ChatMessage] = []
        for m in msgs:
            if isinstance(m, ChatMessage):
                result.append(m)
            elif hasattr(m, "role") and hasattr(m, "content"):
                result.append(ChatMessage(role=m.role, content=m.content, images=getattr(m, "images", []) or []))
            elif isinstance(m, dict):
                result.append(ChatMessage(role=m.get("role", "user"), content=m.get("content", ""), images=m.get("images", []) or []))
        return result

    async def _generate_with_tools(
        self,
        model: Any,
        initial_request: ModelRequest,
        state: AgentGraphState,
    ) -> tuple[ModelResponse, list[ToolExecutionResult], list[dict[str, Any]]]:
        request = initial_request
        tool_results = list(state.get("tool_results", []))
        approval_requests = list(state.get("approval_requests", []))
        response = await self.providers.generate(model, request)

        for _ in range(self.config.max_tool_rounds):
            tool_calls = self._detect_tool_calls(response)
            if not tool_calls:
                return response, tool_results, approval_requests

            round_results = [await self._execute_tool_call_with_events(tool_call, state) for tool_call in tool_calls]
            tool_results.extend(round_results)
            approval_requests.extend(
                self._approval_request(tool_call, result)
                for tool_call, result in zip(tool_calls, round_results)
                if self._requires_approval(result)
            )
            request = ModelRequest(
                prompt=self._prompt_with_tool_results(self._model_prompt(state), response, round_results),
                messages=self._build_request_messages(state),
                required_capabilities=initial_request.required_capabilities,
                required_modality=initial_request.required_modality,
                images=initial_request.images,
                documents=initial_request.documents,
                tools=initial_request.tools,
                tool_results=tool_results,
            )
            response = await self.providers.generate(model, request)

        raise ProviderError(f"Maximum tool rounds ({self.config.max_tool_rounds}) exceeded")

    @staticmethod
    def _model_prompt(state: AgentGraphState) -> str:
        """Put the configured agent instruction ahead of the unmodified user request."""
        system_prompt = state.get("system_prompt")
        if not system_prompt:
            return state["user_prompt"]
        return f"System instructions:\n{system_prompt}\n\nUser request:\n{state['user_prompt']}"

    def _detect_tool_calls(self, response: ModelResponse) -> list[ToolCall]:
        if response.tool_calls:
            return response.tool_calls

        raw_tool_calls = response.raw.get("tool_calls")
        if isinstance(raw_tool_calls, list):
            return [call for item in raw_tool_calls if (call := self._coerce_tool_call(item))]

        stripped = response.content.strip()
        if not stripped:
            return []
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, dict) and "tool_calls" in payload and isinstance(payload["tool_calls"], list):
            return [call for item in payload["tool_calls"] if (call := self._coerce_tool_call(item))]
        if isinstance(payload, dict) and ("tool" in payload or "name" in payload):
            call = self._coerce_tool_call(payload)
            return [call] if call else []
        return []

    def _coerce_tool_call(self, item: Any) -> ToolCall | None:
        if isinstance(item, ToolCall):
            return item
        if not isinstance(item, dict):
            return None
        name = item.get("name") or item.get("tool")
        arguments = item.get("arguments") or item.get("args") or {}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                return None
        if not isinstance(name, str) or not name.strip() or not isinstance(arguments, dict):
            return None
        call_id = item.get("id") if isinstance(item.get("id"), str) else None
        return ToolCall(name=name.strip(), arguments=arguments, id=call_id)

    async def _execute_tool_call_with_events(
        self,
        tool_call: ToolCall,
        state: AgentGraphState,
    ) -> ToolExecutionResult:
        """Wrapper around _execute_tool_call that emits SSE events before/after execution."""
        import time as _time
        streamer: AgentEventStreamer | None = state.get("streamer")
        tool_descriptions = {
            "sandbox.execute": "Executing Python code in isolated Docker sandbox",
            "rag.search": "Searching knowledge base for relevant context",
            "vision.analyze": "Analyzing image or document with vision model",
            "artifact.document.create": "Creating Word document",
            "artifact.presentation.create": "Generating PowerPoint presentation with python-pptx",
            "artifact.pdf.create": "Generating PDF document with ReportLab",
            "artifact.spreadsheet.create": "Creating Excel spreadsheet",
            "artifact.validate": "Validating generated artifact",
        }
        description = tool_descriptions.get(tool_call.name, f"Running {tool_call.name}")
        if streamer is not None:
            streamer.emit_tool_call_start(tool_call.name, description)
        t0 = _time.perf_counter()
        result = await self._execute_tool_call(tool_call, state)
        duration_ms = round((_time.perf_counter() - t0) * 1000, 1)
        if streamer is not None:
            # Emit artifact event when a tool produces file artifacts
            if result.success and result.artifacts:
                for artifact_path in result.artifacts:
                    from pathlib import Path as _Path
                    p = _Path(artifact_path)
                    size = p.stat().st_size if p.exists() else 0
                    ext = p.suffix.lstrip(".").lower()
                    streamer.emit_artifact_ready(
                        name=p.name,
                        file_type=ext,
                        size_bytes=size,
                        download_url=f"/api/v1/artifacts/{p.name}/download",
                    )
            streamer.emit_tool_call_end(
                tool=tool_call.name,
                success=result.success,
                duration_ms=duration_ms,
                summary=result.error if not result.success else None,
            )
        return result

    async def _execute_tool_call(self, tool_call: ToolCall, state: AgentGraphState) -> ToolExecutionResult:
        if self.tools is None:
            return ToolExecutionResult(
                name=tool_call.name,
                success=False,
                output=None,
                error="No tool registry is configured for this runtime.",
                id=tool_call.id,
            )
        try:
            tool = self.tools.get(tool_call.name)
        except KeyError:
            return ToolExecutionResult(
                name=tool_call.name,
                success=False,
                output=None,
                error=f"Tool '{tool_call.name}' is not registered.",
                id=tool_call.id,
            )

        allowed_tools = state.get("tool_allowlist")
        if allowed_tools is not None and tool_call.name not in allowed_tools:
            return ToolExecutionResult(
                name=tool_call.name,
                success=False,
                output=None,
                error=f"Tool '{tool_call.name}' is not allowed for this agent or user.",
                id=tool_call.id,
            )

        decision = self.policy.evaluate(tool_call.name)
        if decision is PolicyDecision.DENY:
            return ToolExecutionResult(
                name=tool_call.name,
                success=False,
                output=None,
                error=f"Tool '{tool_call.name}' is blocked by safety policy.",
                id=tool_call.id,
            )
        if decision is PolicyDecision.REQUIRE_APPROVAL and tool_call.name not in state.get("approved_tools", set()):
            return ToolExecutionResult(
                name=tool_call.name,
                success=False,
                output={"approval_required": True, "tool": tool_call.name},
                error=f"Tool '{tool_call.name}' requires human approval.",
                id=tool_call.id,
            )

        validation_error = self._validate_tool_arguments(tool_call.arguments, getattr(tool, "parameters", {}))
        if validation_error:
            return ToolExecutionResult(
                name=tool_call.name,
                success=False,
                output=None,
                error=validation_error,
                id=tool_call.id,
            )

        try:
            context = {
                "task_id": state["task_id"],
                "tool_results": state.get("tool_results", []),
                "retrieved_context": [],
            }
            tool_call_task = tool.execute(tool_call.arguments, context=context)
            if self.config.tool_timeout > 0:
                result = await asyncio.wait_for(tool_call_task, timeout=self.config.tool_timeout)
            else:
                result = await tool_call_task
        except (TimeoutError, asyncio.TimeoutError):
            return ToolExecutionResult(
                name=tool_call.name,
                success=False,
                output=None,
                error=f"Tool '{tool_call.name}' timed out after {self.config.tool_timeout}s.",
                id=tool_call.id,
            )
        except Exception as error:
            detail = str(error) or type(error).__name__
            return ToolExecutionResult(
                name=tool_call.name,
                success=False,
                output=None,
                error=f"Tool '{tool_call.name}' execution failed: {detail}",
                id=tool_call.id,
            )

        return self._normalize_tool_result(tool_call, result)

    def _normalize_tool_result(self, tool_call: ToolCall, result: Any) -> ToolExecutionResult:
        """Convert a tool return value into the result contract used by models."""
        if not isinstance(result, ToolResult):
            return self._invalid_tool_result(tool_call, "expected a ToolResult instance")
        if not isinstance(result.success, bool):
            return self._invalid_tool_result(tool_call, "field 'success' must be a boolean")
        if result.error is not None and not isinstance(result.error, str):
            return self._invalid_tool_result(tool_call, "field 'error' must be a string or null")
        if not isinstance(result.artifacts, list) or any(not isinstance(item, str) for item in result.artifacts):
            return self._invalid_tool_result(tool_call, "field 'artifacts' must be a list of strings")

        return ToolExecutionResult(
            name=tool_call.name,
            success=result.success,
            output=result.output,
            error=result.error,
            artifacts=result.artifacts,
            id=tool_call.id,
        )

    def _invalid_tool_result(self, tool_call: ToolCall, reason: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            name=tool_call.name,
            success=False,
            output=None,
            error=f"Tool '{tool_call.name}' returned an invalid result: {reason}.",
            id=tool_call.id,
        )

    def _requires_approval(self, result: ToolExecutionResult) -> bool:
        return bool(isinstance(result.output, dict) and result.output.get("approval_required") is True)

    def _approval_request(self, tool_call: ToolCall, result: ToolExecutionResult) -> dict[str, Any]:
        """Structured approval hook for an API or UI to present to a human later."""
        return {
            "tool": tool_call.name,
            "arguments": tool_call.arguments,
            "tool_call_id": tool_call.id,
            "reason": result.error,
        }

    def _validate_tool_arguments(self, arguments: dict[str, Any], schema: dict[str, Any]) -> str | None:
        required = schema.get("required", []) if isinstance(schema, dict) else []
        for field in required:
            if field not in arguments:
                return f"Tool argument '{field}' is required."

        properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
        for field, value in arguments.items():
            expected = properties.get(field, {}).get("type") if isinstance(properties.get(field), dict) else None
            if expected and not self._matches_json_type(value, expected):
                return f"Tool argument '{field}' must be of type {expected}."
        return None

    def _matches_json_type(self, value: Any, expected: str) -> bool:
        if expected == "string":
            return isinstance(value, str)
        if expected == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if expected == "boolean":
            return isinstance(value, bool)
        if expected == "array":
            return isinstance(value, list)
        if expected == "object":
            return isinstance(value, dict)
        return True

    def _tool_schemas(self, allowlist: set[str] | None = None) -> list[dict[str, Any]]:
        if self.tools is None:
            return []
        return [
            {
                "name": tool.name,
                "description": getattr(tool, "description", ""),
                "parameters": getattr(tool, "parameters", {}),
            }
            for tool in (self.tools.get(name) for name in self.tools.names())
            if allowlist is None or tool.name in allowlist
        ]

    def _prompt_with_tool_results(
        self,
        original_prompt: str,
        response: ModelResponse,
        round_results: list[ToolExecutionResult],
    ) -> str:
        payload = [
            {
                "tool": result.name,
                "success": result.success,
                "output": result.output,
                "error": result.error,
                "artifacts": result.artifacts,
                "id": result.id,
            }
            for result in round_results
        ]
        return (
            f"{original_prompt}\n\n"
            f"Assistant requested tool calls: {response.content}\n\n"
            "Tool results:\n"
            f"{json.dumps(payload, default=str)}\n\n"
            "Use the tool results above to produce the final answer. "
            "If a tool failed, explain the failure clearly."
        )
