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
    assert isinstance(state.execution_duration, float)
    assert state.execution_duration >= 0


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
    assert state.provider is None
    assert provider.calls == ["primary", "backup"]
    assert isinstance(state.execution_duration, float)
    assert state.execution_duration >= 0


def test_runtime_status_lifecycle_and_execution_metadata(tmp_path: Path):
    provider = SuccessProvider()
    rt = runtime(tmp_path, provider)

    # Initial graph step validation
    initial_graph_state = {
        "task_id": "test-task-id",
        "user_prompt": "analyze data",
        "selected_model": None,
        "messages": ["analyze data"],
        "final_response": None,
        "errors": [],
        "attempted_models": [],
        "provider": None,
        "fallback_used": False,
        "model_response": None,
        "required_capabilities": {"reasoning"},
        "modality": "text",
        "status": "queued",
        "execution_duration": None,
    }

    # Verify input validation step transitions queued -> running
    running_state = asyncio.run(rt._validate_input(initial_graph_state))
    assert running_state["status"] == "running"

    # Verify full run completes with execution metadata
    state, response = asyncio.run(rt.run("analyze data", {"reasoning"}, task_id="custom-id"))
    assert state.task_id == "custom-id"
    assert state.status == "completed"
    assert state.selected_model == "primary"
    assert state.provider == "fake"
    assert isinstance(state.execution_duration, float)
    assert state.execution_duration >= 0



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


class SlowProvider(ModelProvider):
    def __init__(self, delay: float = 0.2):
        self.delay = delay

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        await asyncio.sleep(self.delay)
        return ModelResponse(content="slow response", model_id=model.id)


def test_runtime_timeout_returns_predictable_failure(tmp_path: Path):
    provider = SlowProvider(delay=0.1)
    rt = runtime(tmp_path, provider)

    state, response = asyncio.run(rt.run("hello", {"reasoning"}, timeout=0.01))

    assert state.status == "failed"
    assert "timed out" in state.final_response
    assert any("timed out" in err for err in state.errors)
    assert response.content == state.final_response
    assert isinstance(state.execution_duration, float)


class CountedFailingProvider(ModelProvider):
    def __init__(self):
        self.calls: list[str] = []

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        self.calls.append(model.id)
        raise ProviderError(f"Failure in {model.id}")


def test_runtime_provider_retry_limit(tmp_path: Path):
    config = tmp_path / "models.yaml"
    config.write_text(
        """models:
  - id: m1
    runtime: fake
    model: m1
    capabilities: [reasoning]
    modalities: [text]
    priority: 30
  - id: m2
    runtime: fake
    model: m2
    capabilities: [reasoning]
    modalities: [text]
    priority: 20
  - id: m3
    runtime: fake
    model: m3
    capabilities: [reasoning]
    modalities: [text]
    priority: 10
"""
    )
    provider = CountedFailingProvider()
    rt = AgentRuntime(ModelRouter(ModelRegistry(config)), ModelProviderRegistry({"fake": provider}))

    # max_retries = 1: 1 initial attempt (m1) + 1 retry (m2). m3 must NOT be attempted!
    state, response = asyncio.run(rt.run("hello", {"reasoning"}, max_retries=1))

    assert state.status == "failed"
    assert provider.calls == ["m1", "m2"]
    assert any("Provider retry limit (1) reached" in err for err in state.errors)
    assert "Model generation failed" in state.final_response


def test_runtime_step_limit_exceeded(tmp_path: Path):
    provider = SuccessProvider()
    rt = runtime(tmp_path, provider)

    # Workflow has 3 nodes (validate_input -> generate_response -> validate_output)
    # If max_steps is set to 1, validate_input runs (step 1), but generate_response (step 2) exceeds max_steps!
    state, response = asyncio.run(rt.run("hello", {"reasoning"}, max_steps=1))

    assert state.status == "failed"
    assert any("Maximum workflow steps" in err for err in state.errors)
    assert "Maximum workflow steps" in state.final_response


def test_runtime_infinite_loop_protection(tmp_path: Path):
    from backend.agents.runtime import detect_cycle
    from backend.agents.state import InfiniteLoopError

    # Test cycle detection helper
    assert detect_cycle(["a", "b", "a", "b", "a", "b"], min_repetitions=3) is True
    assert detect_cycle(["a", "a", "a"], min_repetitions=3) is True
    assert detect_cycle(["validate_input", "generate_response", "validate_output"]) is False

    # Test runtime triggers InfiniteLoopError on repeating cycle
    provider = SuccessProvider()
    rt = runtime(tmp_path, provider)

    looping_state = {
        "step_count": 5,
        "max_steps": 20,
        "node_history": ["node_a", "node_b", "node_a", "node_b", "node_a"],
    }
    with pytest.raises(InfiniteLoopError, match="Infinite loop detected"):
        rt._track_step(looping_state, "node_b")

    # Also test single node repeated 3 times
    single_loop_state = {
        "step_count": 2,
        "max_steps": 20,
        "node_history": ["node_a", "node_a"],
    }
    with pytest.raises(InfiniteLoopError, match="Infinite loop detected"):
        rt._track_step(single_loop_state, "node_a")



