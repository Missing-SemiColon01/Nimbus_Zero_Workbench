import httpx
import pytest

from backend.main import app
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider
from backend.sandbox.coding_workflow import extract_python_code


class RepairingProvider(ModelProvider):
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        self.prompts.append(request.prompt)
        if len(self.prompts) == 1:
            return ModelResponse(
                content="""```python
def add(a, b):
    return a - b
```""",
                model_id=model.id,
            )
        return ModelResponse(
            content="""```python
def add(a, b):
    return a + b
```""",
            model_id=model.id,
        )


def test_extract_python_code_accepts_fenced_and_raw_code():
    assert extract_python_code("```python\nprint('ok')\n```") == "print('ok')"
    assert extract_python_code("def f():\n    return 1") == "def f():\n    return 1"


@pytest.mark.asyncio
async def test_coding_run_repairs_failed_sandbox_tests():
    provider = RepairingProvider()
    async with app.router.lifespan_context(app):
        app.state.runtime.providers.register("ollama", provider)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/coding/run",
                json={
                    "requirement": "Write an add(a, b) function.",
                    "test_code": "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
                    "max_retries": 1,
                    "timeout_seconds": 10,
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["selected_model"] == "coding"
    assert "return a + b" in body["verified_code"]
    assert len(body["attempts"]) == 2
    assert body["attempts"][0]["test_passed"] is False
    assert body["attempts"][1]["test_passed"] is True
    assert "Previous sandbox failure" in provider.prompts[1]


@pytest.mark.asyncio
async def test_coding_run_returns_failed_when_retries_exhausted():
    class AlwaysWrongProvider(ModelProvider):
        async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
            return ModelResponse(content="def add(a, b):\n    return a - b", model_id=model.id)

    async with app.router.lifespan_context(app):
        app.state.runtime.providers.register("ollama", AlwaysWrongProvider())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/coding/run",
                json={
                    "requirement": "Write an add(a, b) function.",
                    "test_code": "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
                    "max_retries": 0,
                    "timeout_seconds": 10,
                },
            )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert len(body["attempts"]) == 1
    assert body["attempts"][0]["test_passed"] is False
    assert body["errors"]
