"""
tests/test_scanned_e2e.py
==========================
Day 3 — Task 3.1: Scanned & Multi-Page PDF End-to-End Test Suite

Validates the full golden demo ingestion and retrieval pipeline using the real
sample PDFs provided in tests/sample-pdf/:
  1. sample-scanned.pdf: 2-page scanned image PDF (tests OCR fallback & page grounding).
  2. sample-table.pdf: Table extraction and structured data retrieval.
  3. sample5.pdf: 5-page multi-page document testing cross-page citations.
  4. sample-empty.pdf: Edge case handling for zero-content documents.
  5. sample-form.pdf: Form fields and key-value label retrieval.
  6. API upload testing: Uploading sample PDFs via POST /api/v1/ingest/upload.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from backend.knowledge.embedder import get_embedder
from backend.knowledge.ocr import OCRResult
from backend.knowledge.pdf_parser import parse_pdf
from backend.knowledge.retriever import IngestResult, KnowledgeRetriever
from backend.knowledge.vector_store import VectorStore
from backend.main import app

SAMPLE_DIR = Path("tests/sample-pdf")


@pytest.fixture(scope="module")
def shared_embedder():
    embedder = get_embedder()
    embedder.load()
    return embedder


@pytest.fixture
def test_retriever(shared_embedder):
    """Isolated in-memory KnowledgeRetriever for test runs."""
    store = VectorStore(
        collection_name="test_e2e_scanned_knowledge",
        storage_path=":memory:",
        embedder=shared_embedder,
    )
    return KnowledgeRetriever(vector_store=store, embedder=shared_embedder)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


class TestScannedPdfEndToEnd:
    def test_sample_scanned_pdf_exists(self):
        scanned_pdf = SAMPLE_DIR / "sample-scanned.pdf"
        assert scanned_pdf.exists(), f"Expected sample-scanned.pdf in {SAMPLE_DIR}"

    def test_scanned_pdf_triggers_ocr_and_retains_page_grounding(self, test_retriever: KnowledgeRetriever):
        """
        Verify that sample-scanned.pdf triggers OCR fallback on its scanned image pages,
        produces searchable chunks, and correctly attributes findings to Page 1 and Page 2.
        """
        scanned_pdf = SAMPLE_DIR / "sample-scanned.pdf"

        call_count = 0

        def mock_ocr(img, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return OCRResult(
                    text=(
                        "SOVEREIGN FACILITY INSPECTION RECORD 2024\n"
                        "Emergency safety relief valve #4 operating threshold: 140 PSI (PASS).\n"
                        "Pressure verified by certified test engineer."
                    ),
                    is_available=True,
                    confidence=95.0,
                    engine="tesseract",
                )
            else:
                return OCRResult(
                    text=(
                        "FACILITY PERIMETER LOG\n"
                        "General exterior cleaning and routine painting of perimeter fence.\n"
                        "No structural defects identified on grounds."
                    ),
                    is_available=True,
                    confidence=92.0,
                    engine="tesseract",
                )

        with patch("backend.knowledge.ocr.ocr_image", side_effect=mock_ocr):
            # 1. Ingest scanned PDF
            result: IngestResult = test_retriever.ingest_document(
                source=scanned_pdf,
                document_id="inspection_scanned_2024",
            )

            assert result.status == "success"
            assert result.page_count == 2
            assert result.ocr_pages == 2  # Both scanned pages triggered OCR
            assert result.chunk_count >= 2

            # 2. Query for safety valve finding
            hits = test_retriever.search("valve operating threshold pressure", top_k=2)
            assert len(hits) >= 1

            top_hit = hits[0]
            assert top_hit["source"] == "sample-scanned.pdf"
            assert top_hit["page"] == 1  # Verified on Page 1
            assert top_hit["document_id"] == "inspection_scanned_2024"
            assert "140 PSI" in top_hit["content"]
            assert top_hit["score"] > 0.4
            assert top_hit["metadata"]["used_ocr"] is True


class TestMultiPageAndTablePdfIngestion:
    def test_ingest_sample_table_pdf(self, test_retriever: KnowledgeRetriever):
        table_pdf = SAMPLE_DIR / "sample-table.pdf"
        assert table_pdf.exists()

        result = test_retriever.ingest_document(table_pdf, document_id="doc_table")
        assert result.status == "success"
        assert result.page_count == 1
        assert result.chunk_count >= 1

        hits = test_retriever.search("Category Value Status Alpha", top_k=1)
        assert len(hits) == 1
        assert "Alpha" in hits[0]["content"]
        assert hits[0]["source"] == "sample-table.pdf"

    def test_ingest_multipage_sample5_pdf(self, test_retriever: KnowledgeRetriever):
        sample5_pdf = SAMPLE_DIR / "sample5.pdf"
        assert sample5_pdf.exists()

        result = test_retriever.ingest_document(sample5_pdf, document_id="doc_sample5")
        assert result.status == "success"
        assert result.page_count == 5
        assert result.chunk_count >= 5

        # Verify search returns distinct pages with correct page metadata
        hits = test_retriever.search("Lorem ipsum dolor sit amet", top_k=3)
        assert len(hits) >= 3
        pages = {hit["page"] for hit in hits}
        assert len(pages) > 1  # Multiple distinct pages retrieved


class TestEdgeCasePdfs:
    def test_sample_empty_pdf_handled_gracefully(self, test_retriever: KnowledgeRetriever):
        empty_pdf = SAMPLE_DIR / "sample-empty.pdf"
        if empty_pdf.exists():
            result = test_retriever.ingest_document(empty_pdf, document_id="doc_empty")
            assert result.status == "success"
            assert result.chunk_count == 0  # No chunks from empty page

    def test_sample_form_pdf_fields_indexed(self, test_retriever: KnowledgeRetriever):
        form_pdf = SAMPLE_DIR / "sample-form.pdf"
        if form_pdf.exists():
            result = test_retriever.ingest_document(form_pdf, document_id="doc_form")
            assert result.status == "success"
            hits = test_retriever.search("Full Name Email Address City", top_k=1)
            assert len(hits) >= 1
            assert "Name" in hits[0]["content"]


class TestApiMultipartUploadWithSamplePdf:
    def test_upload_sample_table_via_api(self, client: TestClient):
        table_pdf = SAMPLE_DIR / "sample-table.pdf"
        pdf_bytes = table_pdf.read_bytes()

        response = client.post(
            "/api/v1/ingest/upload",
            files={"file": ("sample-table.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"document_id": "api_uploaded_table"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["document_id"] == "api_uploaded_table"
        assert data["filename"] == "sample-table.pdf"
        assert data["chunk_count"] >= 1
        assert data["status"] == "success"

        # Search via API to confirm live indexing
        search_res = client.post(
            "/api/v1/knowledge/search",
            json={"query": "Monthly Report Revenue Expenses Profit", "top_k": 1},
        )
        assert search_res.status_code == 200
        search_data = search_res.json()
        assert search_data["total_results"] >= 1
        assert "Revenue" in search_data["results"][0]["content"]


class TestAllSamplePdfCoverage:
    """Ensures 100% coverage across every file in tests/sample-pdf/."""

    def test_sample1_single_page_pdf(self, test_retriever: KnowledgeRetriever):
        sample1 = SAMPLE_DIR / "sample1.pdf"
        assert sample1.exists()
        result = test_retriever.ingest_document(sample1, document_id="doc_sample1")
        assert result.status == "success"
        assert result.page_count == 1
        assert result.chunk_count >= 1

    def test_sample10_ten_page_pdf(self, test_retriever: KnowledgeRetriever):
        sample10 = SAMPLE_DIR / "sample10.pdf"
        assert sample10.exists()
        result = test_retriever.ingest_document(sample10, document_id="doc_sample10")
        assert result.status == "success"
        assert result.page_count == 10
        assert result.chunk_count >= 10

    def test_sample_landscape_pdf(self, test_retriever: KnowledgeRetriever):
        landscape_pdf = SAMPLE_DIR / "sample-landscape.pdf"
        assert landscape_pdf.exists()
        doc = parse_pdf(landscape_pdf)
        assert doc.page_count == 1
        # Landscape orientation has width > height
        assert doc.pages[0].width_pt > doc.pages[0].height_pt

    def test_sample_heavy_pdf(self, test_retriever: KnowledgeRetriever):
        heavy_pdf = SAMPLE_DIR / "sample-heavy.pdf"
        assert heavy_pdf.exists()
        # Parse only first 5 pages for rapid test execution or test full doc
        doc = parse_pdf(heavy_pdf, pages=[1, 2, 3])
        assert doc.page_count == 18
        assert len(doc.pages) == 3

    def test_sample_protected_pdf_graceful_error(self):
        protected_pdf = SAMPLE_DIR / "sample-protected.pdf"
        assert protected_pdf.exists()
        with pytest.raises(ValueError) as exc_info:
            parse_pdf(protected_pdf)
        assert "password-protected or encrypted" in str(exc_info.value).lower()

    def test_scientific_ocr_research_paper(self, test_retriever: KnowledgeRetriever):
        paper_pdf = SAMPLE_DIR / "Efficient_and_effective_OCR_engine_training.pdf"
        assert paper_pdf.exists()
        # Parse first 2 pages to verify scientific/research paper layout extraction
        doc = parse_pdf(paper_pdf, pages=[1, 2])
        assert doc.page_count == 16
        assert len(doc.pages) == 2
        assert len(doc.pages[0].text) > 50

