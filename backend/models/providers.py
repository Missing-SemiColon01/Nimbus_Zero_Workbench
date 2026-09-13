"""Inference-engine adapters.

The rest of the application addresses a model by its configured ``runtime``.
It never needs to know which HTTP API, SDK, or process a runtime uses.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

import httpx

from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse


class ModelProvider(ABC):
    """Adapter for one model inference runtime."""

    @abstractmethod
    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse: ...


class ProviderError(RuntimeError):
    """Base error for failures at the model-provider boundary."""


class ProviderRequestError(ProviderError):
    """The provider rejected a malformed or invalid generation request.

    Retrying another model cannot make an invalid request valid, so callers
    must surface this error rather than treating it as an availability issue.
    """


class ProviderNotFoundError(ProviderError):
    """Raised when no adapter has been registered for a model runtime."""


class ModelProviderRegistry:
    """Runtime-to-provider mapping owned by the model gateway.

    The registry deliberately accepts the abstract ``ModelProvider`` type, so
    adding vLLM, llama.cpp, or another local engine is an adapter/configuration
    change and does not affect agents or routing.
    """

    def __init__(self, providers: Mapping[str, ModelProvider] | None = None):
        self._providers: dict[str, ModelProvider] = {}
        for runtime, provider in (providers or {}).items():
            self.register(runtime, provider)

    def register(self, runtime: str, provider: ModelProvider) -> None:
        runtime = runtime.strip().lower()
        if not runtime:
            raise ValueError("Provider runtime cannot be empty")
        self._providers[runtime] = provider

    def get(self, runtime: str) -> ModelProvider:
        try:
            return self._providers[runtime.strip().lower()]
        except KeyError as error:
            raise ProviderNotFoundError(f"No provider registered for runtime '{runtime}'") from error

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        """Dispatch a request using the provider selected by model configuration."""
        return await self.get(model.runtime).generate(model, request)


class OllamaProvider(ModelProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        payload: dict[str, Any] = {"model": model.model, "prompt": request.prompt, "stream": False}
        if request.images:
            payload["images"] = request.images
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as error:
                if error.response.status_code in {400, 422}:
                    raise ProviderRequestError(
                        f"Ollama rejected generation request for model '{model.id}'"
                    ) from error
                raise ProviderError(f"Ollama generation failed for model '{model.id}'") from error
            except httpx.HTTPError as error:
                raise ProviderError(f"Ollama generation failed for model '{model.id}'") from error
            except ValueError as error:
                raise ProviderError(f"Ollama returned an invalid response for model '{model.id}'") from error
        return ModelResponse(content=data.get("response", ""), model_id=model.id, raw=data)
