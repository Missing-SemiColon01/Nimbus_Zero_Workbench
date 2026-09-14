from dataclasses import dataclass, field


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

    def __post_init__(self) -> None:
        if self.user_prompt is None:
            self.user_prompt = self.user_request
