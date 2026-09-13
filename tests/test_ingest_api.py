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


def _create_minimal_pdf(path: Path, text: str = "Inspection findings: valve intact.") -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


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

        response = client.post(
            "/api/v1/ingest/upload",
            files={"file": ("uploaded_report.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
            data={"document_id": "uploaded_safety_01"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["document_id"] == "uploaded_safety_01"
        assert data["filename"] == "uploaded_report.pdf"
        assert data["chunk_count"] >= 1
        assert data["status"] == "success"


class TestKnowledgeSearchAPI:
    def test_search_endpoint_returns_ranked_results(self, client: TestClient, tmp_path: Path):
        # Ingest a sample document first
        pdf_path = _create_minimal_pdf(tmp_path / "search_doc.pdf", "Substation emergency shutdown protocol active.")
        ingest_res = client.post(
            "/api/v1/ingest",
            json={"file_path": str(pdf_path), "document_id": "substation_01"},
        )
        assert ingest_res.status_code == 201

        # Search for content
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
