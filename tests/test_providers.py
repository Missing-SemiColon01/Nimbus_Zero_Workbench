import asyncio
import json

import httpx
import pytest

from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import (
    ModelProvider,
    ModelProviderRegistry,
    OllamaProvider,
    ProviderError,
    ProviderNotFoundError,
)


MODEL = ModelDefinition(
    id="test-model",
    runtime="fake",
    model="test:latest",
    capabilities={"reasoning"},
    modalities={"text"},
)

VISION_MODEL = ModelDefinition(
    id="vision",
    runtime="ollama",
    model="qwen2.5-vl:7b",
    capabilities={"vision"},
    modalities={"text", "image"},
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


def test_provider_registry_rejects_empty_runtime():
    with pytest.raises(ValueError, match="cannot be empty"):
        ModelProviderRegistry().register("  ", FakeProvider())


def test_ollama_provider_sends_canonical_vision_request(monkeypatch):
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": "valve detected", "eval_count": 5})

    transport = httpx.MockTransport(handler)

    class TestClient(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(transport=transport, **kwargs)

    monkeypatch.setattr("backend.models.providers.httpx.AsyncClient", TestClient)

    response = asyncio.run(
        OllamaProvider("http://ollama:11434/").generate(
            VISION_MODEL,
            ModelRequest(prompt="inspect", images=["base64-image-data"]),
        )
    )

    assert captured == {
        "url": "http://ollama:11434/api/generate",
        "body": {
            "model": "qwen2.5-vl:7b",
            "prompt": "inspect",
            "stream": False,
            "images": ["base64-image-data"],
        },
    }
    assert response.content == "valve detected"
    assert response.model_id == "vision"
    assert response.raw["eval_count"] == 5


def test_ollama_provider_omits_images_field_for_text_request(monkeypatch):
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": "text answer"})

    transport = httpx.MockTransport(handler)

    class TestClient(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(transport=transport, **kwargs)

    monkeypatch.setattr("backend.models.providers.httpx.AsyncClient", TestClient)

    response = asyncio.run(
        OllamaProvider("http://ollama:11434").generate(
            MODEL,
            ModelRequest(prompt="only text prompt"),
        )
    )

    assert "images" not in captured["body"]
    assert captured["body"]["model"] == "test:latest"
    assert captured["body"]["prompt"] == "only text prompt"
    assert response.content == "text answer"


def test_ollama_provider_raises_provider_error_on_http_failure(monkeypatch):
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Model failed to load"})

    transport = httpx.MockTransport(handler)

    class TestClient(httpx.AsyncClient):
        def __init__(self, **kwargs):
            super().__init__(transport=transport, **kwargs)

    monkeypatch.setattr("backend.models.providers.httpx.AsyncClient", TestClient)

    with pytest.raises(ProviderError, match="Ollama generation failed for model 'test-model'"):
        asyncio.run(
            OllamaProvider("http://ollama:11434").generate(
                MODEL,
                ModelRequest(prompt="trigger failure"),
            )
        )
