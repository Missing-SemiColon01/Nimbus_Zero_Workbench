"""Tests for artifact-generation orchestration in the Industrial Workbench Agent."""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

def _has_reportlab():
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False

def _has_docker():
    try:
        import docker  # noqa: F401
        return True
    except ImportError:
        return False

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
    ):
        tools.register(NamedTool(name))

    from backend.sandbox.executor import build_executor
    from backend.tools.sandbox_tool import SandboxTool
    tools.register(SandboxTool(executor=build_executor()))

    for tool in (extra_tools or {}).values():
        tools.register(tool)

    return IndustrialWorkbenchAgent.create(runtime, tools, _agents_yaml())


# ===========================================================================
# 1. Detection tests
# ===========================================================================


class TestDetectArtifactIntent:
    """Unit tests for the detect_artifact_intent function."""

    def test_report_task_type_defaults_to_docx(self):
        intent = detect_artifact_intent("summarize the findings", task_type="report")
        assert intent is not None
        assert intent.artifact_type == "docx"

    def test_artifact_task_type_defaults_to_docx(self):
        intent = detect_artifact_intent("summarize the findings", task_type="artifact")
        assert intent is not None
        assert intent.artifact_type == "docx"

    def test_report_task_type_with_presentation_keyword(self):
        intent = detect_artifact_intent("create a presentation about safety", task_type="report")
        assert intent is not None
        assert intent.artifact_type == "pptx"

    def test_report_task_type_with_pdf_keyword(self):
        intent = detect_artifact_intent("generate a pdf for the audit", task_type="report")
        assert intent is not None
        assert intent.artifact_type == "pdf"

    def test_report_task_type_with_spreadsheet_keyword(self):
        intent = detect_artifact_intent("create a spreadsheet with inspection data", task_type="artifact")
        assert intent is not None
        assert intent.artifact_type == "xlsx"

    def test_keyword_document_create(self):
        intent = detect_artifact_intent("Generate a report on the equipment status")
        assert intent is not None
        assert intent.artifact_type == "docx"

    def test_keyword_approval_note(self):
        intent = detect_artifact_intent("prepare an approval note for the procurement")
        assert intent is not None
        assert intent.artifact_type == "docx"

    def test_keyword_presentation(self):
        intent = detect_artifact_intent("build a presentation for the board meeting")
        assert intent is not None
        assert intent.artifact_type == "pptx"

    def test_keyword_slides(self):
        intent = detect_artifact_intent("create slides about the new safety protocol")
        assert intent is not None
        assert intent.artifact_type == "pptx"

    def test_keyword_spreadsheet(self):
        intent = detect_artifact_intent("produce an excel workbook with monthly stats")
        assert intent is not None
        assert intent.artifact_type == "xlsx"

    def test_keyword_pdf(self):
        intent = detect_artifact_intent("create a pdf with the inspection summary")
        assert intent is not None
        assert intent.artifact_type == "pdf"

    def test_general_purpose_pitch_deck(self):
        intent = detect_artifact_intent("build a pitch deck for angel investors")
        assert intent is not None
        assert intent.artifact_type == "pptx"

    def test_general_purpose_financial_model(self):
        intent = detect_artifact_intent("create a financial model in excel")
        assert intent is not None
        assert intent.artifact_type == "xlsx"

    def test_general_purpose_budget_sheet(self):
        intent = detect_artifact_intent("prepare a budget sheet for next fiscal year")
        assert intent is not None
        assert intent.artifact_type == "xlsx"

    def test_general_purpose_executive_memo(self):
        intent = detect_artifact_intent("draft an executive memo regarding remote work policy")
        assert intent is not None
        assert intent.artifact_type == "docx"

    def test_general_purpose_proposal(self):
        intent = detect_artifact_intent("write a project proposal for the prospective client")
        assert intent is not None
        assert intent.artifact_type == "docx"

    def test_general_purpose_pdf_export(self):
        intent = detect_artifact_intent("export a pdf summary of the survey results")
        assert intent is not None
        assert intent.artifact_type == "pdf"

    def test_no_artifact_intent(self):
        assert detect_artifact_intent("what is the temperature reading?") is None

    def test_no_artifact_plain_question(self):
        assert detect_artifact_intent("explain how the compressor works") is None

    def test_no_artifact_general_technical_question(self):
        assert detect_artifact_intent("what is the difference between a mutex and a semaphore?") is None

    def test_empty_request(self):
        assert detect_artifact_intent("") is None
        assert detect_artifact_intent("   ") is None

    def test_none_task_type_no_keywords(self):
        assert detect_artifact_intent("list the recent alarms", task_type=None) is None

    def test_unrelated_task_type_no_keywords(self):
        """A non-artifact task_type should not trigger detection by itself."""
        assert detect_artifact_intent("debug this issue", task_type="debugging") is None


# ===========================================================================
# 2. Code-driven artifact generation orchestration tests
# ===========================================================================


class TestGenerateArtifactCodeWorkflow:
    """generate_artifact() routes deliverable requests to CodeArtifactWorkflow."""

    def test_generate_docx_artifact(self, tmp_path: Path):
        code = (
            "from docx import Document\n"
            "doc = Document()\n"
            "doc.add_heading('Safety Audit Report', 0)\n"
            "doc.add_paragraph('All equipment passed inspection.')\n"
            "doc.save('report.docx')\n"
        )
        provider = StubProvider(content=f"```python\n{code}```")
        agent = _build_agent(tmp_path, provider)

        result = asyncio.run(
            agent.generate_artifact(
                "Generate a report on safety audit findings",
                task_type="report",
            )
        )

        assert isinstance(result, ArtifactGenerationResult)
        assert result.artifact_type == "docx"
        assert result.status == "completed"
        assert result.path is not None
        assert result.generation_mode == "code"
        assert Path(result.path).exists()
        assert result.task_id

    def test_generate_presentation_artifact(self, tmp_path: Path):
        code = (
            "from pptx import Presentation\n"
            "prs = Presentation()\n"
            "slide = prs.slides.add_slide(prs.slide_layouts[0])\n"
            "slide.shapes.title.text = 'Q3 Safety Review'\n"
            "prs.save('presentation.pptx')\n"
        )
        provider = StubProvider(content=f"```python\n{code}```")
        agent = _build_agent(tmp_path, provider)

        result = asyncio.run(
            agent.generate_artifact(
                "Create a presentation about Q3 safety",
                task_type="presentation",
            )
        )

        assert isinstance(result, ArtifactGenerationResult)
        assert result.artifact_type == "pptx"
        assert result.status == "completed"
        assert result.path is not None
        assert result.generation_mode == "code"
        assert Path(result.path).exists()

    def test_generate_spreadsheet_artifact(self, tmp_path: Path):
        code = (
            "import openpyxl\n"
            "wb = openpyxl.Workbook()\n"
            "ws = wb.active\n"
            "ws['A1'] = 'Sensor'\n"
            "ws['B1'] = 'Reading'\n"
            "ws['A2'] = 'Temp'\n"
            "ws['B2'] = 72\n"
            "wb.save('readings.xlsx')\n"
        )
        provider = StubProvider(content=f"```python\n{code}```")
        agent = _build_agent(tmp_path, provider)

        result = asyncio.run(
            agent.generate_artifact(
                "Generate a spreadsheet with sensor readings",
            )
        )

        assert isinstance(result, ArtifactGenerationResult)
        assert result.artifact_type == "xlsx"
        assert result.status == "completed"
        assert result.path is not None
        assert result.generation_mode == "code"
        assert Path(result.path).exists()

    @pytest.mark.skipif(not _has_reportlab(), reason="reportlab not installed, PDF generation requires Docker sandbox")
    def test_generate_pdf_artifact(self, tmp_path: Path):
        code = (
            "from reportlab.platypus import SimpleDocTemplate, Paragraph\n"
            "from reportlab.lib.styles import getSampleStyleSheet\n"
            "doc = SimpleDocTemplate('report.pdf')\n"
            "styles = getSampleStyleSheet()\n"
            "doc.build([Paragraph('Valve Inspection Audit', styles['Title'])])\n"
        )
        provider = StubProvider(content=f"```python\n{code}```")
        agent = _build_agent(tmp_path, provider)

        result = asyncio.run(
            agent.generate_artifact(
                "Create a pdf report on valve inspection",
            )
        )

        assert isinstance(result, ArtifactGenerationResult)
        assert result.artifact_type == "pdf"
        assert result.status == "completed"
        assert result.path is not None
        assert result.generation_mode == "code"
        assert Path(result.path).exists()


# ===========================================================================
# 3. Failure-case tests
# ===========================================================================


class TestGenerateArtifactFailures:
    """Verify failure modes in code artifact generation return structured results."""

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

    def test_code_execution_failure(self, tmp_path: Path):
        """When the generated code fails execution across retries, result is failed."""
        code = "raise RuntimeError('Script execution failure')"
        provider = StubProvider(content=f"```python\n{code}```")
        agent = _build_agent(tmp_path, provider)

        result = asyncio.run(
            agent.generate_artifact(
                "Generate a report on the test",
                task_type="report",
            )
        )

        assert result.status == "failed"
        assert result.artifact_type == "docx"
        assert result.generation_mode == "code"
        assert len(result.errors) >= 1

    def test_model_generation_exception(self, tmp_path: Path):
        """When model generation raises, generate_artifact catches and returns failed."""
        provider = FailingProvider()
        agent = _build_agent(tmp_path, provider)

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
        r = ArtifactGenerationResult(task_id="t1", artifact_type="docx", status="completed")
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
            artifact_type="xlsx",
            status="failed",
            errors=["disk full"],
        )
        data = r.model_dump(mode="json")
        restored = ArtifactGenerationResult.model_validate(data)
        assert restored == r


# ===========================================================================
# 5. Multi-attempt repair loop tests
# ===========================================================================


class MultiAttemptRepairProvider(ModelProvider):
    """Provider that yields bad code on attempt 1 and working code on attempt 2."""

    def __init__(self, bad_code: str, good_code: str):
        self.bad_code = bad_code
        self.good_code = good_code
        self.prompts: list[str] = []

    async def generate(self, model: ModelDefinition, request: Any) -> ModelResponse:
        self.prompts.append(request.prompt)
        if len(self.prompts) == 1:
            return ModelResponse(
                content=f"```python\n{self.bad_code}\n```",
                model_id=model.id,
            )
        return ModelResponse(
            content=f"```python\n{self.good_code}\n```",
            model_id=model.id,
        )


class TestCodeArtifactWorkflowRepair:
    """Verify that CodeArtifactWorkflow feeds errors and validation back into repair attempts."""

    def test_workflow_repairs_after_runtime_error(self, tmp_path: Path):
        bad_code = "raise ValueError('Initial code buggy')"
        good_code = (
            "from docx import Document\n"
            "doc = Document()\n"
            "doc.add_heading('Repaired Report', 0)\n"
            "doc.add_paragraph('Successfully generated on attempt 2.')\n"
            "doc.save('report.docx')\n"
        )
        provider = MultiAttemptRepairProvider(bad_code=bad_code, good_code=good_code)
        agent = _build_agent(tmp_path, provider)

        result = asyncio.run(
            agent.generate_artifact("Generate an audit report", task_type="report")
        )

        assert result.status == "completed"
        assert result.artifact_type == "docx"
        assert Path(result.path).exists()
        assert len(provider.prompts) == 2
        # Verify the repair prompt received the error traceback / feedback
        assert "PREVIOUS ATTEMPT FAILED" in provider.prompts[1]
        assert "Initial code buggy" in provider.prompts[1]
        assert "REPAIR INSTRUCTIONS" in provider.prompts[1]

    def test_workflow_repairs_after_validation_failure(self, tmp_path: Path):
        """Attempt 1 creates an empty document; attempt 2 adds required content."""
        empty_code = (
            "from docx import Document\n"
            "doc = Document()\n"
            "doc.save('report.docx')\n"
        )
        good_code = (
            "from docx import Document\n"
            "doc = Document()\n"
            "doc.add_paragraph('Non-empty content is now provided.')\n"
            "doc.save('report.docx')\n"
        )
        provider = MultiAttemptRepairProvider(bad_code=empty_code, good_code=good_code)
        agent = _build_agent(tmp_path, provider)

        result = asyncio.run(
            agent.generate_artifact("Generate a document", task_type="report")
        )

        assert result.status == "completed"
        assert len(provider.prompts) == 2
        assert "PREVIOUS ATTEMPT FAILED" in provider.prompts[1]
        assert "Artifact has no readable content" in provider.prompts[1]

