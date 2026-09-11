from dataclasses import dataclass, field


@dataclass
class AgentState:
    task_id: str
    user_request: str
    plan: list[str] = field(default_factory=list)
    current_step: int = 0
    messages: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    retrieved_context: list[dict] = field(default_factory=list)
    selected_model: str | None = None
    approval_required: bool = False
    status: str = "queued"
