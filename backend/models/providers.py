"""Inference-engine adapters.

The rest of the application addresses a model by its configured ``runtime``.
It never needs to know which HTTP API, SDK, or process a runtime uses.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping
import json
from typing import Any

import httpx

from backend.models.contracts import (
    ChatMessage,
    ModelDefinition,
    ModelRequest,
    ModelResponse,
    ToolCall,
    normalize_messages,
)


class ModelProvider(ABC):
    """Adapter for one model inference runtime."""

    @abstractmethod
    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse: ...

    async def stream_generate(
        self,
        model: ModelDefinition,
        request: ModelRequest,
    ) -> AsyncIterator[str]:
        """Stream content with a fallback for providers without native streaming."""
        response = await self.generate(model, request)
        if response.content:
            yield response.content

    async def stream_generate_response(
        self,
        model: ModelDefinition,
        request: ModelRequest,
    ) -> ModelResponse:
        """Collect a streaming response while preserving its final metadata."""
        content_parts: list[str] = []
        async for chunk in self.stream_generate(model, request):
            content_parts.append(chunk)
        return ModelResponse(content="".join(content_parts), model_id=model.id)


class ProviderError(RuntimeError):
    """Base error for failures at the model-provider boundary."""


class ProviderRequestError(ProviderError):
    """Raised when the provider rejects a malformed or invalid request."""


class ProviderNotFoundError(ProviderError):
    """Raised when no adapter has been registered for a model runtime."""


class ModelProviderRegistry:
    """Runtime-to-provider mapping owned by the model gateway."""

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

    async def stream_generate(
        self,
        model: ModelDefinition,
        request: ModelRequest,
    ) -> AsyncIterator[str]:
        async for chunk in self.get(model.runtime).stream_generate(model, request):
            yield chunk

    async def stream_generate_response(
        self,
        model: ModelDefinition,
        request: ModelRequest,
    ) -> ModelResponse:
        provider = self.get(model.runtime)
        collector = getattr(provider, "stream_generate_response", None)
        if collector is not None:
            return await collector(model, request)
        content_parts: list[str] = []
        async for chunk in provider.stream_generate(model, request):
            content_parts.append(chunk)
        return ModelResponse(content="".join(content_parts), model_id=model.id)


class OllamaProvider(ModelProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    @staticmethod
    def _format_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool_schema.get("name"),
                    "description": tool_schema.get("description", ""),
                    "parameters": tool_schema.get("parameters", {}),
                },
            }
            for tool_schema in tools
        ]

    @staticmethod
    def _tool_calls_from_data(data: dict[str, Any]) -> list[ToolCall]:
        message = data.get("message", {})
        if not isinstance(message, dict):
            return []
        raw_tool_calls = message.get("tool_calls", [])
        tool_calls: list[ToolCall] = []
        if not isinstance(raw_tool_calls, list):
            return tool_calls
        for tool_call in raw_tool_calls:
            if not isinstance(tool_call, dict):
                continue
            function = tool_call.get("function", {})
            if not isinstance(function, dict):
                function = {}
            name = function.get("name") or tool_call.get("name")
            arguments = function.get("arguments") or tool_call.get("arguments") or {}
            call_id = tool_call.get("id")
            if isinstance(name, str) and name.strip():
                tool_calls.append(
                    ToolCall(
                        name=name.strip(),
                        arguments=arguments if isinstance(arguments, dict) else {},
                        id=call_id if isinstance(call_id, str) else None,
                    )
                )
        return tool_calls

    @staticmethod
    def _response_from_data(model: ModelDefinition, data: Any) -> ModelResponse:
        if not isinstance(data, dict):
            raise ProviderError(f"Ollama returned an invalid response for model '{model.id}'")
        message = data.get("message", {})
        if not isinstance(message, dict):
            raise ProviderError(f"Ollama returned an invalid response for model '{model.id}'")
        content = message.get("content", "")
        if not content and isinstance(data.get("response"), str):
            content = data.get("response", "")
        if not isinstance(content, str):
            raise ProviderError(f"Ollama returned an invalid response for model '{model.id}'")
        tool_calls = OllamaProvider._tool_calls_from_data(data)
        if not content.strip() and tool_calls:
            call_summaries = [f"{call.name}({json.dumps(call.arguments)})" for call in tool_calls]
            content = f"Tool calls requested: {', '.join(call_summaries)}"
        return ModelResponse(
            content=content,
            model_id=model.id,
            raw=data,
            tool_calls=tool_calls,
        )

    @staticmethod
    def _clean_base64_image(data: str) -> str:
        """Ensure base64 image strings do not have data URI scheme prefixes before sending to Ollama."""
        if isinstance(data, str) and data.startswith("data:") and ";base64," in data:
            return data.split(";base64,", 1)[1]
        if isinstance(data, str) and data.startswith("data:") and "," in data:
            return data.split(",", 1)[1]
        return data

    def _build_payload(self, model: ModelDefinition, request: ModelRequest, *, stream: bool) -> dict[str, Any]:
        messages = normalize_messages(request.messages, request.prompt, request.images)
        payload: dict[str, Any] = {
            "model": model.model,
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                    **({"images": [self._clean_base64_image(img) for img in message.images]} if message.images else {}),
                }
                for message in messages
            ],
            "stream": stream,
        }
        if request.documents:
            payload["documents"] = request.documents
        if request.tools:
            payload["tools"] = self._format_tools(request.tools)
        return payload

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        payload = self._build_payload(model, request, stream=False)
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
        return self._response_from_data(model, data)

    async def _stream_response(
        self,
        model: ModelDefinition,
        request: ModelRequest,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        payload = self._build_payload(model, request, stream=True)
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError as error:
                            raise ProviderError(
                                f"Ollama returned an invalid stream response for model '{model.id}'"
                            ) from error
                        if not isinstance(data, dict) or not isinstance(data.get("message"), dict):
                            raise ProviderError(
                                f"Ollama returned an invalid stream response for model '{model.id}'"
                            )
                        content = data["message"].get("content", "")
                        if not isinstance(content, str):
                            raise ProviderError(
                                f"Ollama returned an invalid stream response for model '{model.id}'"
                            )
                        if content:
                            yield content, data
            except httpx.HTTPStatusError as error:
                if error.response.status_code in {400, 422}:
                    raise ProviderRequestError(
                        f"Ollama rejected generation request for model '{model.id}'"
                    ) from error
                raise ProviderError(f"Ollama generation failed for model '{model.id}'") from error
            except httpx.HTTPError as error:
                raise ProviderError(f"Ollama generation failed for model '{model.id}'") from error

    async def stream_generate(
        self,
        model: ModelDefinition,
        request: ModelRequest,
    ) -> AsyncIterator[str]:
        async for content, _ in self._stream_response(model, request):
            yield content

    async def stream_generate_response(
        self,
        model: ModelDefinition,
        request: ModelRequest,
    ) -> ModelResponse:
        content_parts: list[str] = []
        final_data: dict[str, Any] = {}
        async for content, data in self._stream_response(model, request):
            content_parts.append(content)
            final_data = data
        response = self._response_from_data(model, final_data or {"message": {}})
        if not response.content and response.tool_calls:
            response = ModelResponse(
                content=f"Tool calls requested: {', '.join(f'{call.name}({json.dumps(call.arguments)})' for call in response.tool_calls)}",
                model_id=model.id,
                raw=response.raw,
                tool_calls=response.tool_calls,
            )
        return response
