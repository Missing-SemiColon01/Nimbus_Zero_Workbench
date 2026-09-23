from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import re
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
    timeout: float = 180.0
    tool_timeout: float = 60.0
    tool_allowlist: frozenset[str] | None = None
    max_retries: int = 2
    max_steps: int = 15
    max_tool_rounds: int = 3


def detect_cycle(history: list[str], min_repetitions: int = 4) -> bool:
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
    tool_round: int
    pending_tool_calls: list[ToolCall]


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
        workflow.add_node("execute_tools", self._execute_tools)
        workflow.add_node("validate_output", self._validate_output)

        workflow.add_edge(START, "validate_input")
        workflow.add_edge("validate_input", "generate_response")
        workflow.add_conditional_edges(
            "generate_response",
            self._route_after_generation,
            {
                "execute_tools": "execute_tools",
                "validate_output": "validate_output",
            },
        )
        workflow.add_edge("execute_tools", "generate_response")
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
                raw_tc = getattr(m, "tool_calls", []) or []
                coerced_tc = [
                    tc if isinstance(tc, ToolCall) else ToolCall(
                        name=tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", ""),
                        arguments=tc.get("arguments", {}) if isinstance(tc, dict) else getattr(tc, "arguments", {}),
                        id=tc.get("id", str(uuid.uuid4())) if isinstance(tc, dict) else getattr(tc, "id", str(uuid.uuid4())),
                    )
                    for tc in raw_tc
                ]
                initial_messages.append(ChatMessage(
                    role=m.role,
                    content=m.content,
                    images=getattr(m, "images", []) or [],
                    tool_calls=coerced_tc,
                ))
            elif isinstance(m, dict):
                raw_tc = m.get("tool_calls") or []
                coerced_tc = [
                    tc if isinstance(tc, ToolCall) else ToolCall(
                        name=tc.get("name", ""),
                        arguments=tc.get("arguments", {}),
                        id=tc.get("id", str(uuid.uuid4())),
                    )
                    for tc in raw_tc if isinstance(tc, (dict, ToolCall))
                ]
                initial_messages.append(ChatMessage(
                    role=m.get("role", "user"),
                    content=m.get("content", ""),
                    images=m.get("images", []) or [],
                    tool_calls=coerced_tc,
                ))
        if user_msg is not None:
            initial_messages.append(user_msg)

        if system_prompt and isinstance(system_prompt, str) and system_prompt.strip():
            clean_sys = system_prompt.strip()
            has_system = any(
                (m.role == "system" if isinstance(m, ChatMessage) else getattr(m, "role", "") == "system")
                for m in initial_messages
            )
            if not has_system:
                initial_messages.insert(0, ChatMessage(role="system", content=clean_sys))
        resolved_images = self._validate_attachments(images, "images")
        resolved_documents = self._validate_attachments(documents, "documents")
        resolved_capabilities = set(capabilities)
        resolved_modality = modality
        effective_tool_allowlist = self._effective_tool_allowlist(tool_allowlist)

        has_vision_tool = bool(
            self.tools and "vision.analyze" in self.tools.names()
            and (effective_tool_allowlist is None or "vision.analyze" in effective_tool_allowlist)
        )
        if resolved_images:
            if not has_vision_tool or modality == "image":
                resolved_capabilities.add("vision")
                resolved_modality = "image"
            else:
                # Orchestrator-Worker pattern: Top-level agent is text reasoning model
                # that delegates image analysis to vision.analyze tool
                resolved_capabilities.add("reasoning")
                resolved_modality = "text"
        if resolved_documents:
            resolved_capabilities.add("document_understanding")
            # Image-capable document models commonly handle both inputs. A
            # document-only request uses the explicit document modality.
            if not resolved_images:
                resolved_modality = "document"

        effective_timeout = timeout if timeout is not None else self.config.timeout
        effective_max_retries = max_retries if max_retries is not None else self.config.max_retries
        effective_max_steps = max_steps if max_steps is not None else self.config.max_steps

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
            "tool_round": 0,
            "pending_tool_calls": [],
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

    def _route_after_generation(self, state: AgentGraphState) -> str:
        """Route to execute_tools if pending tool calls exist, else validate_output."""
        if state.get("status") == "failed":
            return "validate_output"
        if state.get("approval_required") or bool(state.get("approval_requests")):
            return "validate_output"
        pending = state.get("pending_tool_calls") or []
        tool_round = state.get("tool_round", 0)
        max_tool_rounds = state.get("max_tool_rounds", self.config.max_tool_rounds)
        if pending and tool_round < max_tool_rounds:
            return "execute_tools"
        return "validate_output"

    async def _execute_tools(self, state: AgentGraphState) -> dict[str, Any]:
        """Execute pending tool calls from the model turn and accumulate results."""
        step_count, node_history = self._track_step(state, "execute_tools")
        pending = list(state.get("pending_tool_calls") or [])
        tool_round = state.get("tool_round", 0) + 1
        streamer: AgentEventStreamer | None = state.get("streamer")

        round_results = [await self._execute_tool_call_with_events(tool_call, state) for tool_call in pending]
        tool_results = [*state.get("tool_results", []), *round_results]

        approval_requests = list(state.get("approval_requests", []))
        approval_requests.extend(
            self._approval_request(tool_call, result)
            for tool_call, result in zip(pending, round_results)
            if self._requires_approval(result)
        )
        approval_required = bool(approval_requests)

        # Retain structured tool calls and tool outputs in conversational messages state (Audit Flaw 1.5)
        new_messages = list(state.get("messages", []))
        new_messages.append(ChatMessage(
            role="assistant",
            content=json.dumps([{"tool": tc.name, "arguments": tc.arguments} for tc in pending], default=str),
            tool_calls=pending,
        ))
        new_messages.append(ChatMessage(
            role="user",
            content=(
                f"Tool execution results:\n{json.dumps([r.output if r.success else r.error for r in round_results], default=str)}\n\n"
                "Use the tool results above to produce the final answer. If a tool failed, explain the failure clearly."
            ),
        ))

        if streamer is not None:
            streamer.emit_thought("Analyzing tool results and synthesizing response...")

        return {
            "step_count": step_count,
            "node_history": node_history,
            "tool_results": tool_results,
            "tool_round": tool_round,
            "pending_tool_calls": [],
            "approval_requests": approval_requests,
            "approval_required": approval_required,
            "messages": new_messages,
            "status": "awaiting_approval" if approval_required else "running",
        }

    async def _generate_response(self, state: AgentGraphState) -> dict[str, Any]:
        """Route and generate through the provider abstraction with streaming and tool detection."""
        step_count, node_history = self._track_step(state, "generate_response")
        streamer: AgentEventStreamer | None = state.get("streamer")
        tool_round = state.get("tool_round", 0)
        max_tool_rounds = state.get("max_tool_rounds", self.config.max_tool_rounds)
        is_max_rounds = tool_round >= max_tool_rounds

        if streamer is not None:
            if tool_round == 0:
                streamer.emit_thought("Generating response...")
            else:
                streamer.emit_thought("Synthesizing final response...")

        # If max tool rounds reached, strip tools and enforce final answer synthesis (Audit Flaw 1.4)
        if is_max_rounds:
            tools = []
            prompt = (
                f"{self._model_prompt(state)}\n\n"
                f"[Advisory]: Maximum tool rounds limit ({max_tool_rounds}) reached. "
                "Synthesize your best-effort final answer based strictly on the accumulated tool evidence. "
                "Clearly state any remaining uncertainties or incomplete inspections."
            )
        elif tool_round > 0 and state.get("tool_results"):
            # Tools have executed: strip tools to lift tool grammar constraints and stream the full synthesis
            tools = []
            last_resp = state.get("model_response") or ModelResponse(content="")
            prompt = self._prompt_with_tool_results(self._model_prompt(state), last_resp, state.get("tool_results", []))
        else:
            tools = self._tool_schemas(state.get("tool_allowlist"))
            prompt = self._model_prompt(state)

        model_request = ModelRequest(
            prompt=prompt,
            messages=self._build_request_messages(state),
            required_capabilities=state["required_capabilities"],
            required_modality=state["modality"],
            images=state.get("images", []),
            documents=state.get("documents", []),
            tools=tools,
            tool_results=state.get("tool_results", []),
        )
        candidates = self.router.candidates(model_request)
        if not candidates:
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
                # Case 1: No tools on request (conversational turn or forced final synthesis)
                if not model_request.tools:
                    if streamer is not None:
                        accumulated = ""
                        async for token in self.providers.stream_generate(model, model_request):
                            accumulated += token
                            streamer.emit_content_delta(token)
                        response = ModelResponse(content=accumulated, model_id=model.id)
                    else:
                        response = await self.providers.generate(model, model_request)

                    final_content = response.content.strip() or "Task execution completed."
                    return {
                        "selected_model": model.id,
                        "provider": model.runtime,
                        "fallback_used": len(attempted_models) > 1,
                        "attempted_models": attempted_models,
                        "messages": [*state.get("messages", []), ChatMessage(role="assistant", content=final_content)],
                        "final_response": final_content,
                        "errors": errors,
                        "model_response": response,
                        "pending_tool_calls": [],
                        "status": "completed",
                        "step_count": step_count,
                        "node_history": node_history,
                    }

                # Case 2: Tools available on request
                # Generate buffered first so tool JSON is NOT leaked to chat (Audit Flaw 1.2)
                response = await self.providers.generate(model, model_request)
                tool_calls = self._detect_tool_calls(response)

                if tool_calls:
                    # Model chose to call tools; do not stream JSON to chat UI
                    return {
                        "selected_model": model.id,
                        "provider": model.runtime,
                        "fallback_used": len(attempted_models) > 1,
                        "attempted_models": attempted_models,
                        "errors": errors,
                        "model_response": response,
                        "pending_tool_calls": tool_calls,
                        "status": "running",
                        "step_count": step_count,
                        "node_history": node_history,
                    }
                else:
                    # Model answered directly without invoking any tools
                    if streamer is not None and response.content:
                        for chunk in re.split(r"(\s+)", response.content):
                            if chunk:
                                streamer.emit_content_delta(chunk)

                    final_content = response.content.strip() or "Task execution completed."
                    return {
                        "selected_model": model.id,
                        "provider": model.runtime,
                        "fallback_used": len(attempted_models) > 1,
                        "attempted_models": attempted_models,
                        "messages": [*state.get("messages", []), ChatMessage(role="assistant", content=final_content)],
                        "final_response": final_content,
                        "errors": errors,
                        "model_response": response,
                        "pending_tool_calls": [],
                        "status": "completed",
                        "step_count": step_count,
                        "node_history": node_history,
                    }

            except ProviderRequestError:
                raise
            except ProviderError as error:
                last_error = error
                errors.append(str(error))
                continue

        # If all candidates fail or retry limit reached:
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
            "messages": [*state.get("messages", []), ChatMessage(role="assistant", content=predictable_response)],
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
        result: list[ChatMessage] = []

        system_prompt = state.get("system_prompt")
        has_system = any(
            (m.role == "system" if isinstance(m, ChatMessage) or (hasattr(m, "role") and not isinstance(m, dict)) else m.get("role") == "system")
            for m in msgs
        )
        if system_prompt and not has_system:
            result.append(ChatMessage(role="system", content=system_prompt.strip()))

        for m in msgs:
            if isinstance(m, ChatMessage):
                result.append(m)
            elif hasattr(m, "role") and hasattr(m, "content"):
                raw_tc = getattr(m, "tool_calls", []) or []
                coerced_tc = [
                    tc if isinstance(tc, ToolCall) else ToolCall(
                        name=tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", ""),
                        arguments=tc.get("arguments", {}) if isinstance(tc, dict) else getattr(tc, "arguments", {}),
                        id=tc.get("id", str(uuid.uuid4())) if isinstance(tc, dict) else getattr(tc, "id", str(uuid.uuid4())),
                    )
                    for tc in raw_tc
                ]
                result.append(ChatMessage(
                    role=m.role,
                    content=m.content,
                    images=getattr(m, "images", []) or [],
                    tool_calls=coerced_tc,
                ))
            elif isinstance(m, dict):
                raw_tc = m.get("tool_calls") or []
                coerced_tc = [
                    tc if isinstance(tc, ToolCall) else ToolCall(
                        name=tc.get("name", ""),
                        arguments=tc.get("arguments", {}),
                        id=tc.get("id", str(uuid.uuid4())),
                    )
                    for tc in raw_tc if isinstance(tc, (dict, ToolCall))
                ]
                result.append(ChatMessage(
                    role=m.get("role", "user"),
                    content=m.get("content", ""),
                    images=m.get("images", []) or [],
                    tool_calls=coerced_tc,
                ))
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
            tool_results_prompt = self._prompt_with_tool_results(self._model_prompt(state), response, round_results)
            round_messages = self._build_request_messages(state)
            round_messages.append(ChatMessage(role="assistant", content=response.content or "Calling tools..."))
            round_messages.append(ChatMessage(
                role="user",
                content=(
                    f"Tool execution results:\n{json.dumps([r.output if r.success else r.error for r in round_results], default=str)}\n\n"
                    "Use the tool results above to produce the final answer. If a tool failed, explain the failure clearly."
                ),
            ))
            request = ModelRequest(
                prompt=tool_results_prompt,
                messages=round_messages,
                required_capabilities=initial_request.required_capabilities,
                required_modality=initial_request.required_modality,
                images=initial_request.images,
                documents=initial_request.documents,
                tools=initial_request.tools,
                tool_results=tool_results,
            )
            response = await self.providers.generate(model, request)

        # Graceful Answer Synthesis on Max Tool Rounds Limit (Task 1.3 / Audit Flaw 1.4)
        final_prompt = (
            f"{self._model_prompt(state)}\n\n"
            f"[Advisory]: Maximum tool rounds limit ({self.config.max_tool_rounds}) reached. "
            "Synthesize your best-effort final answer based strictly on the accumulated tool results above. "
            "Clearly note any pending steps or unresolved questions as an advisory."
        )
        round_messages = self._build_request_messages(state)
        round_messages.append(ChatMessage(role="assistant", content=response.content or "Completed tool rounds."))
        round_messages.append(ChatMessage(
            role="user",
            content=(
                f"Accumulated tool execution results:\n{json.dumps([r.output if r.success else r.error for r in tool_results], default=str)}\n\n"
                "Maximum tool iteration rounds reached. Formulate your final response with all evidence collected."
            ),
        ))
        final_request = ModelRequest(
            prompt=final_prompt,
            messages=round_messages,
            required_capabilities=initial_request.required_capabilities,
            required_modality=initial_request.required_modality,
            images=initial_request.images,
            documents=initial_request.documents,
            tools=[],
            tool_results=tool_results,
        )
        final_response = await self.providers.generate(model, final_request)
        return final_response, tool_results, approval_requests

    @staticmethod
    def _model_prompt(state: AgentGraphState) -> str:
        """Put the configured agent instruction ahead of the unmodified user request."""
        system_prompt = state.get("system_prompt")
        if not system_prompt:
            return state["user_prompt"]
        return f"System instructions:\n{system_prompt}\n\nUser request:\n{state['user_prompt']}"

    @staticmethod
    def _strip_code_fences(content: str) -> str:
        """Strip markdown ```json ... ``` or ``` ... ``` code blocks if present (Audit Flaw 1.3)."""
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if match:
            return match.group(1).strip()
        return content.strip()

    def _detect_tool_calls(self, response: ModelResponse) -> list[ToolCall]:
        if response.tool_calls:
            valid = [c for call in response.tool_calls if (c := self._coerce_tool_call(call))]
            if valid:
                return valid

        raw_tool_calls = response.raw.get("tool_calls")
        if isinstance(raw_tool_calls, list):
            valid = [c for item in raw_tool_calls if (c := self._coerce_tool_call(item))]
            if valid:
                return valid

        cleaned = self._strip_code_fences(response.content)
        if not cleaned:
            return []
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback: extract the first complete { ... } or [ ... ] substring
            brace_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
            if brace_match:
                try:
                    payload = json.loads(brace_match.group(1))
                except json.JSONDecodeError:
                    return []
            else:
                return []

        if isinstance(payload, list):
            return [call for item in payload if (call := self._coerce_tool_call(item))]
        if isinstance(payload, dict) and "tool_calls" in payload and isinstance(payload["tool_calls"], list):
            return [call for item in payload["tool_calls"] if (call := self._coerce_tool_call(item))]
        if isinstance(payload, dict) and ("tool" in payload or "name" in payload):
            call = self._coerce_tool_call(payload)
            return [call] if call else []
        return []

    def _coerce_tool_call(self, item: Any) -> ToolCall | None:
        if isinstance(item, ToolCall):
            if self.tools is not None and item.name not in self.tools.names():
                return None
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
        name = name.strip()
        # Prevent false-positive tool detection from sample JSON or code written in the response:
        # A tool call MUST match a registered tool name when tools are configured.
        if self.tools is not None and name not in self.tools.names():
            return None
        call_id = item.get("id") if isinstance(item.get("id"), str) else None
        return ToolCall(name=name, arguments=arguments, id=call_id)

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
