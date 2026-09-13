"""
tests/test_vision_rag_combined.py
==================================
Day 3 — Task 3.2: Vision + RAG Combined Query Simulation

Simulates the sovereign golden hero workflow:
  1. Agent receives request: "Analyze this inspection report for safety defects and visual anomalies".
  2. PDF page is rendered to high-resolution image via PyMuPDF.
  3. Vision tool (vision.analyze) executes on the page image to detect visual defects, stamps, and layout.
  4. RAG tool (rag.search) executes semantic search on the ingested document to retrieve exact text passages.
  5. Outputs are synchronized into AgentState:
       - AgentState.tool_results contains vision analysis.
       - AgentState.retrieved_context contains page-grounded text chunks.
  6. Multi-modal context fusion verifies complete evidence generation for Dev 1 (supervisor) and Dev 3 (artifact generator).
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import fitz
import pytest
from PIL import Image

from backend.agents.state import AgentState
from backend.core.config import get_settings
from backend.knowledge.embedder import get_embedder
from backend.knowledge.retriever import KnowledgeRetriever
from backend.knowledge.vector_store import VectorStore
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider
from backend.models.registry import ModelRegistry
from backend.models.router import ModelRouter
from backend.tools.contracts import ToolResult
from backend.tools.rag_tool import RAGSearchTool
from backend.tools.registry import ToolRegistry
from backend.tools.setup import build_tool_registry
from backend.tools.vision_tool import VisionAnalyzeTool

SAMPLE_DIR = Path("tests/sample-pdf")


class MockVisionProvider(ModelProvider):
    """Deterministic mock provider for vision testing."""

    def __init__(self, response_text: str = "VISUAL INSPECTION: Stamp detected. Surface shows minor oxidation, no structural cracks."):
        self.response_text = response_text
        self.calls: list[tuple[ModelDefinition, ModelRequest]] = []

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        self.calls.append((model, request))
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
        collection_name="test_vision_rag_combined",
        storage_path=":memory:",
        embedder=shared_embedder,
    )
    return KnowledgeRetriever(vector_store=store, embedder=shared_embedder)


@pytest.fixture
def mock_vision_provider():
    return MockVisionProvider()


@pytest.fixture
def test_tool_registry(isolated_retriever, mock_vision_provider):
    """Build registry with in-memory retriever and mock vision provider."""
    return build_tool_registry(
        provider_registry=mock_vision_provider,
        retriever=isolated_retriever,
    )


def _render_pdf_first_page_to_png(pdf_path: Path, output_image_path: Path) -> Path:
    """Render the first page of a PDF as a PNG image."""
    doc = fitz.open(str(pdf_path))
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=150)
    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(output_image_path))
    doc.close()
    return output_image_path


from backend.knowledge.ocr import OCRResult
from unittest.mock import patch

class TestVisionRagCombinedWorkflow:
    """Validates Day 3 Task 3.2 end-to-end combination of Vision + RAG."""

    def test_registry_contains_both_sovereign_tools(self, test_tool_registry: ToolRegistry):
        names = test_tool_registry.names()
        assert "rag.search" in names
        assert "vision.analyze" in names

        rag_tool = test_tool_registry.get("rag.search")
        vision_tool = test_tool_registry.get("vision.analyze")

        assert isinstance(rag_tool, RAGSearchTool)
        assert isinstance(vision_tool, VisionAnalyzeTool)

    @pytest.mark.asyncio
    async def test_combined_hero_workflow_simulation(
        self,
        isolated_retriever: KnowledgeRetriever,
        test_tool_registry: ToolRegistry,
        tmp_path: Path,
    ):
        """
        Full simulation of the hero workflow:
          1. Ingest sample-scanned.pdf into sovereign knowledge retriever.
          2. Render Page 1 to an image file.
          3. Agent invokes vision.analyze on the image.
          4. Agent invokes rag.search on the knowledge base.
          5. Verify state contains both visual findings and exact page-cited text.
        """
        # Step 1: Ingest document with realistic OCR findings
        scanned_pdf = SAMPLE_DIR / "sample-scanned.pdf"
        assert scanned_pdf.exists()

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
            assert ingest_result.page_count == 2
            assert ingest_result.chunk_count >= 2

        # Step 2: Render Page 1 to an image
        page_image_path = tmp_path / "inspection_page_1.png"
        _render_pdf_first_page_to_png(scanned_pdf, page_image_path)
        assert page_image_path.exists()
        assert page_image_path.stat().st_size > 0

        # Step 3: Initialize AgentState
        state = AgentState(
            task_id="task_hero_inspection_001",
            user_request="Analyze this inspection report for safety defects and visual anomalies",
        )

        # Context dictionary passed to tools
        context = {
            "task_id": state.task_id,
            "retrieved_context": state.retrieved_context,
            "tool_results": state.tool_results,
        }

        # Step 4: Execute Vision Tool
        vision_tool = test_tool_registry.get("vision.analyze")
        vision_result: ToolResult = await vision_tool.execute(
            {
                "image_path": str(page_image_path),
                "prompt": "Examine this page for inspection stamps, serial numbers, and physical defects.",
            },
            context=context,
        )

        assert vision_result.success is True
        assert "analysis" in vision_result.output
        assert "VISUAL INSPECTION" in vision_result.output["analysis"]
        # Confirm recorded into tool_results
        assert len(state.tool_results) >= 1
        assert state.tool_results[0]["tool"] == "vision.analyze"

        # Step 5: Execute RAG Search Tool
        rag_tool = test_tool_registry.get("rag.search")
        rag_result: ToolResult = await rag_tool.execute(
            {
                "query": "safety pressure relief valve operating tolerance PSI defect findings",
                "top_k": 3,
                "document_id": "doc_inspection_001",
            },
            context=context,
        )

        assert rag_result.success is True
        assert isinstance(rag_result.output, list)
        assert len(rag_result.output) > 0

        # Confirm chunks recorded into AgentState.retrieved_context
        assert len(state.retrieved_context) > 0
        first_chunk = state.retrieved_context[0]
        assert "content" in first_chunk
        assert "page" in first_chunk
        assert "source" in first_chunk
        assert first_chunk["document_id"] == "doc_inspection_001"

        # Step 6: Multi-modal fusion check
        # A downstream supervisor agent or approval note generator can fuse:
        visual_evidence = state.tool_results[0]["output"]["analysis"]
        textual_citations = [
            f"[Page {chunk['page']}]: {chunk['content'][:80]}"
            for chunk in state.retrieved_context
        ]

        fused_summary = (
            f"SUMMARY FOR APPROVAL NOTE:\n"
            f"1. Visual Evidence: {visual_evidence}\n"
            f"2. Text Citations ({len(textual_citations)} chunks):\n"
            + "\n".join(textual_citations)
        )

        assert "Visual Evidence" in fused_summary
        assert "Text Citations" in fused_summary
        assert "Page" in fused_summary

    @pytest.mark.asyncio
    async def test_combined_query_with_table_pdf(
        self,
        isolated_retriever: KnowledgeRetriever,
        test_tool_registry: ToolRegistry,
        tmp_path: Path,
    ):
        """
        Verify workflow on sample-table.pdf:
          - Vision tool analyzes financial/inspection layout.
          - RAG retrieves tabular numerical data.
        """
        table_pdf = SAMPLE_DIR / "sample-table.pdf"
        assert table_pdf.exists()

        isolated_retriever.ingest_document(table_pdf, document_id="doc_table_001")

        # Render table page
        page_img = tmp_path / "table_page_1.png"
        _render_pdf_first_page_to_png(table_pdf, page_img)

        state = AgentState(
            task_id="task_table_001",
            user_request="Verify table numbers and visual formatting",
        )
        context = {
            "task_id": state.task_id,
            "retrieved_context": state.retrieved_context,
            "tool_results": state.tool_results,
        }

        # 1. Vision inspects format
        v_tool = test_tool_registry.get("vision.analyze")
        v_res = await v_tool.execute({"image_path": str(page_img), "prompt": "Check table headers."}, context)
        assert v_res.success is True

        # 2. RAG queries numbers
        r_tool = test_tool_registry.get("rag.search")
        r_res = await r_tool.execute({"query": "Revenue Profit Expenses Quarter", "top_k": 2}, context)
        assert r_res.success is True
        assert len(state.retrieved_context) > 0
        assert any("Revenue" in c["content"] or "Quarter" in c["content"] or "Profit" in c["content"] for c in state.retrieved_context)

    @pytest.mark.asyncio
    async def test_graceful_handling_when_image_missing_during_combined_run(
        self,
        test_tool_registry: ToolRegistry,
    ):
        """If image is missing, vision tool fails gracefully without halting RAG."""
        state = AgentState(task_id="task_resilience_001", user_request="Inspect missing image")
        context = {
            "retrieved_context": state.retrieved_context,
            "tool_results": state.tool_results,
        }

        v_tool = test_tool_registry.get("vision.analyze")
        v_res = await v_tool.execute({"image_path": "non_existent_page.png"}, context)
        assert v_res.success is False
        assert "not found" in v_res.error.lower()

        # RAG still executes normally
        r_tool = test_tool_registry.get("rag.search")
        r_res = await r_tool.execute({"query": "any query", "top_k": 1}, context)
        assert r_res.success is True
