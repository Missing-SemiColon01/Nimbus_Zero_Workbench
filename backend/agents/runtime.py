import uuid

from backend.agents.state import AgentState
from backend.models.contracts import ModelRequest
from backend.models.router import ModelRouter


class AgentRuntime:
    """Orchestration seam ready to be backed by LangGraph."""
    def __init__(self, router: ModelRouter):
        self.router = router

    def begin(self, user_request: str, capabilities: set[str], modality: str = "text") -> AgentState:
        state = AgentState(task_id=str(uuid.uuid4()), user_request=user_request, status="planning")
        state.plan = ["classify_task", "select_model", "execute", "validate"]
        state.selected_model = self.router.select(ModelRequest(prompt=user_request, required_capabilities=capabilities, required_modality=modality)).id
        state.status = "ready"
        return state
