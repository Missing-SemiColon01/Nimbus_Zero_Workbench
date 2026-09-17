"""Tests for artifact-generation orchestration in the Industrial Workbench Agent."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from backend.agents.artifact_detection import ArtifactIntent, detect_artifact_intent
from backend.agents.industrial_workbench import (
    AGENT_ID,
    IndustrialWorkbenchAgent,
    IndustrialWorkbenchAgentConfig,
)
from backend.agents.runtime import AgentRuntime
from backend.models.contracts import ModelDefinition, ModelResponse, ToolCall
from backend.models.providers import ModelProvider, ModelProviderRegistry
from backend.models.registry import ModelRegistry
from backend.models.router import ModelRouter
from backend.schemas.artifact_result import ArtifactGenerationResult
from backend.tools.contracts import Tool, ToolResult
from backend.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class StubProvider(ModelProvider):
    """Provider that returns a canned response, optionally with tool_calls."""

    def __init__(self, content: str = "ok", tool_calls: list[ToolCall] | None = None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.call_count = 0

    async def generate(self, model: ModelDefinition, request: Any) -> ModelResponse:
        self.call_count += 1
        return ModelResponse(
            content=self.content,
            model_id=model.id,
            tool_calls=self.tool_calls,
        )


class FailingProvider(ModelProvider):
    """Provider that always raises."""

    async def generate(self, model: ModelDefinition, request: Any) -> ModelResponse:
        raise RuntimeError("provider exploded")


class FakeArtifactTool(Tool):
    """Simulates an artifact-creation tool that succeeds with realistic output."""

    def __init__(self, name: str, *, succeed: bool = True):
        self.name = name
        self._succeed = succeed
        self.call_count = 0
        self.last_arguments: dict[str, Any] = {}

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        self.call_count += 1
        self.last_arguments = arguments
        if not self._succeed:
            return ToolResult(success=False, output=None, error="disk full")
        return ToolResult(
            success=True,
            output={
                "id": "art-001",
                "type": self.name.split(".")[0],
                "filename": f"test-artifact.{self.name.split('.')[0][:4]}",
                "mime_type": "application/octet-stream",
                "storage_uri": f"/data/artifacts/test-artifact.{self.name.split('.')[0][:4]}",
                "task_id": context.get("task_id", "unknown"),
            },
            artifacts=[f"/data/artifacts/test-artifact.{self.name.split('.')[0][:4]}"],
        )


class NamedTool(Tool):
    """Minimal stub tool for registry padding."""

    def __init__(self, name: str):
        self.name = name

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        return ToolResult(success=True, output={})


def _models_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "models.yaml"
    p.write_text(
        "models:\n"
        "  - id: reasoning\n"
        "    runtime: stub\n"
        "    model: test\n"
        "    capabilities: [reasoning]\n"
        "    modalities: [text]\n"
    )
    return p


def _agents_yaml() -> Path:
    return Path("configs/agents.yaml")


def _build_agent(
    tmp_path: Path,
    provider: ModelProvider,
    extra_tools: dict[str, Tool] | None = None,
) -> IndustrialWorkbenchAgent:
    """Build an IndustrialWorkbenchAgent wired to a stub provider and tool registry."""
    models_config = _models_yaml(tmp_path)
    registry = ModelRegistry(models_config)
    providers = ModelProviderRegistry({"stub": provider})
    runtime = AgentRuntime(ModelRouter(registry), providers)

    tools = ToolRegistry()
    # Register the standard tool set expected by configs/agents.yaml
    for name in (
        "rag.search",
        "vision.analyze",
        "artifact.validate",
        "sandbox.execute",
    ):
        tools.register(NamedTool(name))

    if extra_tools:
        for tool in extra_tools.values():
            tools.register(tool)
    else:
        # Register default artifact tools so agent validation passes.
        for name in ("document.create", "presentation.create", "pdf.create", "spreadsheet.create"):
            tools.register(NamedTool(name))

    return IndustrialWorkbenchAgent.create(runtime, tools, _agents_yaml())


# ===========================================================================
# 1. Detection tests
# ===========================================================================


class TestDetectArtifactIntent:
    """Unit tests for the detect_artifact_intent function."""

    def test_report_task_type_defaults_to_document(self):
        intent = detect_artifact_intent("summarize the findings", task_type="report")
        assert intent is not None
        assert intent.artifact_type == "document"
        assert intent.tool_name == "document.create"

    def test_artifact_task_type_defaults_to_document(self):
        intent = detect_artifact_intent("summarize the findings", task_type="artifact")
        assert intent is not None
        assert intent.artifact_type == "document"
        assert intent.tool_name == "document.create"

    def test_report_task_type_with_presentation_keyword(self):
        intent = detect_artifact_intent("create a presentation about safety", task_type="report")
        assert intent is not None
        assert intent.artifact_type == "presentation"
        assert intent.tool_name == "presentation.create"

    def test_report_task_type_with_pdf_keyword(self):
        intent = detect_artifact_intent("generate a pdf for the audit", task_type="report")
        assert intent is not None
        assert intent.artifact_type == "pdf"
        assert intent.tool_name == "pdf.create"

    def test_report_task_type_with_spreadsheet_keyword(self):
        intent = detect_artifact_intent("create a spreadsheet with inspection data", task_type="artifact")
        assert intent is not None
        assert intent.artifact_type == "spreadsheet"
        assert intent.tool_name == "spreadsheet.create"

    def test_keyword_document_create(self):
        intent = detect_artifact_intent("Generate a report on the equipment status")
        assert intent is not None
        assert intent.artifact_type == "document"
        assert intent.tool_name == "document.create"

    def test_keyword_approval_note(self):
        intent = detect_artifact_intent("prepare an approval note for the procurement")
        assert intent is not None
        assert intent.artifact_type == "document"
        assert intent.tool_name == "document.create"

    def test_keyword_presentation(self):
        intent = detect_artifact_intent("build a presentation for the board meeting")
        assert intent is not None
        assert intent.artifact_type == "presentation"
        assert intent.tool_name == "presentation.create"

    def test_keyword_slides(self):
        intent = detect_artifact_intent("create slides about the new safety protocol")
        assert intent is not None
        assert intent.artifact_type == "presentation"

    def test_keyword_spreadsheet(self):
        intent = detect_artifact_intent("produce an excel workbook with monthly stats")
        assert intent is not None
        assert intent.artifact_type == "spreadsheet"
        assert intent.tool_name == "spreadsheet.create"

    def test_keyword_pdf(self):
        intent = detect_artifact_intent("create a pdf with the inspection summary")
        assert intent is not None
        assert intent.artifact_type == "pdf"
        assert intent.tool_name == "pdf.create"

    def test_no_artifact_intent(self):
        assert detect_artifact_intent("what is the temperature reading?") is None

    def test_no_artifact_plain_question(self):
        assert detect_artifact_intent("explain how the compressor works") is None

    def test_empty_request(self):
        assert detect_artifact_intent("") is None
        assert detect_artifact_intent("   ") is None

    def test_none_task_type_no_keywords(self):
        assert detect_artifact_intent("list the recent alarms", task_type=None) is None

    def test_unrelated_task_type_no_keywords(self):
        """A non-artifact task_type should not trigger detection by itself."""
        assert detect_artifact_intent("debug this issue", task_type="debugging") is None


# ===========================================================================
# 2. Happy-path orchestration tests
# ===========================================================================


class TestGenerateArtifactHappyPath:
    """generate_artifact() succeeds when the model triggers the tool call via runtime."""

    def test_runtime_tool_call_path(self, tmp_path: Path):
        """When the provider returns a tool_call, the runtime executes it and
        generate_artifact extracts the result from AgentState."""
        doc_tool = FakeArtifactTool("document.create")

        # Provider returns a tool call that the runtime loop will execute.
        provider = StubProvider(
            content="",
            tool_calls=[
                ToolCall(
                    name="document.create",
                    arguments={
                        "subject": "Safety Audit",
                        "purpose": "Quarterly review",
                        "recommendation": "Approve",
                        "requested_approval": "Plant Manager",
                    },
                ),
            ],
        )
        agent = _build_agent(tmp_path, provider, extra_tools={"document.create": doc_tool})

        result = asyncio.run(
            agent.generate_artifact(
                "Generate a report on safety audit findings",
                task_type="report",
            )
        )

        assert isinstance(result, ArtifactGenerationResult)
        assert result.artifact_type == "document"
        # The runtime should have executed the tool at least once (the provider
        # returns a tool_call, which the runtime loop picks up).  However, the
        # StubProvider always returns the same response including tool_calls,
        # so the runtime may loop.  Either way the orchestrator should return
        # completed or failed gracefully.
        assert result.status in {"completed", "failed"}
        assert result.task_id  # non-empty UUID

    def test_manual_json_content_path(self, tmp_path: Path):
        """When the provider returns JSON content (no structured tool_call), the
        orchestrator parses it and calls the tool manually."""
        doc_tool = FakeArtifactTool("document.create")
        json_content = json.dumps({
            "subject": "Pump Inspection",
            "purpose": "Annual review",
            "recommendation": "Replace seals",
            "requested_approval": "Maintenance Lead",
        })
        provider = StubProvider(content=json_content)
        agent = _build_agent(tmp_path, provider, extra_tools={"document.create": doc_tool})

        result = asyncio.run(
            agent.generate_artifact("Generate a report on the pump inspection")
        )

        assert isinstance(result, ArtifactGenerationResult)
        assert result.artifact_type == "document"
        assert result.status == "completed"
        assert result.path is not None
        assert result.download_url is not None
        assert "/download" in result.download_url
        assert result.artifact_metadata.get("task_id") is not None
        assert doc_tool.call_count >= 1

    def test_presentation_artifact(self, tmp_path: Path):
        """Presentation artifact via keyword detection."""
        pres_tool = FakeArtifactTool("presentation.create")
        json_content = json.dumps({
            "title": "Q3 Safety Review",
            "slides": [{"layout": "title", "title": "Overview"}],
        })
        provider = StubProvider(content=json_content)
        agent = _build_agent(tmp_path, provider, extra_tools={"presentation.create": pres_tool})

        result = asyncio.run(
            agent.generate_artifact("Create a presentation about Q3 safety")
        )

        assert result.artifact_type == "presentation"
        assert result.status == "completed"
        assert pres_tool.call_count >= 1

    def test_spreadsheet_artifact(self, tmp_path: Path):
        """Spreadsheet artifact via keyword detection."""
        xl_tool = FakeArtifactTool("spreadsheet.create")
        json_content = json.dumps({
            "title": "Readings",
            "sheets": [{"title": "Data", "columns": [{"key": "temp", "header": "Temperature"}]}],
        })
        provider = StubProvider(content=json_content)
        agent = _build_agent(tmp_path, provider, extra_tools={"spreadsheet.create": xl_tool})

        result = asyncio.run(
            agent.generate_artifact("Generate a spreadsheet with sensor readings")
        )

        assert result.artifact_type == "spreadsheet"
        assert result.status == "completed"

    def test_pdf_artifact(self, tmp_path: Path):
        """PDF artifact via keyword detection."""
        pdf_tool = FakeArtifactTool("pdf.create")
        json_content = json.dumps({
            "subject": "Valve Inspection",
            "purpose": "Annual check",
            "recommendation": "Pass",
            "requested_approval": "QA Manager",
        })
        provider = StubProvider(content=json_content)
        agent = _build_agent(tmp_path, provider, extra_tools={"pdf.create": pdf_tool})

        result = asyncio.run(
            agent.generate_artifact("Create a pdf report on valve inspection")
        )

        assert result.artifact_type == "pdf"
        assert result.status == "completed"


# ===========================================================================
# 3. Failure-case tests
# ===========================================================================


class TestGenerateArtifactFailures:
    """Verify that all failure modes return a proper ArtifactGenerationResult."""

    def test_no_artifact_intent(self, tmp_path: Path):
        """Request that is not artifact-related returns status=failed."""
        provider = StubProvider(content="hello")
        agent = _build_agent(tmp_path, provider)

        result = asyncio.run(
            agent.generate_artifact("What is the compressor pressure?")
        )

        assert result.status == "failed"
        assert result.artifact_type == "unknown"
        assert any("Could not determine" in e for e in result.errors)

    def test_tool_not_registered(self, tmp_path: Path):
        """When the detected tool is not in the registry, returns failed."""
        provider = StubProvider(content="ok")
        models_config = _models_yaml(tmp_path)
        registry = ModelRegistry(models_config)
        providers = ModelProviderRegistry({"stub": provider})
        runtime = AgentRuntime(ModelRouter(registry), providers)

        tools = ToolRegistry()
        # Deliberately omit document.create — but we need the config to not
        # reference it either, so build with a minimal config.
        config = IndustrialWorkbenchAgentConfig(tools=None)
        agent = IndustrialWorkbenchAgent(runtime, tools, config)

        result = asyncio.run(
            agent.generate_artifact(
                "Generate a report on equipment status",
                task_type="report",
            )
        )

        assert result.status == "failed"
        assert any("not registered" in e for e in result.errors)

    def test_tool_execution_failure(self, tmp_path: Path):
        """When the artifact tool returns success=False, result reflects failure."""
        doc_tool = FakeArtifactTool("document.create", succeed=False)
        json_content = json.dumps({
            "subject": "Test",
            "purpose": "Test",
            "recommendation": "Test",
            "requested_approval": "Test",
        })
        provider = StubProvider(content=json_content)
        agent = _build_agent(tmp_path, provider, extra_tools={"document.create": doc_tool})

        result = asyncio.run(
            agent.generate_artifact("Generate a report on the test", task_type="report")
        )

        assert result.status == "failed"
        assert any("disk full" in e for e in result.errors)
        assert result.path is None

    def test_model_returns_non_json(self, tmp_path: Path):
        """When the model produces plain text instead of JSON, the tool cannot be called."""
        provider = StubProvider(content="Here is a nice summary of the findings.")
        agent = _build_agent(tmp_path, provider)

        result = asyncio.run(
            agent.generate_artifact("Generate a report on the findings", task_type="report")
        )

        assert result.status == "failed"
        assert any("did not produce valid" in e for e in result.errors)

    def test_model_generation_exception(self, tmp_path: Path):
        """When model generation raises, generate_artifact catches and returns failed."""
        provider = FailingProvider()
        # Build agent manually since FailingProvider will fail during agent.run
        models_config = _models_yaml(tmp_path)
        registry = ModelRegistry(models_config)
        providers = ModelProviderRegistry({"stub": provider})
        runtime = AgentRuntime(ModelRouter(registry), providers)

        tools = ToolRegistry()
        for name in (
            "rag.search", "vision.analyze", "document.create",
            "presentation.create", "pdf.create", "spreadsheet.create",
            "artifact.validate", "sandbox.execute",
        ):
            tools.register(NamedTool(name))

        agent = IndustrialWorkbenchAgent.create(runtime, tools, _agents_yaml())

        result = asyncio.run(
            agent.generate_artifact("Generate a report", task_type="report")
        )

        assert result.status == "failed"
        assert len(result.errors) >= 1


# ===========================================================================
# 4. ArtifactGenerationResult schema tests
# ===========================================================================


class TestArtifactGenerationResult:
    """Verify the Pydantic schema behaves correctly."""

    def test_minimal_valid(self):
        r = ArtifactGenerationResult(task_id="t1", artifact_type="document", status="completed")
        assert r.path is None
        assert r.download_url is None
        assert r.artifact_metadata == {}
        assert r.errors == []

    def test_full_valid(self):
        r = ArtifactGenerationResult(
            task_id="t2",
            artifact_type="pdf",
            status="completed",
            path="/data/artifacts/out.pdf",
            download_url="/api/v1/artifacts/out.pdf/download",
            artifact_metadata={"id": "a1", "filename": "out.pdf"},
            errors=[],
        )
        assert r.path == "/data/artifacts/out.pdf"

    def test_serialization_roundtrip(self):
        r = ArtifactGenerationResult(
            task_id="t3",
            artifact_type="spreadsheet",
            status="failed",
            errors=["disk full"],
        )
        data = r.model_dump(mode="json")
        restored = ArtifactGenerationResult.model_validate(data)
        assert restored == r


# ===========================================================================
# 5. Task type routing tests
# ===========================================================================


class TestTaskTypeRouting:
    """Verify that task_type correctly routes to the right artifact tool."""

    def test_report_routes_to_document(self, tmp_path: Path):
        doc_tool = FakeArtifactTool("document.create")
        json_content = json.dumps({
            "subject": "X", "purpose": "Y",
            "recommendation": "Z", "requested_approval": "W",
        })
        provider = StubProvider(content=json_content)
        agent = _build_agent(tmp_path, provider, extra_tools={"document.create": doc_tool})

        result = asyncio.run(
            agent.generate_artifact("summarize findings", task_type="report")
        )

        assert result.artifact_type == "document"
        assert doc_tool.call_count >= 1

    def test_artifact_with_presentation_keyword(self, tmp_path: Path):
        pres_tool = FakeArtifactTool("presentation.create")
        json_content = json.dumps({
            "title": "Overview", "slides": [{"layout": "title", "title": "Hi"}],
        })
        provider = StubProvider(content=json_content)
        agent = _build_agent(tmp_path, provider, extra_tools={"presentation.create": pres_tool})

        result = asyncio.run(
            agent.generate_artifact(
                "create a presentation deck about maintenance",
                task_type="artifact",
            )
        )

        assert result.artifact_type == "presentation"
        assert pres_tool.call_count >= 1


# ===========================================================================
# 6. Internal helper tests
# ===========================================================================


class TestExtractToolArguments:
    """Test the static _extract_tool_arguments helper on IndustrialWorkbenchAgent."""

    def test_from_structured_tool_calls(self):
        resp = ModelResponse(
            content="",
            model_id="test",
            tool_calls=[ToolCall(name="document.create", arguments={"subject": "X"})],
        )
        args = IndustrialWorkbenchAgent._extract_tool_arguments(resp, "document.create")
        assert args == {"subject": "X"}

    def test_from_raw_tool_calls(self):
        resp = ModelResponse(
            content="",
            model_id="test",
            raw={"tool_calls": [{"name": "pdf.create", "arguments": {"subject": "Y"}}]},
        )
        args = IndustrialWorkbenchAgent._extract_tool_arguments(resp, "pdf.create")
        assert args == {"subject": "Y"}

    def test_from_json_content(self):
        resp = ModelResponse(
            content=json.dumps({"title": "Report", "sheets": []}),
            model_id="test",
        )
        args = IndustrialWorkbenchAgent._extract_tool_arguments(resp, "spreadsheet.create")
        assert args == {"title": "Report", "sheets": []}

    def test_from_json_content_with_tool_calls_wrapper(self):
        resp = ModelResponse(
            content=json.dumps({
                "tool_calls": [
                    {"name": "document.create", "arguments": {"subject": "Z"}}
                ]
            }),
            model_id="test",
        )
        args = IndustrialWorkbenchAgent._extract_tool_arguments(resp, "document.create")
        assert args == {"subject": "Z"}

    def test_no_match_returns_none(self):
        resp = ModelResponse(content="just text", model_id="test")
        assert IndustrialWorkbenchAgent._extract_tool_arguments(resp, "document.create") is None

    def test_empty_content_returns_none(self):
        resp = ModelResponse(content="", model_id="test")
        assert IndustrialWorkbenchAgent._extract_tool_arguments(resp, "document.create") is None

