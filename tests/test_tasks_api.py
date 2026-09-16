import httpx
import pytest
from pathlib import Path

from backend.main import app
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse, ToolCall
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


class ApprovalToolProvider(ModelProvider):
    def __init__(self):
        self.calls = 0

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.calls == 1:
            return ModelResponse(
                content='{"tool":"document.create","arguments":{"title":"Approval note"}}',
                model_id=model.id,
                tool_calls=[
                    ToolCall(
                        name="document.create",
                        arguments={"title": "Approval note"},
                        id="create-doc-1",
                    )
                ],
            )
        return ModelResponse(content="Approval is required before creating the document.", model_id=model.id)


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
    assert isinstance(body["execution_duration"], float)
    assert body["execution_duration"] >= 0
    assert body["artifacts"] == []
    assert body["tool_results"] == []
    assert body["errors"] == []
    assert body["approval_required"] is False
    assert body["approval_requests"] == []
    assert len(provider.calls) == 1
    model, request = provider.calls[0]
    assert model.id == "reasoning"
    assert "Industrial Workbench Agent" in request.prompt
    assert request.prompt.endswith("Explain model routing")


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
    assert response.json() | {
        "task_id": "ignored",
        "execution_duration": "ignored",
        "artifacts": [],
        "tool_results": [],
        "errors": [],
        "approval_required": False,
        "approval_requests": [],
    } == {
        "task_id": "ignored",
        "status": "completed",
        "selected_model": "reasoning-fallback",
        "provider": "ollama",
        "fallback_used": True,
        "attempted_models": ["reasoning", "reasoning-fallback"],
        "plan": ["generate_response"],
        "response": "Fallback answer",
        "execution_duration": "ignored",
        "artifacts": [],
        "tool_results": [],
        "errors": [],
        "approval_required": False,
        "approval_requests": [],
    }
    assert isinstance(response.json()["execution_duration"], float)
    assert response.json()["execution_duration"] >= 0
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


@pytest.mark.asyncio
async def test_create_task_accepts_uploaded_document_path(tmp_path: Path):
    provider = FakeProvider()
    async with app.router.lifespan_context(app):
        app.state.settings.data_dir = tmp_path
        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir(parents=True)
        uploaded_pdf = uploads_dir / "inspection.pdf"
        uploaded_pdf.write_bytes(b"%PDF-1.4 test")

        app.state.runtime.providers.register("ollama", provider)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tasks",
                json={
                    "request": "Find safety issues in this inspection report",
                    "document_paths": [str(uploaded_pdf)],
                },
            )

    assert response.status_code == 201
    body = response.json()
    assert body["selected_model"] == "vision"
    model, request = provider.calls[0]
    assert model.id == "vision"
    assert request.required_modality == "document"
    assert request.documents == [str(uploaded_pdf.resolve())]
    assert "document_understanding" in request.required_capabilities


@pytest.mark.asyncio
async def test_create_task_rejects_document_path_outside_uploads(tmp_path: Path):
    outside_pdf = tmp_path / "outside.pdf"
    outside_pdf.write_bytes(b"%PDF-1.4 test")

    async with app.router.lifespan_context(app):
        app.state.settings.data_dir = tmp_path / "data"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tasks",
                json={
                    "request": "Analyze this document",
                    "document_paths": [str(outside_pdf)],
                },
            )

    assert response.status_code == 404
    assert "document not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_task_returns_trace_fields_for_tool_approval():
    provider = ApprovalToolProvider()
    async with app.router.lifespan_context(app):
        app.state.runtime.providers.register("ollama", provider)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tasks",
                json={"request": "Create an approval note", "task_type": "reasoning"},
            )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "awaiting_approval"
    assert body["approval_required"] is True
    assert body["approval_requests"] == [
        {
            "tool": "document.create",
            "arguments": {"title": "Approval note"},
            "tool_call_id": "create-doc-1",
            "reason": "Tool 'document.create' requires human approval.",
        }
    ]
    assert body["tool_results"][0]["tool"] == "document.create"
    assert body["tool_results"][0]["success"] is False
    assert body["artifacts"] == []
