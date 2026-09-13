import asyncio
from pathlib import Path

from backend.agents.runtime import AgentRuntime
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
