import uuid

from backend.agents.state import AgentState
from backend.models.contracts import ModelRequest, ModelResponse
from backend.models.providers import ModelProviderRegistry
from backend.models.router import ModelRouter


class AgentRuntime:
    """Orchestration seam ready to be backed by LangGraph."""
    def __init__(self, router: ModelRouter, providers: ModelProviderRegistry):
        self.router = router
        self.providers = providers

    async def run(self, user_request: str, capabilities: set[str], modality: str = "text") -> tuple[AgentState, ModelResponse]:
        model_request = ModelRequest(
            prompt=user_request,
            required_capabilities=capabilities,
            required_modality=modality,
        )
        selected_model = self.router.select(model_request)
        state = AgentState(task_id=str(uuid.uuid4()), user_request=user_request, status="planning")
        state.plan = ["classify_task", "select_model", "execute", "validate"]
        state.selected_model = selected_model.id
        response = await self.providers.generate(selected_model, model_request)
        state.status = "completed"
        return state, response
