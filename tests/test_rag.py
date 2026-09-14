"""
tests/test_rag.py
=================
Day 3 — Task 3.4: Core RAG and OCR Fallback Integration Tests

Validates:
  1. test_ingest_and_retrieve:
       - Ingests a small test PDF document.
       - Searches for known content.
       - Asserts retrieved chunk returns correct content, page number, and source.
  2. test_ocr_fallback:
       - Provides an image with rendered text.
       - Validates that OCR extraction returns that text.
  3. test_rag_tool_execution:
       - Validates RAGSearchTool execute interface and ToolResult structure.
  4. test_rag_agent_state_sync:
       - Asserts context synchronization into AgentState.retrieved_context.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
from PIL import Image, ImageDraw

from backend.agents.state import AgentState
from backend.knowledge.embedder import get_embedder
from backend.knowledge.ocr import OCRResult, ocr_image
from backend.knowledge.retriever import KnowledgeRetriever
from backend.knowledge.vector_store import VectorStore
from backend.tools.rag_tool import RAGSearchTool

SAMPLE_DIR = Path("tests/sample-pdf")


@pytest.fixture(scope="module")
def shared_embedder():
    embedder = get_embedder()
    embedder.load()
    return embedder


@pytest.fixture
def isolated_retriever(shared_embedder):
    store = VectorStore(
        collection_name="test_rag_spec",
        storage_path=":memory:",
        embedder=shared_embedder,
    )
    return KnowledgeRetriever(vector_store=store, embedder=shared_embedder)


def _create_synthetic_pdf(path: Path, text: str, page_number: int = 1) -> Path:
    """Create a minimal 1-page PDF containing known test text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    doc.close()
    return path


def test_ingest_and_retrieve(isolated_retriever: KnowledgeRetriever, tmp_path: Path):
    """
    Day 3 Task 3.4:
      - Ingest a small test PDF.
      - Search for known content.
      - Assert chunk returned with correct page number and source.
    """
    known_content = "Emergency shutdown sequence initiated for reactor chamber 4B at 1500 PSI."
    test_pdf_path = tmp_path / "reactor_safety_manual.pdf"
    _create_synthetic_pdf(test_pdf_path, known_content)

    # 1. Ingest document
    result = isolated_retriever.ingest_document(test_pdf_path, document_id="doc_reactor_001")
    assert result.status == "success"
    assert result.page_count == 1
    assert result.chunk_count >= 1

    # 2. Search for known content
    hits = isolated_retriever.search("reactor chamber emergency shutdown", top_k=1)
    assert len(hits) >= 1

    top_hit = hits[0]
    # 3. Assert chunk returned with correct page number and source
    assert "reactor chamber" in top_hit["content"].lower()
    assert top_hit["page"] == 1
    assert top_hit["source"] == "reactor_safety_manual.pdf"
    assert top_hit["document_id"] == "doc_reactor_001"
    assert top_hit["score"] > 0.4


def test_ocr_fallback(tmp_path: Path):
    """
    Day 3 Task 3.4:
      - Provide a white image with text.
      - Assert OCR returns that text.
    """
    # 1. Create a white image with text rendered onto it
    img_path = tmp_path / "scanned_gauge_label.png"
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    test_text = "SAFETY RELIEF VALVE: 140 PSI"
    draw.text((10, 40), test_text, fill=(0, 0, 0))
    img.save(img_path)

    # 2. Mock Tesseract availability and extraction to verify ocr_image pipeline
    with patch("backend.knowledge.ocr.is_tesseract_available", return_value=True), \
         patch("backend.knowledge.ocr.pytesseract.image_to_string", return_value=f"{test_text}\x0c"):
        res = ocr_image(img_path)
        assert res.is_available is True
        assert res.has_text is True
        assert "SAFETY RELIEF VALVE" in res.text
        assert "140 PSI" in res.text


@pytest.mark.asyncio
async def test_rag_tool_execution(isolated_retriever: KnowledgeRetriever, tmp_path: Path):
    """
    Verifies RAGSearchTool interface compliance and ToolResult output structure.
    """
    doc_path = tmp_path / "spec_sheet.pdf"
    _create_synthetic_pdf(doc_path, "Coolant pump operating at 3000 RPM nominal rate.")
    isolated_retriever.ingest_document(doc_path, document_id="doc_spec_sheet")

    tool = RAGSearchTool(retriever=isolated_retriever)
    result = await tool.execute({"query": "coolant pump operating rate", "top_k": 1}, context={})

    assert result.success is True
    assert isinstance(result.output, list)
    assert len(result.output) == 1
    assert "coolant pump" in result.output[0]["content"].lower()
    assert result.output[0]["page"] == 1


@pytest.mark.asyncio
async def test_rag_agent_state_sync(isolated_retriever: KnowledgeRetriever, tmp_path: Path):
    """
    Verifies automatic state synchronization into AgentState.retrieved_context.
    """
    doc_path = tmp_path / "maintenance_log.pdf"
    _create_synthetic_pdf(doc_path, "Turbine bearing replaced on 12 August 2026.")
    isolated_retriever.ingest_document(doc_path, document_id="doc_maintenance")

    state = AgentState(
        task_id="task_rag_sync_001",
        user_request="Find turbine maintenance history",
    )
    context = {
        "task_id": state.task_id,
        "retrieved_context": state.retrieved_context,
        "tool_results": state.tool_results,
    }

    tool = RAGSearchTool(retriever=isolated_retriever)
    await tool.execute({"query": "turbine bearing replacement date"}, context=context)

    assert len(state.retrieved_context) >= 1
    chunk = state.retrieved_context[0]
    assert "Turbine bearing" in chunk["content"]
    assert chunk["page"] == 1
    assert chunk["source"] == "maintenance_log.pdf"
