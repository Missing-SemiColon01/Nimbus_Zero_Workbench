import asyncio
import json

import httpx
import pytest

from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider, ModelProviderRegistry, ProviderNotFoundError


MODEL = ModelDefinition(
    id="test-model",
    runtime="fake",
    model="test:latest",
    capabilities={"reasoning"},
    modalities={"text"},
)


class FakeProvider(ModelProvider):
    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content=request.prompt, model_id=model.id)


def test_provider_registry_dispatches_using_model_runtime():
    providers = ModelProviderRegistry({"fake": FakeProvider()})

    response = asyncio.run(providers.generate(MODEL, ModelRequest(prompt="hello")))

    assert response.content == "hello"
    assert response.model_id == "test-model"


def test_provider_registry_rejects_unknown_runtime():
    with pytest.raises(ProviderNotFoundError, match="missing"):
        ModelProviderRegistry().get("missing")


def test_ollama_provider_sends_canonical_request(monkeypatch):
    from backend.models.providers import OllamaProvider

    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": "done", "eval_count": 3})

    transport = httpx.MockTransport(handler)

    class TestClient(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(transport=transport, **kwargs)

    monkeypatch.setattr("backend.models.providers.httpx.AsyncClient", TestClient)
    response = asyncio.run(
        OllamaProvider("http://ollama:11434/").generate(
            MODEL,
            ModelRequest(prompt="inspect", images=["base64-image"]),
        )
    )

    assert captured == {
        "url": "http://ollama:11434/api/generate",
        "body": {"model": "test:latest", "prompt": "inspect", "stream": False, "images": ["base64-image"]},
    }
    assert response.content == "done"
    assert response.raw["eval_count"] == 3
