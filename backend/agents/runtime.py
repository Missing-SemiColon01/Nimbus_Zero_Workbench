import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.state import AgentState, StateValidationError, validate_state
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
    ) -> tuple[AgentState, ModelResponse]:
        """Run the agent workflow for one task."""
        resolved_task_id = task_id or str(uuid.uuid4())
        initial_messages = [user_request] if isinstance(user_request, str) and user_request.strip() else []

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
        }

        # Pre-validate input state before invoking workflow
        validate_state(initial_state, require_model=False)

        result = await self.graph.ainvoke(initial_state)
        model_response = result.get("model_response")
        assert model_response is not None

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
        )
        return state, model_response

    async def _validate_input(self, state: AgentGraphState) -> dict[str, Any]:
        """Validate input state fields inside the graph workflow."""
        validate_state(state, require_model=False)
        return {}

    async def _validate_output(self, state: AgentGraphState) -> dict[str, Any]:
        """Validate output state fields including selected_model."""
        validate_state(state, require_model=True)
        return {}

    async def _generate_response(self, state: AgentGraphState) -> dict[str, Any]:
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
        attempted_models = list(state.get("attempted_models") or [])
        errors = list(state.get("errors") or [])
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

        # If all candidates fail:
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
        }

