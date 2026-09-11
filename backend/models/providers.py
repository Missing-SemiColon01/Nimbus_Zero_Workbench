from abc import ABC, abstractmethod

import httpx

from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse


class ModelProvider(ABC):
    @abstractmethod
    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse: ...


class OllamaProvider(ModelProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{self.base_url}/api/generate", json={"model": model.model, "prompt": request.prompt, "stream": False})
            response.raise_for_status()
            data = response.json()
        return ModelResponse(content=data.get("response", ""), model_id=model.id, raw=data)
