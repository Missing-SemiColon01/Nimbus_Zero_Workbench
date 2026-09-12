import httpx
import pytest

from backend.main import app
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider, ProviderError


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
    assert body["plan"] == ["classify_task", "select_model", "execute", "validate"]
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
