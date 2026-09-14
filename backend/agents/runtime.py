import uuid
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.state import AgentState
from backend.models.contracts import ModelRequest, ModelResponse
from backend.models.providers import ModelProviderRegistry, ProviderError, ProviderRequestError
from backend.models.router import ModelRouter


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


class AgentRuntime:
    """Minimal LangGraph orchestration over the model routing boundary."""

    def __init__(self, router: ModelRouter, providers: ModelProviderRegistry):
        self.router = router
        self.providers = providers
        workflow = StateGraph(AgentGraphState)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_edge(START, "generate_response")
        workflow.add_edge("generate_response", END)
        self.graph = workflow.compile()

    async def run(self, user_request: str, capabilities: set[str], modality: str = "text") -> tuple[AgentState, ModelResponse]:
        """Run START -> generate_response -> END for one task."""
        result = await self.graph.ainvoke(
            {
                "task_id": str(uuid.uuid4()),
                "user_prompt": user_request,
                "selected_model": None,
                "messages": [user_request],
                "final_response": None,
                "errors": [],
                "attempted_models": [],
                "provider": None,
                "fallback_used": False,
                "model_response": None,
                "required_capabilities": capabilities,
                "modality": modality,
            }
        )
        model_response = result["model_response"]
        assert model_response is not None
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
            status="completed",
        )
        return state, model_response

    async def _generate_response(self, state: AgentGraphState) -> dict:
        """Route and generate through the existing provider abstraction only."""
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
        attempted_models = list(state["attempted_models"])
        errors = list(state["errors"])
        for model in candidates:
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
            }

        assert last_error is not None
        raise last_error
