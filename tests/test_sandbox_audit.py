from pathlib import Path

import httpx
import pytest

from backend.main import app
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider
from backend.security.audit import AuditLogger


class PassingCodeProvider(ModelProvider):
    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content="def add(a, b):\n    return a + b", model_id=model.id)


def test_audit_logger_writes_jsonl_events(tmp_path: Path):
    logger = AuditLogger(tmp_path)
    event = logger.record("sandbox.run", {"success": True}, task_id="task-1")

    events = logger.tail()
    assert len(events) == 1
    assert events[0]["event_id"] == event.event_id
    assert events[0]["event_type"] == "sandbox.run"
    assert events[0]["task_id"] == "task-1"
    assert events[0]["payload"] == {"success": True}


@pytest.mark.asyncio
async def test_sandbox_run_records_audit_event(tmp_path: Path):
    async with app.router.lifespan_context(app):
        app.state.settings.data_dir = tmp_path
        app.state.audit = AuditLogger(tmp_path)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/sandbox/run",
                json={"code": "print('audit')", "timeout_seconds": 10},
            )
            audit_response = await client.get("/api/v1/audit/events")

    assert response.status_code == 200
    assert audit_response.status_code == 200
    events = audit_response.json()
    assert events[-1]["event_type"] == "sandbox.run"
    assert events[-1]["payload"]["network_disabled"] is True
    assert events[-1]["payload"]["success"] is True


@pytest.mark.asyncio
async def test_coding_run_records_audit_event(tmp_path: Path):
    async with app.router.lifespan_context(app):
        app.state.settings.data_dir = tmp_path
        app.state.audit = AuditLogger(tmp_path)
        app.state.runtime.providers.register("ollama", PassingCodeProvider())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/coding/run",
                json={
                    "requirement": "Write add(a, b).",
                    "test_code": "from solution import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
                    "max_retries": 0,
                    "timeout_seconds": 10,
                },
            )
            audit_response = await client.get("/api/v1/audit/events?limit=1")

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    event = audit_response.json()[0]
    assert event["event_type"] == "coding.run"
    assert event["task_id"] == response.json()["task_id"]
    assert event["payload"]["attempt_count"] == 1
    assert event["payload"]["test_passed"] is True
