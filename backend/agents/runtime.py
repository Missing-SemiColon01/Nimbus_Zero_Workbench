from __future__ import annotations

import asyncio
from dataclasses import dataclass
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
from backend.models.contracts import ModelRequest, ModelResponse
from backend.models.providers import ModelProviderRegistry, ProviderError, ProviderRequestError
from backend.models.router import ModelRouter


@dataclass(frozen=True)
class RuntimeConfig:
    timeout: float = 60.0
    max_retries: int = 2
    max_steps: int = 15


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
    selected_model: str | None
    messages: list[str]
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


class AgentRuntime:
    """Minimal LangGraph orchestration over the model routing boundary with reliability controls."""

    def __init__(
        self,
        router: ModelRouter,
        providers: ModelProviderRegistry,
        config: RuntimeConfig | None = None,
    ):
        self.router = router
        self.providers = providers
        self.config = config or RuntimeConfig()

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
        task_id: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        max_steps: int | None = None,
    ) -> tuple[AgentState, ModelResponse]:
        """Run the agent workflow for one task with reliability controls."""
        start_time = time.perf_counter()
        resolved_task_id = task_id or str(uuid.uuid4())
        initial_messages = [user_request] if isinstance(user_request, str) and user_request.strip() else []

        effective_timeout = timeout if timeout is not None else self.config.timeout
        effective_max_retries = max_retries if max_retries is not None else self.config.max_retries
        effective_max_steps = max_steps if max_steps is not None else self.config.max_steps

        initial_state: AgentGraphState = {
            "task_id": resolved_task_id,
            "user_prompt": user_request,
            "selected_model": None,
            "messages": initial_messages,
            "final_response": None,
            "errors": [],
            "attempted_models": [],
            "provider": None,
            "fallback_used": False,
            "model_response": None,
            "required_capabilities": capabilities,
            "modality": modality,
            "status": "queued",
            "execution_duration": None,
            "step_count": 0,
            "node_history": [],
            "max_retries": effective_max_retries,
            "max_steps": effective_max_steps,
        }

        # Pre-validate input state before invoking workflow
        validate_state(initial_state, require_model=False)

        try:
            if effective_timeout is not None and effective_timeout > 0:
                async with asyncio.timeout(effective_timeout):
                    result = await self.graph.ainvoke(
                        initial_state,
                        config={"recursion_limit": max(effective_max_steps * 2, 25)},
                    )
            else:
                result = await self.graph.ainvoke(
                    initial_state,
                    config={"recursion_limit": max(effective_max_steps * 2, 25)},
                )
        except (TimeoutError, asyncio.TimeoutError):
            execution_duration = round(time.perf_counter() - start_time, 4)
            error_msg = f"Task execution timed out after {effective_timeout}s"
            predictable_content = f"Model generation failed: {error_msg}"
            state = AgentState(
                task_id=resolved_task_id,
                user_request=user_request,
                user_prompt=user_request,
                plan=["generate_response"],
                messages=[*initial_messages, predictable_content],
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
            state = AgentState(
                task_id=resolved_task_id,
                user_request=user_request,
                user_prompt=user_request,
                plan=["generate_response"],
                messages=[*initial_messages, predictable_content],
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
            state = AgentState(
                task_id=resolved_task_id,
                user_request=user_request,
                user_prompt=user_request,
                plan=["generate_response"],
                messages=[*initial_messages, predictable_content],
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
            selected_model=result["selected_model"],
            final_response=result["final_response"],
            errors=result["errors"],
            provider=result["provider"],
            fallback_used=result["fallback_used"],
            attempted_models=result["attempted_models"],
            status=status,
            execution_duration=execution_duration,
            step_count=result.get("step_count", 0),
        )
        return state, model_response

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
        return {
            "status": "running",
            "step_count": step_count,
            "node_history": node_history,
        }

    async def _validate_output(self, state: AgentGraphState) -> dict[str, Any]:
        """Validate output state fields including selected_model."""
        step_count, node_history = self._track_step(state, "validate_output")
        validate_state(state, require_model=True)
        return {
            "step_count": step_count,
            "node_history": node_history,
        }

    async def _generate_response(self, state: AgentGraphState) -> dict[str, Any]:
        """Route and generate through the existing provider abstraction with retry limits."""
        step_count, node_history = self._track_step(state, "generate_response")

        model_request = ModelRequest(
            prompt=state["user_prompt"],
            required_capabilities=state["required_capabilities"],
            required_modality=state["modality"],
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
                response = await self.providers.generate(model, model_request)
            except ProviderRequestError:
                # A malformed request must not be retried against another model.
                raise
            except ProviderError as error:
                last_error = error
                errors.append(str(error))
                continue

            return {
                "selected_model": model.id,
                "provider": model.runtime,
                "fallback_used": len(attempted_models) > 1,
                "attempted_models": attempted_models,
                "messages": [*state["messages"], response.content],
                "final_response": response.content,
                "errors": errors,
                "model_response": response,
                "status": "completed",
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
            "messages": [*state["messages"], predictable_response],
            "final_response": predictable_response,
            "errors": errors,
            "model_response": model_response,
            "status": "failed",
            "step_count": step_count,
            "node_history": node_history,
        }



