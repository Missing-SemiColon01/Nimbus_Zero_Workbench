import httpx
import pytest

from backend.main import app
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider, ProviderError, ProviderRequestError


class FakeProvider(ModelProvider):
    def __init__(self, response: str = "Generated answer"):
        self.response = response
        self.calls: list[tuple[ModelDefinition, ModelRequest]] = []

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        self.calls.append((model, request))
        return ModelResponse(content=self.response, model_id=model.id)


class FailingProvider(ModelProvider):
    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        raise ProviderError("Ollama is unavailable")


class FailFirstProvider(ModelProvider):
    def __init__(self):
        self.calls: list[str] = []

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        self.calls.append(model.id)
        if model.id == "reasoning":
            raise ProviderError("model is temporarily unavailable")
        return ModelResponse(content="Fallback answer", model_id=model.id)


class InvalidRequestProvider(ModelProvider):
    def __init__(self):
        self.calls: list[str] = []

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        self.calls.append(model.id)
        raise ProviderRequestError("prompt is malformed")


@pytest.mark.asyncio
async def test_create_task_generates_response_with_selected_model():
    provider = FakeProvider()
    async with app.router.lifespan_context(app):
        app.state.runtime.providers.register("ollama", provider)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
            "/api/v1/tasks",
            json={"request": "Explain model routing", "capabilities": ["reasoning"]},
            )

    assert response.status_code == 201
    body = response.json()
    assert body["task_id"]
    assert body["status"] == "completed"
    assert body["selected_model"] == "reasoning"
    assert body["provider"] == "ollama"
    assert body["fallback_used"] is False
    assert body["attempted_models"] == ["reasoning"]
    assert body["plan"] == ["generate_response"]
    assert body["response"] == "Generated answer"
    assert len(provider.calls) == 1
    model, request = provider.calls[0]
    assert model.id == "reasoning"
    assert request.prompt == "Explain model routing"


@pytest.mark.asyncio
async def test_create_task_returns_clean_error_when_provider_fails():
    async with app.router.lifespan_context(app):
        app.state.runtime.providers.register("ollama", FailingProvider())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
            "/api/v1/tasks",
            json={"request": "Explain model routing", "capabilities": ["reasoning"]},
            )

    assert response.status_code == 502
    assert response.json() == {"detail": "Model generation failed"}


@pytest.mark.asyncio
async def test_create_task_falls_back_to_next_eligible_model():
    provider = FailFirstProvider()
    async with app.router.lifespan_context(app):
        app.state.runtime.providers.register("ollama", provider)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tasks",
                json={"request": "Explain model routing", "task_type": "reasoning"},
            )

    assert response.status_code == 201
    assert response.json() | {"task_id": "ignored"} == {
        "task_id": "ignored",
        "status": "completed",
        "selected_model": "reasoning-fallback",
        "provider": "ollama",
        "fallback_used": True,
        "attempted_models": ["reasoning", "reasoning-fallback"],
        "plan": ["generate_response"],
        "response": "Fallback answer",
    }
    assert provider.calls == ["reasoning", "reasoning-fallback"]


@pytest.mark.asyncio
async def test_create_task_does_not_fallback_for_invalid_provider_request():
    provider = InvalidRequestProvider()
    async with app.router.lifespan_context(app):
        app.state.runtime.providers.register("ollama", provider)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tasks",
                json={"request": "Explain model routing", "task_type": "reasoning"},
            )

    assert response.status_code == 422
    assert response.json() == {"detail": "Model generation request is invalid"}
    assert provider.calls == ["reasoning"]


@pytest.mark.asyncio
async def test_create_task_maps_task_type_to_capability():
    provider = FakeProvider()
    async with app.router.lifespan_context(app):
        app.state.runtime.providers.register("ollama", provider)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tasks",
                json={"request": "Write a unit test", "task_type": "coding"},
            )

    assert response.status_code == 201
    assert response.json()["selected_model"] == "coding"
    assert provider.calls[0][1].required_capabilities == {"coding"}
