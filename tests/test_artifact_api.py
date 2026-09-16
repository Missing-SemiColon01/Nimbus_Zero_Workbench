"""
tests/test_artifact_api.py
==========================
Tests for Artifact HTTP API endpoints:
- GET /api/v1/artifacts (list artifacts)
- GET /api/v1/artifacts/{filename}/download (safe download)
- GET /api/v1/artifacts/previews/{preview_name} (safe preview thumbnail retrieval)
- Path traversal protection tests
"""

from pathlib import Path
from starlette.testclient import TestClient

from backend.main import app


def test_list_artifacts_empty(tmp_path: Path):
    with TestClient(app) as client:
        # Override data_dir via settings
        client.app.state.settings.data_dir = tmp_path
        response = client.get("/api/v1/artifacts")
        assert response.status_code == 200
        assert response.json() == []


def test_list_artifacts_with_files_and_previews(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    previews_dir = tmp_path / "tmp" / "artifact-previews"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy artifact and preview
    pdf_file = artifacts_dir / "approval-note.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 dummy content")
    (artifacts_dir / "nested-dir").mkdir()

    preview_file = previews_dir / "approval-note-page-1.png"
    preview_file.write_bytes(b"\x89PNG dummy preview")

    with TestClient(app) as client:
        client.app.state.settings.data_dir = tmp_path
        response = client.get("/api/v1/artifacts")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        item = data[0]
        assert item["filename"] == "approval-note.pdf"
        assert item["file_type"] == "pdf"
        assert item["size_bytes"] > 0
        assert item["download_url"] == "/api/v1/artifacts/approval-note.pdf/download"
        assert item["preview_url"] == "/api/v1/artifacts/previews/approval-note-page-1.png"


def test_download_artifact_success(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    docx_file = artifacts_dir / "report.docx"
    docx_file.write_bytes(b"PK dummy docx bytes")

    with TestClient(app) as client:
        client.app.state.settings.data_dir = tmp_path
        response = client.get("/api/v1/artifacts/report.docx/download")
        assert response.status_code == 200
        assert response.content == b"PK dummy docx bytes"
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in response.headers["content-type"]


def test_download_artifact_not_found(tmp_path: Path):
    with TestClient(app) as client:
        client.app.state.settings.data_dir = tmp_path
        response = client.get("/api/v1/artifacts/non_existent.pdf/download")
        assert response.status_code == 404


def test_download_artifact_path_traversal_blocked(tmp_path: Path):
    with TestClient(app) as client:
        client.app.state.settings.data_dir = tmp_path
        response = client.get("/api/v1/artifacts/..%2f..%2fconfigs%2fmodels.yaml/download")
        assert response.status_code == 404


def test_get_preview_success(tmp_path: Path):
    previews_dir = tmp_path / "tmp" / "artifact-previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    thumb = previews_dir / "test-thumb.png"
    thumb.write_bytes(b"\x89PNG dummy")

    with TestClient(app) as client:
        client.app.state.settings.data_dir = tmp_path
        response = client.get("/api/v1/artifacts/previews/test-thumb.png")
        assert response.status_code == 200
        assert response.content == b"\x89PNG dummy"
        assert response.headers["content-type"] == "image/png"


def test_get_preview_path_traversal_blocked(tmp_path: Path):
    with TestClient(app) as client:
        client.app.state.settings.data_dir = tmp_path
        response = client.get("/api/v1/artifacts/previews/..%2f..%2fconfigs%2fmodels.yaml")
        assert response.status_code == 404

