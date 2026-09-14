"""
tests/test_quality_checks.py
============================
Day 3 — Task 3.5: Quality Checks & Certification Before Hand-off to Dev 1 & Dev 3

Validates the 5 mandatory quality criteria defined in the implementation plan:
  [x] Criteria 1: rag.search returns >= 3 relevant chunks from a 10-page PDF.
  [x] Criteria 2: Each chunk has source, page, content, chunk_id, document_id metadata.
  [x] Criteria 3: Vision tool returns non-empty analysis string for a clear page image.
  [x] Criteria 4: OCR doesn't crash on a blank or unreadable page.
  [x] Criteria 5: Both tools registered in ToolRegistry and discoverable by agent.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
from PIL import Image

from backend.agents.state import AgentState
from backend.knowledge.embedder import get_embedder
from backend.knowledge.ocr import ocr_image
from backend.knowledge.retriever import KnowledgeRetriever
from backend.knowledge.vector_store import VectorStore
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider
from backend.tools.rag_tool import RAGSearchTool
from backend.tools.setup import build_tool_registry
from backend.tools.vision_tool import VisionAnalyzeTool

SAMPLE_DIR = Path("tests/sample-pdf")


class MockCertificationVisionProvider(ModelProvider):
    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content="Visual Inspection Analysis: Equipment shows intact casing, no cracks or rust.",
            model_id=model.id,
        )


@pytest.fixture(scope="module")
def shared_embedder():
    embedder = get_embedder()
    embedder.load()
    return embedder


@pytest.fixture
def quality_retriever(shared_embedder):
    store = VectorStore(
        collection_name="test_quality_certification",
        storage_path=":memory:",
        embedder=shared_embedder,
    )
    return KnowledgeRetriever(vector_store=store, embedder=shared_embedder)


class TestQualityChecksCertification:
    """Pre-hand-off certification for Dev 1 (LangGraph Agent) & Dev 3 (Artifacts)."""

    def test_quality_check_1_and_2_rag_search_on_10_page_pdf(self, quality_retriever: KnowledgeRetriever):
        """
        Criteria 1: rag.search returns >= 3 relevant chunks from a 10-page PDF.
        Criteria 2: Each chunk has source, page, content, chunk_id, document_id metadata.
        """
        sample10 = SAMPLE_DIR / "sample10.pdf"
        assert sample10.exists(), "sample10.pdf must exist in tests/sample-pdf"

        # Ingest the 10-page document
        ingest_res = quality_retriever.ingest_document(sample10, document_id="doc_sample10_qc")
        assert ingest_res.status == "success"
        assert ingest_res.page_count == 10
        assert ingest_res.chunk_count >= 10

        tool = RAGSearchTool(retriever=quality_retriever)

        state = AgentState(task_id="qc_task_001", user_request="Inspect findings")
        context = {"retrieved_context": state.retrieved_context}

        # Query for safety/technical content
        import asyncio
        result = asyncio.run(
            tool.execute(
                {"query": "demonstration document page content text", "top_k": 5},
                context=context,
            )
        )

        assert result.success is True
        chunks = result.output

        # Check 1: >= 3 relevant chunks returned from 10-page document
        assert len(chunks) >= 3, f"Expected >= 3 chunks from 10-page PDF, got {len(chunks)}"

        # Check 2: Each chunk has source, page, content, chunk_id, document_id metadata
        for idx, chunk in enumerate(chunks):
            assert "source" in chunk and chunk["source"] == "sample10.pdf", f"Chunk {idx} missing/invalid source"
            assert "page" in chunk and 1 <= chunk["page"] <= 10, f"Chunk {idx} invalid page: {chunk.get('page')}"
            assert "content" in chunk and len(chunk["content"].strip()) > 0, f"Chunk {idx} empty content"
            assert "chunk_id" in chunk and len(chunk["chunk_id"]) > 0, f"Chunk {idx} missing chunk_id"
            assert "document_id" in chunk and chunk["document_id"] == "doc_sample10_qc", f"Chunk {idx} missing document_id"
            assert "score" in chunk and isinstance(chunk["score"], float), f"Chunk {idx} missing score"

    def test_quality_check_3_vision_tool_returns_non_empty_analysis(self, tmp_path: Path):
        """
        Criteria 3: Vision tool returns non-empty analysis string for a clear page image.
        """
        # Create clear page image
        img_path = tmp_path / "clear_inspection_page.png"
        img = Image.new("RGB", (300, 300), color=(240, 240, 240))
        img.save(img_path)

        provider = MockCertificationVisionProvider()
        tool = VisionAnalyzeTool(provider=provider)

        import asyncio
        result = asyncio.run(
            tool.execute(
                {"image_path": str(img_path), "prompt": "Inspect equipment casing."},
                context={},
            )
        )

        assert result.success is True
        assert "analysis" in result.output
        analysis_str = result.output["analysis"]
        assert isinstance(analysis_str, str)
        assert len(analysis_str.strip()) > 0
        assert "Visual Inspection Analysis" in analysis_str

    def test_quality_check_4_ocr_does_not_crash_on_blank_or_unreadable_page(self, tmp_path: Path):
        """
        Criteria 4: OCR doesn't crash on a blank or unreadable page.
        """
        # 1. Test with a completely blank image
        blank_img_path = tmp_path / "blank_page.png"
        blank_img = Image.new("RGB", (200, 200), color=(255, 255, 255))
        blank_img.save(blank_img_path)

        # Ensure OCR handles blank image cleanly without crashing
        with patch("backend.knowledge.ocr.is_tesseract_available", return_value=True), \
             patch("backend.knowledge.ocr.pytesseract.image_to_string", return_value=""):
            result = ocr_image(blank_img_path)
            assert result.error is None
            assert result.has_text is False

        # 2. Test with sample-empty.pdf
        sample_empty = SAMPLE_DIR / "sample-empty.pdf"
        if sample_empty.exists():
            from backend.knowledge.pdf_parser import parse_pdf
            parsed = parse_pdf(sample_empty)
            assert parsed.page_count == 1
            # Did not crash, parsed page safely
            assert len(parsed.pages) == 1

    def test_quality_check_5_both_tools_registered_in_tool_registry(self, quality_retriever: KnowledgeRetriever):
        """
        Criteria 5: Both tools registered in ToolRegistry and discoverable by agent.
        """
        registry = build_tool_registry(
            provider_registry=MockCertificationVisionProvider(),
            retriever=quality_retriever,
        )

        names = registry.names()
        assert "rag.search" in names
        assert "vision.analyze" in names

        # Verify discoverability and contracts
        rag_tool = registry.get("rag.search")
        vision_tool = registry.get("vision.analyze")

        assert isinstance(rag_tool, RAGSearchTool)
        assert isinstance(vision_tool, VisionAnalyzeTool)
        assert len(rag_tool.description) > 0
        assert len(vision_tool.description) > 0
        assert "query" in rag_tool.parameters["properties"]
        assert "image_path" in vision_tool.parameters["properties"]
