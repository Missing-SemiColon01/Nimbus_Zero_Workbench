from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any



class StateValidationError(ValueError):
    """Raised when an agent state has missing or invalid fields."""

    pass


class WorkflowTimeoutError(RuntimeError):
    """Raised or captured when workflow execution exceeds the configured timeout."""

    pass


class StepLimitExceededError(RuntimeError):
    """Raised or captured when workflow execution exceeds maximum allowed steps."""

    pass


class InfiniteLoopError(RuntimeError):
    """Raised or captured when an infinite loop is detected in the workflow."""

    pass



def validate_state(
    state: Mapping[str, Any] | "AgentState",
    require_model: bool = False,
) -> None:
    """Validate required fields: task_id, user_prompt, messages, and selected_model.

    Parameters
    ----------
    state:
        AgentState instance or dictionary (e.g. AgentGraphState).
    require_model:
        If True, selected_model must be a non-empty string.
        If False, selected_model can be None, but if provided, must be a non-empty string.
    """
    if isinstance(state, AgentState):
        task_id = state.task_id
        user_prompt = state.user_prompt or state.user_request
        messages = state.messages
        selected_model = state.selected_model
    elif isinstance(state, Mapping):
        if "task_id" not in state or state["task_id"] is None:
            raise StateValidationError("State missing required field: 'task_id'")
        task_id = state["task_id"]

        user_prompt = state.get("user_prompt")
        if user_prompt is None:
            user_prompt = state.get("user_request")
        if user_prompt is None:
            raise StateValidationError("State missing required field: 'user_prompt'")

        if "messages" not in state or state["messages"] is None:
            raise StateValidationError("State missing required field: 'messages'")
        messages = state["messages"]
        selected_model = state.get("selected_model")
    else:
        raise StateValidationError(f"Invalid state object type: {type(state).__name__}")

    if not isinstance(task_id, str) or not task_id.strip():
        raise StateValidationError("Field 'task_id' must be a non-empty string")

    if not isinstance(user_prompt, str) or not user_prompt.strip():
        raise StateValidationError("Field 'user_prompt' must be a non-empty string")

    if not isinstance(messages, list) or len(messages) == 0:
        raise StateValidationError("Field 'messages' must be a non-empty list of strings")

    for i, msg in enumerate(messages):
        if not isinstance(msg, str) or not msg.strip():
            raise StateValidationError(f"Field 'messages[{i}]' must be a non-empty string")

    if require_model:
        if selected_model is None or not isinstance(selected_model, str) or not selected_model.strip():
            raise StateValidationError("Field 'selected_model' must be a non-empty string")
    elif selected_model is not None:
        if not isinstance(selected_model, str) or not selected_model.strip():
            raise StateValidationError("Field 'selected_model' must be a non-empty string if provided")


@dataclass
class AgentState:
    task_id: str
    user_request: str
    # ``user_request`` remains for the existing tool-facing state contract.
    # ``user_prompt`` is the name used by the LangGraph workflow state.
    user_prompt: str | None = None
    plan: list[str] = field(default_factory=list)
    current_step: int = 0
    messages: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    retrieved_context: list[dict] = field(default_factory=list)
    selected_model: str | None = None
    final_response: str | None = None
    errors: list[str] = field(default_factory=list)
    provider: str | None = None
    fallback_used: bool = False
    attempted_models: list[str] = field(default_factory=list)
    approval_required: bool = False
    status: str = "queued"
    execution_duration: float | None = None
    step_count: int = 0



    def __post_init__(self) -> None:
        if self.user_prompt is None:
            self.user_prompt = self.user_request

    def validate(self, require_model: bool = False) -> None:
        validate_state(self, require_model=require_model)
