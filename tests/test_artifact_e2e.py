"""
tests/test_artifact_e2e.py
==========================
End-to-End Artifact Generation and Validation Pipeline:
1. Ingest inspection document with OCR / parse findings.
2. Extract multi-modal findings (visual anomaly + text citations).
3. Transform findings into structured specs (ApprovalNoteSpec, PresentationSpec).
4. Create DOCX, PDF, and PPTX artifacts via ToolRegistry adapters (document.create, pdf.create, presentation.create).
5. Validate each generated artifact using artifact.validate (structural integrity + preview rendering).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.artifacts.contracts import Artifact
from backend.knowledge.embedder import get_embedder
from backend.knowledge.ocr import OCRResult
from backend.knowledge.retriever import KnowledgeRetriever
from backend.knowledge.vector_store import VectorStore
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider
from backend.tools.contracts import ToolResult
from backend.tools.registry import ToolRegistry
from backend.tools.setup import build_tool_registry

SAMPLE_DIR = Path("tests/sample-pdf")


class MockVisionProvider(ModelProvider):
    """Deterministic mock provider for vision testing."""

    def __init__(self, response_text: str = "VISUAL INSPECTION: Stamp detected. Surface shows minor oxidation, no structural cracks."):
        self.response_text = response_text

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content=self.response_text,
            model_id=model.id,
            raw={"usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70}},
        )


@pytest.fixture(scope="module")
def shared_embedder():
    embedder = get_embedder()
    embedder.load()
    return embedder


@pytest.fixture
def isolated_retriever(shared_embedder):
    store = VectorStore(
        collection_name="test_artifact_e2e_knowledge",
        storage_path=":memory:",
        embedder=shared_embedder,
    )
    return KnowledgeRetriever(vector_store=store, embedder=shared_embedder)


@pytest.fixture
def test_tool_registry(isolated_retriever, tmp_path: Path):
    """Build registry configured with isolated temporary directories for artifacts and previews."""
    from backend.artifacts.tools import DocumentCreateTool, PdfCreateTool, PresentationCreateTool
    from backend.artifacts.validation_tool import ArtifactValidateTool
    from backend.tools.rag_tool import RAGSearchTool
    from backend.tools.vision_tool import VisionAnalyzeTool

    registry = ToolRegistry()
    registry.register(RAGSearchTool(retriever=isolated_retriever))
    registry.register(VisionAnalyzeTool(provider=MockVisionProvider(), registry=None))

    artifact_dir = tmp_path / "artifacts"
    preview_dir = tmp_path / "previews"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    registry.register(DocumentCreateTool(artifact_dir))
    registry.register(PresentationCreateTool(artifact_dir))
    registry.register(PdfCreateTool(artifact_dir))
    registry.register(ArtifactValidateTool(preview_dir))
    return registry


def test_end_to_end_inspection_to_artifacts_and_validation(
    isolated_retriever: KnowledgeRetriever,
    test_tool_registry: ToolRegistry,
    tmp_path: Path,
):
    import asyncio

    async def _run():
        scanned_pdf = SAMPLE_DIR / "sample-scanned.pdf"
        assert scanned_pdf.exists()

        # Step 1: Ingest document
        def mock_ocr(img, **kwargs):
            return OCRResult(
                text=(
                    "SOVEREIGN INDUSTRIAL INSPECTION REPORT 2024\n"
                    "Asset: Safety Pressure Relief Valve SV-402\n"
                    "Max operating tolerance: 150 PSI. Pressure test recorded at 135 PSI (PASS).\n"
                    "Visual inspection stamp: CERTIFIED INSPECTED.\n"
                    "Defect findings: No structural fractures detected on pipe casing."
                ),
                is_available=True,
                confidence=96.0,
                engine="tesseract",
            )

        with patch("backend.knowledge.ocr.ocr_image", side_effect=mock_ocr):
            ingest_result = isolated_retriever.ingest_document(
                scanned_pdf,
                document_id="doc_inspection_001",
            )
            assert ingest_result.status == "success"

        # Step 2: Query knowledge base via RAG tool
        rag_tool = test_tool_registry.get("rag.search")
        context = {"task_id": "task_e2e_artifact_001"}
        rag_result: ToolResult = await rag_tool.execute(
            {
                "query": "Pressure Relief Valve tolerance PSI defect findings",
                "top_k": 2,
                "document_id": "doc_inspection_001",
            },
            context=context,
        )
        assert rag_result.success is True
        chunks = rag_result.output
        assert len(chunks) > 0

        # Step 3: Prepare structured approval note payload grounded in evidence
        source_citation = f"{chunks[0]['source']} (Page {chunks[0]['page']})"
        finding_text = f"Pressure test recorded at 135 PSI (tolerance: 150 PSI) - {chunks[0]['content'][:60]}..."

        approval_payload = {
            "title": "Facility Equipment Inspection Approval",
            "subject": "Safety Relief Valve SV-402 Inspection & Re-certification",
            "purpose": "Authorise continued operations for Valve SV-402 following regular visual & pressure testing.",
            "findings": [
                finding_text,
                "Visual inspection verified: no structural fractures or pipe casing anomalies.",
            ],
            "recommendation": "Approve renewed operating certificate for safety valve SV-402 for fiscal year 2024-2025.",
            "requested_approval": "Approval of renewal certificate by the Plant Operations Director.",
            "prepared_by": "Senior Inspection Engineer",
            "source_references": [source_citation],
        }

        # Step 4A: Generate DOCX approval note
        docx_tool = test_tool_registry.get("document.create")
        docx_res: ToolResult = await docx_tool.execute(approval_payload, context=context)
        assert docx_res.success is True
        docx_artifact = docx_res.output
        assert docx_artifact["type"] == "docx"
        assert Path(docx_artifact["storage_uri"]).exists()

        # Step 4B: Generate PDF approval note
        pdf_tool = test_tool_registry.get("pdf.create")
        pdf_res: ToolResult = await pdf_tool.execute(approval_payload, context=context)
        assert pdf_res.success is True
        pdf_artifact = pdf_res.output
        assert pdf_artifact["type"] == "pdf"
        assert Path(pdf_artifact["storage_uri"]).exists()

        # Step 4C: Prepare and generate PPTX presentation
        presentation_payload = {
            "title": "Valve SV-402 Inspection Briefing",
            "slides": [
                {
                    "layout": "title",
                    "title": "Safety Relief Valve SV-402",
                    "subtitle": "Inspection Findings & Certification Review",
                },
                {
                    "layout": "executive_summary",
                    "title": "Executive Summary",
                    "bullets": [
                        "Operating pressure: 135 PSI against max 150 PSI tolerance.",
                        "No structural casing anomalies or fractures found.",
                        "Recommended action: Renew operating license.",
                    ],
                },
                {
                    "layout": "two_column",
                    "title": "Visual vs Pressure Assessment",
                    "left_heading": "Visual Inspection",
                    "left_items": ["Surface stamp: Certified", "Casing integrity confirmed"],
                    "right_heading": "Pressure Testing",
                    "right_items": ["Recorded: 135 PSI", "Threshold: 150 PSI", "Status: PASS"],
                },
                {
                    "layout": "recommendation",
                    "title": "Operational Decision",
                    "recommendation": "Grant operational renewal for SV-402",
                    "decision_points": [
                        "Sign renewal certificate",
                        "Schedule next routine survey in 12 months",
                    ],
                },
            ],
        }

        pptx_tool = test_tool_registry.get("presentation.create")
        pptx_res: ToolResult = await pptx_tool.execute(presentation_payload, context=context)
        assert pptx_res.success is True
        pptx_artifact = pptx_res.output
        assert pptx_artifact["type"] == "pptx"
        assert Path(pptx_artifact["storage_uri"]).exists()

        # Step 5: Validate all artifacts with artifact.validate
        validate_tool = test_tool_registry.get("artifact.validate")

        # 5A: Validate PDF artifact (native PyMuPDF validation and preview rendering)
        pdf_val_res: ToolResult = await validate_tool.execute(
            {
                "artifact": pdf_artifact,
                "required_text": ["Valve SV-402", "Inspection"],
                "render_preview": True,
            },
            context=context,
        )
        assert pdf_val_res.success is True
        assert pdf_val_res.output["valid"] is True
        assert pdf_val_res.output["checks"]["has_extractable_text"] is True
        assert pdf_val_res.output["preview_path"] is not None
        assert Path(pdf_val_res.output["preview_path"]).exists()

        # 5B: Validate DOCX artifact (structural check without requiring external office renderer in CI/unit)
        docx_val_res: ToolResult = await validate_tool.execute(
            {
                "artifact": docx_artifact,
                "required_text": ["Valve SV-402"],
                "render_preview": False,
            },
            context=context,
        )
        assert docx_val_res.success is True
        assert docx_val_res.output["valid"] is True
        assert docx_val_res.output["checks"]["required_text_present"] is True

        # 5C: Validate PPTX artifact (structural check)
        pptx_val_res: ToolResult = await validate_tool.execute(
            {
                "artifact": pptx_artifact,
                "required_text": ["SV-402"],
                "render_preview": False,
            },
            context=context,
        )
        assert pptx_val_res.success is True
        assert pptx_val_res.output["valid"] is True
        assert pptx_val_res.output["checks"]["has_content"] is True

    asyncio.run(_run())

