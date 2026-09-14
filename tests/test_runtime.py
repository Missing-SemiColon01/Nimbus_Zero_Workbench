import asyncio
from pathlib import Path

import pytest

from backend.agents.runtime import AgentRuntime
from backend.agents.state import StateValidationError, validate_state
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider, ModelProviderRegistry, ProviderError, ProviderRequestError
from backend.models.registry import ModelRegistry
from backend.models.router import ModelRouter


class FailingOverProvider(ModelProvider):
    def __init__(self, error: ProviderError):
        self.error = error
        self.calls: list[str] = []

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        self.calls.append(model.id)
        if model.id == "primary":
            raise self.error
        return ModelResponse(content="fallback response", model_id=model.id)


def runtime(tmp_path: Path, provider: ModelProvider) -> AgentRuntime:
    config = tmp_path / "models.yaml"
    config.write_text(
        """models:
  - id: primary
    runtime: fake
    model: primary
    capabilities: [reasoning]
    modalities: [text]
    priority: 10
  - id: backup
    runtime: fake
    model: backup
    capabilities: [reasoning]
    modalities: [text]
    priority: 1
"""
    )
    return AgentRuntime(ModelRouter(ModelRegistry(config)), ModelProviderRegistry({"fake": provider}))


def test_runtime_falls_back_after_provider_error(tmp_path: Path):
    provider = FailingOverProvider(ProviderError("network unavailable"))

    state, response = asyncio.run(runtime(tmp_path, provider).run("hello", {"reasoning"}))

    assert response.content == "fallback response"
    assert state.selected_model == "backup"
    assert state.provider == "fake"
    assert state.fallback_used is True
    assert state.attempted_models == ["primary", "backup"]
    assert state.user_prompt == "hello"
    assert state.final_response == "fallback response"
    assert state.messages == ["hello", "fallback response"]
    assert state.errors == ["network unavailable"]
    assert state.plan == ["generate_response"]
    assert provider.calls == ["primary", "backup"]


def test_runtime_does_not_fallback_after_invalid_request(tmp_path: Path):
    provider = FailingOverProvider(ProviderRequestError("malformed prompt"))

    try:
        asyncio.run(runtime(tmp_path, provider).run("hello", {"reasoning"}))
    except ProviderRequestError:
        pass
    else:
        raise AssertionError("Expected the invalid request error to be returned")

    assert provider.calls == ["primary"]


class SuccessProvider(ModelProvider):
    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content="successful response", model_id=model.id)


class AllFailingProvider(ModelProvider):
    def __init__(self, error: ProviderError):
        self.error = error
        self.calls: list[str] = []

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        self.calls.append(model.id)
        raise self.error


def test_runtime_successful_generation(tmp_path: Path):
    provider = SuccessProvider()

    state, response = asyncio.run(runtime(tmp_path, provider).run("hello world", {"reasoning"}))

    assert state.status == "completed"
    assert response.content == "successful response"
    assert state.selected_model == "primary"
    assert state.provider == "fake"
    assert state.fallback_used is False
    assert state.attempted_models == ["primary"]
    assert state.user_prompt == "hello world"
    assert state.final_response == "successful response"
    assert state.messages == ["hello world", "successful response"]
    assert state.errors == []
    assert state.plan == ["generate_response"]
    assert isinstance(state.task_id, str) and len(state.task_id) > 0


def test_runtime_provider_failure_returns_predictable_response(tmp_path: Path):
    provider = AllFailingProvider(ProviderError("Ollama connection refused"))

    state, response = asyncio.run(runtime(tmp_path, provider).run("test prompt", {"reasoning"}))

    assert state.status == "failed"
    assert state.fallback_used is True
    assert state.attempted_models == ["primary", "backup"]
    assert state.errors == ["Ollama connection refused", "Ollama connection refused"]
    assert response.content.startswith("Model generation failed: Ollama connection refused")
    assert state.final_response == response.content
    assert state.messages == ["test prompt", response.content]
    assert state.selected_model == "backup"
    assert provider.calls == ["primary", "backup"]


def test_runtime_rejects_empty_or_whitespace_user_prompt(tmp_path: Path):
    rt = runtime(tmp_path, SuccessProvider())

    with pytest.raises(StateValidationError, match="user_prompt"):
        asyncio.run(rt.run("", {"reasoning"}))

    with pytest.raises(StateValidationError, match="user_prompt"):
        asyncio.run(rt.run("   ", {"reasoning"}))


def test_runtime_graph_validates_missing_or_invalid_state_fields(tmp_path: Path):
    rt = runtime(tmp_path, SuccessProvider())

    # Missing task_id
    with pytest.raises(StateValidationError, match="task_id"):
        asyncio.run(
            rt.graph.ainvoke(
                {
                    "user_prompt": "hello",
                    "messages": ["hello"],
                    "required_capabilities": {"reasoning"},
                    "modality": "text",
                }
            )
        )

    # Empty task_id
    with pytest.raises(StateValidationError, match="task_id"):
        asyncio.run(
            rt.graph.ainvoke(
                {
                    "task_id": "  ",
                    "user_prompt": "hello",
                    "messages": ["hello"],
                    "required_capabilities": {"reasoning"},
                    "modality": "text",
                }
            )
        )

    # Missing user_prompt
    with pytest.raises(StateValidationError, match="user_prompt"):
        asyncio.run(
            rt.graph.ainvoke(
                {
                    "task_id": "task-123",
                    "messages": ["hello"],
                    "required_capabilities": {"reasoning"},
                    "modality": "text",
                }
            )
        )

    # Missing messages
    with pytest.raises(StateValidationError, match="messages"):
        asyncio.run(
            rt.graph.ainvoke(
                {
                    "task_id": "task-123",
                    "user_prompt": "hello",
                    "required_capabilities": {"reasoning"},
                    "modality": "text",
                }
            )
        )

    # Empty messages list
    with pytest.raises(StateValidationError, match="messages"):
        asyncio.run(
            rt.graph.ainvoke(
                {
                    "task_id": "task-123",
                    "user_prompt": "hello",
                    "messages": [],
                    "required_capabilities": {"reasoning"},
                    "modality": "text",
                }
            )
        )


def test_validate_state_checks_selected_model_when_required():
    from backend.agents.state import validate_state

    valid_initial = {"task_id": "t1", "user_prompt": "p1", "messages": ["p1"]}
    validate_state(valid_initial, require_model=False)

    with pytest.raises(StateValidationError, match="selected_model"):
        validate_state(valid_initial, require_model=True)

    with pytest.raises(StateValidationError, match="selected_model"):
        validate_state({**valid_initial, "selected_model": "  "}, require_model=True)

    validate_state({**valid_initial, "selected_model": "reasoning"}, require_model=True)

