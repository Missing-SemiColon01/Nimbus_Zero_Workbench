"""Inference-engine adapters.

The rest of the application addresses a model by its configured ``runtime``.
It never needs to know which HTTP API, SDK, or process a runtime uses.
"""

from abc import ABC, abstractmethod
from collections.abc import Mapping
import json
from typing import Any

import httpx

from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse, ToolCall


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
        messages = []
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})

        payload: dict[str, Any] = {
            "model": model.model,
            "messages": messages,
            "stream": False,
        }
        if request.images:
            # Attach images to the last user message if present
            if messages:
                messages[-1]["images"] = request.images
            else:
                messages.append({"role": "user", "content": "", "images": request.images})

        if request.tools:
            formatted_tools = []
            for tool_schema in request.tools:
                formatted_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool_schema.get("name"),
                        "description": tool_schema.get("description", ""),
                        "parameters": tool_schema.get("parameters", {}),
                    },
                })
            payload["tools"] = formatted_tools

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                response = await client.post(f"{self.base_url}/api/chat", json=payload)
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

        msg = data.get("message", {})
        content = msg.get("content", "")
        raw_tool_calls = msg.get("tool_calls", [])
        tool_calls = []

        if isinstance(raw_tool_calls, list):
            for tc in raw_tool_calls:
                if isinstance(tc, dict):
                    fn = tc.get("function", {})
                    name = fn.get("name") or tc.get("name")
                    args = fn.get("arguments") or tc.get("arguments") or {}
                    call_id = tc.get("id")
                    if isinstance(name, str) and name.strip():
                        tool_calls.append(ToolCall(name=name.strip(), arguments=args if isinstance(args, dict) else {}, id=call_id))

        if not content.strip() and tool_calls:
            call_summaries = [f"{tc.name}({json.dumps(tc.arguments)})" for tc in tool_calls]
            content = f"Tool calls requested: {', '.join(call_summaries)}"

        return ModelResponse(
            content=content,
            model_id=model.id,
            raw=data,
            tool_calls=tool_calls,
        )
