"""
tests/test_multimodal_pdf_vision.py
====================================
Tests for:
1. Automatic scanned-PDF page rendering (PyMuPDF fitz).
2. Sending rendered pages to vision.analyze.
3. Combining OCR and vision results into a structured output.
4. Returning the combined result through IndustrialWorkbenchAgent.
5. Scenarios covering scanned PDFs, diagrams, and equipment photos.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from unittest.mock import AsyncMock, patch

import fitz
import pytest
from PIL import Image

from backend.agents.industrial_workbench import AGENT_ID, IndustrialWorkbenchAgent
from backend.agents.runtime import AgentRuntime
from backend.knowledge.ocr import OCRResult
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider, ModelProviderRegistry
from backend.models.registry import ModelRegistry
from backend.models.router import ModelRouter
from backend.tools.contracts import ToolResult
from backend.tools.registry import ToolRegistry
from backend.tools.vision_tool import (
    VisionAnalyzeTool,
    encode_image_to_base64,
    render_pdf_page_to_image,
)

SAMPLE_DIR = Path("tests/sample-pdf")


class MockVisionProvider(ModelProvider):
    """Deterministic mock provider for vision testing."""

    def __init__(self, response_text: str = "VISUAL INSPECTION: Safety valve shows surface oxidation, dial reads 120 PSI."):
        self.response_text = response_text
        self.calls: list[tuple[ModelDefinition, ModelRequest]] = []

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        self.calls.append((model, request))
        return ModelResponse(
            content=self.response_text,
            model_id=model.id,
            raw={"usage": {"prompt_tokens": 50, "completion_tokens": 20}},
        )


def _create_sample_diagram(path: Path) -> Path:
    """Create a mock schematic/diagram image with text markings."""
    img = Image.new("RGB", (300, 200), color=(255, 255, 255))
    img.save(path, format="PNG")
    return path


def _create_sample_equipment_photo(path: Path) -> Path:
    """Create a mock equipment photo."""
    img = Image.new("RGB", (400, 300), color=(100, 100, 100))
    img.save(path, format="JPEG")
    return path


@pytest.fixture
def mock_vision_provider():
    return MockVisionProvider()


@pytest.fixture
def vision_tool(mock_vision_provider):
    return VisionAnalyzeTool(provider=mock_vision_provider)


class TestPDFRenderingAndEncoding:
    """Tests automatic rendering of PDF pages to images."""

    def test_render_pdf_page_to_image(self):
        sample_pdf = SAMPLE_DIR / "sample-scanned.pdf"
        assert sample_pdf.exists()

        png_bytes = render_pdf_page_to_image(sample_pdf, page_number=1, dpi=150)
        assert isinstance(png_bytes, bytes)
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    def test_render_pdf_page_out_of_bounds_raises(self):
        sample_pdf = SAMPLE_DIR / "sample-scanned.pdf"
        with pytest.raises(ValueError, match="out of range"):
            render_pdf_page_to_image(sample_pdf, page_number=999)

    def test_encode_image_to_base64_with_pdf(self):
        sample_pdf = SAMPLE_DIR / "sample-scanned.pdf"
        b64 = encode_image_to_base64(sample_pdf)
        assert isinstance(b64, str)
        decoded = base64.b64decode(b64)
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"


class TestVisionAnalyzeScannedPDFAndCombination:
    """Tests executing vision.analyze with scanned PDFs, combining OCR and vision."""

    @pytest.mark.asyncio
    async def test_scanned_pdf_renders_and_combines_ocr_and_vision(self, vision_tool, mock_vision_provider):
        sample_pdf = SAMPLE_DIR / "sample-scanned.pdf"
        assert sample_pdf.exists()

        def mock_ocr(img, **kwargs):
            return OCRResult(
                text="STAMP: VERIFIED PASS\nSERIAL: SV-8942\nTEST PRESSURE: 135 PSI",
                is_available=True,
                confidence=95.0,
                engine="tesseract",
            )

        with patch("backend.tools.vision_tool.ocr_image", side_effect=mock_ocr):
            result: ToolResult = await vision_tool.execute(
                {
                    "image_path": str(sample_pdf),
                    "prompt": "Inspect this scanned PDF report for inspection stamps and pressure readings.",
                    "page_number": 1,
                },
                context={},
            )

        assert result.success is True
        output = result.output
        assert output["is_pdf"] is True
        assert output["page_number"] == 1
        assert "STAMP: VERIFIED PASS" in output["ocr_text"]
        assert "VISUAL INSPECTION" in output["analysis"]
        assert "OCR Transcription" in output["combined_result"]
        assert "Visual Analysis" in output["combined_result"]

        # Check model request prompt was enriched with OCR
        assert len(mock_vision_provider.calls) == 1
        _, req = mock_vision_provider.calls[0]
        assert "[Transcribed Text from OCR]:" in req.prompt
        assert "SERIAL: SV-8942" in req.prompt
        assert len(req.images) == 1


class TestDiagramsAndEquipmentPhotos:
    """Tests visual inspection and OCR combination on diagrams and equipment photos."""

    @pytest.mark.asyncio
    async def test_diagram_inspection_with_ocr_and_vision(self, vision_tool, mock_vision_provider, tmp_path: Path):
        diagram_path = _create_sample_diagram(tmp_path / "piping_schematic.png")

        def mock_ocr(img, **kwargs):
            return OCRResult(
                text="VALVE V-101 | FLOW DIRECTION -> | P&ID SCHEMATIC 401-B",
                is_available=True,
                confidence=92.0,
                engine="tesseract",
            )

        mock_vision_provider.response_text = "DIAGRAM ANALYSIS: Component V-101 is located between pump P-1 and manifold M-3."

        with patch("backend.tools.vision_tool.ocr_image", side_effect=mock_ocr):
            result: ToolResult = await vision_tool.execute(
                {
                    "image_path": str(diagram_path),
                    "prompt": "Identify components and labels in this piping diagram.",
                },
                context={},
            )

        assert result.success is True
        output = result.output
        assert "VALVE V-101" in output["ocr_text"]
        assert "DIAGRAM ANALYSIS" in output["analysis"]
        assert "OCR Transcription:" in output["combined_result"]
        assert "Visual Analysis:" in output["combined_result"]

    @pytest.mark.asyncio
    async def test_equipment_photo_defect_analysis(self, vision_tool, mock_vision_provider, tmp_path: Path):
        photo_path = _create_sample_equipment_photo(tmp_path / "pump_casing.jpg")

        def mock_ocr(img, **kwargs):
            return OCRResult(
                text="TAG: ACME-PUMP-900",
                is_available=True,
                confidence=88.0,
                engine="tesseract",
            )

        mock_vision_provider.response_text = "PHOTO INSPECTION: Hairline crack observed near the flange bolt; seal shows minor weeping."

        with patch("backend.tools.vision_tool.ocr_image", side_effect=mock_ocr):
            result: ToolResult = await vision_tool.execute(
                {
                    "image_path": str(photo_path),
                    "prompt": "Assess this pump photo for physical wear, cracks, or leaks.",
                },
                context={},
            )

        assert result.success is True
        output = result.output
        assert "TAG: ACME-PUMP-900" in output["ocr_text"]
        assert "Hairline crack" in output["analysis"]
        assert "OCR Transcription" in output["combined_result"]


class TestIndustrialWorkbenchAgentMultimodalReturn:
    """Tests returning the combined OCR + vision result through IndustrialWorkbenchAgent."""

    @pytest.mark.asyncio
    async def test_agent_inspect_multimodal_scanned_pdf(self, tmp_path: Path):
        sample_pdf = SAMPLE_DIR / "sample-scanned.pdf"
        assert sample_pdf.exists()

        models_config = tmp_path / "models.yaml"
        models_config.write_text(
            """models:
  - id: vision
    runtime: fake
    model: test-vision
    capabilities: [vision, document_understanding]
    modalities: [text, image, document]
"""
        )

        mock_provider = MockVisionProvider(
            response_text="INSPECTION REPORT: Certified compliance with safety margins."
        )

        runtime = AgentRuntime(
            ModelRouter(ModelRegistry(models_config)),
            ModelProviderRegistry({"fake": mock_provider}),
        )

        tools = ToolRegistry()
        vision_tool = VisionAnalyzeTool(
            provider=ModelProviderRegistry({"fake": mock_provider}),
            registry=ModelRegistry(models_config),
        )
        tools.register(vision_tool)

        class NamedTool:
            def __init__(self, name: str):
                self.name = name

        for tool_name in (
            "rag.search",
            "document.create",
            "spreadsheet.create",
            "presentation.create",
            "pdf.create",
            "artifact.validate",
            "sandbox.execute",
        ):
            tools.register(NamedTool(tool_name))  # type: ignore

        config_path = Path("configs/agents.yaml")
        agent = IndustrialWorkbenchAgent.create(runtime, tools, config_path)

        def mock_ocr(img, **kwargs):
            return OCRResult(
                text="CERTIFIED INSPECTION: BOILER #4\nOPERATIONAL STATUS: NORMAL",
                is_available=True,
                confidence=98.0,
                engine="tesseract",
            )

        with patch("backend.tools.vision_tool.ocr_image", side_effect=mock_ocr):
            state, response = await agent.inspect_multimodal(
                "Review this scanned document and provide findings",
                document_path=sample_pdf,
                page_number=1,
            )

        assert state.status == "completed"
        assert response.content == "INSPECTION REPORT: Certified compliance with safety margins."
        # Verify the agent prompt received both OCR and Vision analysis
        assert len(mock_provider.calls) >= 1
        agent_call_prompt = mock_provider.calls[-1][1].prompt
        assert "BOILER #4" in agent_call_prompt
        assert "INSPECTION REPORT" in agent_call_prompt

