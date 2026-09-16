from __future__ import annotations

from unittest.mock import MagicMock, patch

from starlette.testclient import TestClient

from backend.main import app
from backend.sandbox.contracts import SandboxRequest, SandboxResult
from backend.tools.sandbox_tool import SandboxTool


class FakeExecutor:
    def __init__(self, result: SandboxResult | None = None):
        self.requests: list[SandboxRequest] = []
        self.result = result or SandboxResult(
            exit_code=0,
            stdout="42\n",
            stderr="",
            test_passed=False,
        )

    def run(self, request: SandboxRequest) -> SandboxResult:
        self.requests.append(request)
        return self.result


def test_sandbox_tool_executes_with_expected_contract():
    executor = FakeExecutor()
    tool = SandboxTool(executor)

    import asyncio

    result = asyncio.run(
        tool.execute(
            {"code": "print(42)", "test_code": "", "timeout_seconds": 5},
            context={},
        )
    )

    assert result.success is True
    assert result.output["exit_code"] == 0
    assert result.output["stdout"] == "42\n"
    assert executor.requests[0].code == "print(42)"
    assert executor.requests[0].timeout_seconds == 5


def test_sandbox_tool_rejects_empty_code():
    import asyncio

    result = asyncio.run(SandboxTool(FakeExecutor()).execute({"code": "   "}, context={}))

    assert result.success is False
    assert result.error == "No code provided."


def test_sandbox_run_api_uses_registered_tool():
    fake_tool = SandboxTool(FakeExecutor())
    with TestClient(app) as client:
        app.state.tools.register(fake_tool)
        response = client.post(
            "/api/v1/sandbox/run",
            json={"code": "print(42)", "timeout_seconds": 5},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["exit_code"] == 0
    assert body["stdout"] == "42\n"
    assert fake_tool.executor.requests[0].timeout_seconds == 5


def test_sandbox_execute_is_registered_in_tool_registry():
    fake_executor = FakeExecutor()
    with patch("backend.tools.setup.build_executor", return_value=fake_executor):
        from backend.tools.setup import build_tool_registry

        registry = build_tool_registry(
            retriever=MagicMock(),
            model_registry=MagicMock(),
            provider_registry=MagicMock(),
        )

    assert "sandbox.execute" in registry.names()
    assert isinstance(registry.get("sandbox.execute"), SandboxTool)
