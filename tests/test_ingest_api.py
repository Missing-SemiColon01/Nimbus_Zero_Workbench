"""
tests/test_ingest_api.py
=========================
Unit tests for Day 2 Task 2.5: Ingest & Knowledge API Endpoints

Tests verify:
  - POST /api/v1/ingest (path ingestion & 404 validation)
  - POST /api/v1/ingest/upload (multipart PDF upload & format validation)
  - POST /api/v1/knowledge/search (semantic search query & response format)
  - GET /api/v1/tools (listing of registered tools)
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import fitz  # PyMuPDF
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.knowledge.retriever import IngestResult


def _create_minimal_pdf(path: Path, text: str = "Inspection findings: valve intact.") -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def _successful_retriever(document_id: str, filename: str) -> MagicMock:
    retriever = MagicMock()
    retriever.ingest_document.return_value = IngestResult(
        document_id=document_id,
        filename=filename,
        page_count=1,
        chunk_count=1,
        ocr_pages=0,
        duration_seconds=0.01,
        status="success",
    )
    return retriever


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


class TestIngestAPI:
    def test_ingest_missing_file_returns_404(self, client: TestClient):
        response = client.post(
            "/api/v1/ingest",
            json={"file_path": "non_existent_file.pdf"},
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_ingest_valid_pdf_path(self, client: TestClient, tmp_path: Path):
        pdf_path = _create_minimal_pdf(tmp_path / "test_doc.pdf")
        retriever = MagicMock()
        retriever.ingest_document.return_value = IngestResult(
            document_id="test_doc_01",
            filename="test_doc.pdf",
            page_count=1,
            chunk_count=1,
            ocr_pages=0,
            duration_seconds=0.01,
            status="success",
        )

        with patch("backend.api.routes.get_retriever", return_value=retriever):
            response = client.post(
                "/api/v1/ingest",
                json={
                    "file_path": str(pdf_path),
                    "document_id": "test_doc_01",
                    "chunk_size": 200,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["document_id"] == "test_doc_01"
        assert data["filename"] == "test_doc.pdf"
        assert data["page_count"] == 1
        assert data["chunk_count"] >= 1
        assert data["status"] == "success"
        retriever.ingest_document.assert_called_once_with(
            source=pdf_path,
            document_id="test_doc_01",
            chunk_size=200,
            chunk_overlap=50,
        )

    def test_upload_non_pdf_rejected_with_400(self, client: TestClient):
        fake_file = io.BytesIO(b"not a pdf")
        response = client.post(
            "/api/v1/ingest/upload",
            files={"file": ("notes.txt", fake_file, "text/plain")},
        )
        assert response.status_code == 400
        assert "only pdf" in response.json()["detail"].lower()

    def test_upload_valid_pdf_multipart(self, client: TestClient, tmp_path: Path):
        pdf_path = _create_minimal_pdf(tmp_path / "uploaded_report.pdf", "Safety valve pressure: 130 PSI.")
        pdf_bytes = pdf_path.read_bytes()
        retriever = MagicMock()
        retriever.ingest_document.return_value = IngestResult(
            document_id="uploaded_safety_01",
            filename="uploaded_report.pdf",
            page_count=1,
            chunk_count=1,
            ocr_pages=0,
            duration_seconds=0.01,
            status="success",
        )

        with patch("backend.api.routes.get_retriever", return_value=retriever):
            response = client.post(
                "/api/v1/ingest/upload",
                files={"file": ("uploaded_report.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
                data={"document_id": "uploaded_safety_01"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["document_id"] == "uploaded_safety_01"
        assert data["filename"] == "uploaded_report.pdf"
        assert Path(data["document_path"]).name == "uploaded_report.pdf"
        assert Path(data["document_path"]).exists()
        assert data["chunk_count"] >= 1
        assert data["status"] == "success"
        saved_path = retriever.ingest_document.call_args.kwargs["source"]
        assert saved_path.name == "uploaded_report.pdf"
        assert saved_path.exists()

    def test_upload_sanitizes_filename(self, client: TestClient, tmp_path: Path):
        pdf_path = _create_minimal_pdf(tmp_path / "unsafe.pdf")
        retriever = MagicMock()
        retriever.ingest_document.return_value = IngestResult(
            document_id="unsafe",
            filename="unsafe.pdf",
            page_count=1,
            chunk_count=1,
            ocr_pages=0,
            duration_seconds=0.01,
            status="success",
        )

        with patch("backend.api.routes.get_retriever", return_value=retriever):
            response = client.post(
                "/api/v1/ingest/upload",
                files={"file": ("../unsafe.pdf", io.BytesIO(pdf_path.read_bytes()), "application/pdf")},
            )

        assert response.status_code == 201
        saved_path = retriever.ingest_document.call_args.kwargs["source"]
        assert saved_path.name == "unsafe.pdf"
        assert saved_path.parent.name == "uploads"

    def test_upload_empty_pdf_rejected(self, client: TestClient):
        """Empty PDF bytes should be rejected cleanly (either 400 or 500, not a crash)."""
        empty_pdf = io.BytesIO(b"")
        response = client.post(
            "/api/v1/ingest/upload",
            files={"file": ("empty.pdf", empty_pdf, "application/pdf")},
        )
        # Accept 400 (bad input) or 500 (parse failure) — both are non-crash responses
        assert response.status_code in (400, 422, 500)


class TestStoragePersistence:
    """
    Dev 4B Phase 2 — Storage Reliability.
    Verifies uploaded PDFs are actually written to data/uploads/ on disk
    and persist after the request completes.
    """

    def test_upload_file_persists_on_disk(self, client: TestClient, tmp_path: Path):
        """After a successful upload the file must exist in data/uploads/."""
        filename = "persist_check.pdf"
        pdf_bytes = _create_minimal_pdf(tmp_path / filename, "Persistence check content.").read_bytes()
        retriever = _successful_retriever("persist_check_01", filename)

        with patch("backend.api.routes.get_retriever", return_value=retriever):
            response = client.post(
                "/api/v1/ingest/upload",
                files={"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")},
                data={"document_id": "persist_check_01"},
            )
        assert response.status_code == 201

        saved_path = Path(response.json()["document_path"])
        assert saved_path.exists(), f"Expected file at {saved_path} — not found"
        assert saved_path.stat().st_size > 0, "Saved file is unexpectedly empty"

    def test_upload_overwrites_existing_file(self, client: TestClient, tmp_path: Path):
        """Uploading the same filename twice should overwrite cleanly with no error."""
        filename = "overwrite_check.pdf"

        for i, content in enumerate(["First upload content.", "Second upload — overwrite."]):
            pdf_bytes = _create_minimal_pdf(tmp_path / f"v{i}.pdf", content).read_bytes()
            retriever = _successful_retriever(f"overwrite_{i}", filename)
            with patch("backend.api.routes.get_retriever", return_value=retriever):
                response = client.post(
                    "/api/v1/ingest/upload",
                    files={"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")},
                    data={"document_id": f"overwrite_{i}"},
                )
            assert response.status_code == 201

        saved_path = Path(response.json()["document_path"])
        assert saved_path.exists()

    def test_uploads_dir_created_automatically(self, client: TestClient, tmp_path: Path):
        """The uploads directory is created by the API automatically (mkdir parents=True)."""
        filename = "dir_creation_check.pdf"
        pdf_bytes = _create_minimal_pdf(tmp_path / filename, "Dir creation check.").read_bytes()
        retriever = _successful_retriever("dir_creation_check", filename)

        with patch("backend.api.routes.get_retriever", return_value=retriever):
            response = client.post(
                "/api/v1/ingest/upload",
                files={"file": (filename, io.BytesIO(pdf_bytes), "application/pdf")},
            )
        assert response.status_code == 201
        assert Path("data/uploads").is_dir()


class TestKnowledgeSearchAPI:
    def test_search_endpoint_returns_ranked_results(self, client: TestClient, tmp_path: Path):
        retriever = MagicMock()
        retriever.search.return_value = [
            {
                "content": "Substation emergency shutdown protocol active.",
                "source": "search_doc.pdf",
                "page": 1,
                "chunk_id": "substation_01-page-1-chunk-0",
                "document_id": "substation_01",
                "score": 0.98,
                "metadata": {},
            }
        ]

        with patch("backend.api.routes.get_retriever", return_value=retriever):
            response = client.post(
                "/api/v1/knowledge/search",
                json={"query": "substation emergency shutdown", "top_k": 3},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "substation emergency shutdown"
        assert data["total_results"] >= 1
        top_hit = data["results"][0]
        assert "substation" in top_hit["content"].lower()
        assert top_hit["source"] == "search_doc.pdf"
        assert "page" in top_hit
        assert "score" in top_hit
        retriever.search.assert_called_once_with(
            query="substation emergency shutdown",
            top_k=3,
            score_threshold=None,
            filter_doc_id=None,
        )

    def test_search_empty_query_returns_422(self, client: TestClient):
        response = client.post(
            "/api/v1/knowledge/search",
            json={"query": ""},
        )
        assert response.status_code == 422


class TestToolsAPI:
    def test_list_tools_returns_rag_and_vision_tools(self, client: TestClient):
        response = client.get("/api/v1/tools")
        assert response.status_code == 200
        tools = response.json()
        tool_names = [t["name"] for t in tools]

        assert "rag.search" in tool_names
        assert "vision.analyze" in tool_names
