"""
tests/test_retriever.py
========================
Unit tests for backend/knowledge/retriever.py (Day 1 — Task 1.6: Ingest Pipeline & Retriever)

Tests verify end-to-end PDF ingestion, PyMuPDF parsing, chunking, embedding,
Qdrant indexing, and semantic search with exact page citations.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
import pytest

from backend.knowledge.embedder import get_embedder
from backend.knowledge.retriever import (
    IngestResult,
    KnowledgeRetriever,
    get_retriever,
)
from backend.knowledge.vector_store import VectorStore


# -- helpers -------------------------------------------------------------------

def _create_sample_pdf(path: Path) -> Path:
    """Create a sample multi-page PDF for end-to-end testing."""
    doc = fitz.open()

    # Page 1: General Info
    p1 = doc.new_page()
    p1.insert_text((72, 72), "Facility Safety Report 2024. Introduction and overview of sovereign plant operations.", fontsize=12)

    # Page 2: Safety Critical Valve Finding
    p2 = doc.new_page()
    p2.insert_text((72, 72), "Emergency pressure relief valve #4 operating threshold is 140 PSI. Inspection passed on schedule.", fontsize=12)

    # Page 3: Turbine Maintenance
    p3 = doc.new_page()
    p3.insert_text((72, 72), "Turbine generator lubrication schedule. Maintenance cycle every 6 months.", fontsize=12)

    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture(scope="module")
def shared_embedder():
    embedder = get_embedder()
    embedder.load()
    return embedder


@pytest.fixture
def memory_retriever(shared_embedder):
    """Provide a fresh KnowledgeRetriever with an in-memory vector store."""
    store = VectorStore(
        collection_name="test_retriever_knowledge",
        storage_path=":memory:",
        embedder=shared_embedder,
    )
    return KnowledgeRetriever(vector_store=store, embedder=shared_embedder)


# -- tests ---------------------------------------------------------------------

class TestKnowledgeRetrieverBasics:
    def test_initial_count_zero(self, memory_retriever: KnowledgeRetriever):
        assert memory_retriever.count() == 0

    def test_nonexistent_pdf_raises(self, memory_retriever: KnowledgeRetriever, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            memory_retriever.ingest_document(tmp_path / "missing.pdf")


class TestEndToEndIngestAndSearch:
    def test_ingest_pdf_and_retrieve_with_page_citation(
        self,
        memory_retriever: KnowledgeRetriever,
        tmp_path: Path,
    ):
        pdf_path = _create_sample_pdf(tmp_path / "safety_report.pdf")

        # 1. End-to-end Ingestion
        res = memory_retriever.ingest_document(pdf_path, document_id="safety_2024")
        assert isinstance(res, IngestResult)
        assert res.status == "success"
        assert res.page_count == 3
        assert res.chunk_count >= 3
        assert res.duration_seconds > 0
        assert memory_retriever.count() >= 3

        # 2. Semantic Search for specific finding on Page 2
        hits = memory_retriever.search("What is the operating pressure limit for valve 4?", top_k=3)
        assert len(hits) >= 1

        top_hit = hits[0]
        # Verify schema matches AgentState.retrieved_context expectations
        assert "content" in top_hit
        assert "source" in top_hit
        assert "page" in top_hit
        assert "score" in top_hit
        assert "document_id" in top_hit

        # Verify exact page citation grounding
        assert top_hit["source"] == "safety_report.pdf"
        assert top_hit["page"] == 2
        assert top_hit["document_id"] == "safety_2024"
        assert "140 PSI" in top_hit["content"]
        assert top_hit["score"] > 0.5

    def test_ingest_raw_text(self, memory_retriever: KnowledgeRetriever):
        res = memory_retriever.ingest_text(
            text="Transformer substation warning: Voltage fluctuations detected on Grid 3.",
            document_id="substation_note",
            filename="grid_log.txt",
        )
        assert res.status == "success"
        assert res.chunk_count == 1

        hits = memory_retriever.search("substation voltage issues", top_k=1)
        assert len(hits) == 1
        assert hits[0]["document_id"] == "substation_note"
        assert hits[0]["source"] == "grid_log.txt"
        assert "Grid 3" in hits[0]["content"]

    def test_delete_document(self, memory_retriever: KnowledgeRetriever, tmp_path: Path):
        pdf_path = _create_sample_pdf(tmp_path / "temp_doc.pdf")
        memory_retriever.ingest_document(pdf_path, document_id="doc_to_remove")
        assert memory_retriever.count() >= 3

        memory_retriever.delete_document("doc_to_remove")
        assert memory_retriever.count() == 0

        hits = memory_retriever.search("pressure valve", top_k=1)
        assert len(hits) == 0


class TestSingletonAccessor:
    def test_get_retriever_returns_instance(self):
        r = get_retriever()
        assert isinstance(r, KnowledgeRetriever)
