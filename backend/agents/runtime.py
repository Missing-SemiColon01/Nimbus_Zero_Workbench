import uuid

from backend.agents.state import AgentState
from backend.models.contracts import ModelRequest, ModelResponse
from backend.models.providers import ModelProviderRegistry, ProviderError, ProviderRequestError
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
        state = AgentState(task_id=str(uuid.uuid4()), user_request=user_request, status="planning")
        state.plan = ["classify_task", "select_model", "execute", "validate"]
        candidates = self.router.candidates(model_request)
        if not candidates:
            # Preserve the router's established public error for this case.
            self.router.select(model_request)

        last_error: ProviderError | None = None
        for model in candidates:
            state.attempted_models.append(model.id)
            try:
                response = await self.providers.generate(model, model_request)
            except ProviderRequestError:
                # A malformed request must not be retried against another model.
                raise
            except ProviderError as error:
                last_error = error
                continue

            state.selected_model = model.id
            state.provider = model.runtime
            state.fallback_used = len(state.attempted_models) > 1
            state.status = "completed"
            return state, response

        assert last_error is not None
        raise last_error
