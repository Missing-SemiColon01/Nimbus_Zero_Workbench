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


# ---------------------------------------------------------------------------
# Dev 4B Phase 3 — Artifact Storage Reliability
# These tests write real files into the live data/artifacts/ and data/tmp/
# directories (not tmp_path) to verify persistence and API reachability.
# ---------------------------------------------------------------------------

import pytest


class TestArtifactStorageReliability:
    """
    Confirms that data/artifacts/ and data/tmp/artifact-previews/ persist on
    disk and that files written there are reachable through the live API.
    """

    ARTIFACTS_DIR = Path("data/artifacts")
    PREVIEWS_DIR = Path("data/tmp/artifact-previews")

    @pytest.fixture(autouse=True)
    def ensure_dirs(self):
        """Guarantee both storage dirs exist and app is pointing at the real data/ dir."""
        self.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        self.PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)
        # Other tests mutate app.state.settings.data_dir to tmp_path.
        # Reset here so these tests always use the real on-disk path.
        with TestClient(app) as client:
            client.app.state.settings.data_dir = Path("data")
        yield

    def test_artifacts_dir_exists_on_disk(self):
        """data/artifacts/ must be present (created at startup or by fixture)."""
        assert self.ARTIFACTS_DIR.is_dir()

    def test_tmp_previews_dir_exists_on_disk(self):
        """data/tmp/artifact-previews/ must be present."""
        assert self.PREVIEWS_DIR.is_dir()

    def test_artifact_written_to_disk_is_listable(self):
        """A file written to data/artifacts/ appears in GET /api/v1/artifacts."""
        artifact = self.ARTIFACTS_DIR / "dev4b_list_check.pdf"
        artifact.write_bytes(b"%PDF-1.4 dev4b storage check")

        try:
            with TestClient(app) as client:
                response = client.get("/api/v1/artifacts")
                assert response.status_code == 200
                filenames = [item["filename"] for item in response.json()]
                assert "dev4b_list_check.pdf" in filenames
        finally:
            artifact.unlink(missing_ok=True)

    def test_artifact_written_to_disk_is_downloadable(self):
        """A file written to data/artifacts/ can be streamed via the download endpoint."""
        payload = b"%PDF-1.4 downloadable artifact content"
        artifact = self.ARTIFACTS_DIR / "dev4b_download_check.pdf"
        artifact.write_bytes(payload)

        try:
            with TestClient(app) as client:
                response = client.get("/api/v1/artifacts/dev4b_download_check.pdf/download")
                assert response.status_code == 200
                assert response.content == payload
                assert "application/pdf" in response.headers["content-type"]
        finally:
            artifact.unlink(missing_ok=True)

    def test_preview_written_to_disk_is_servable(self):
        """A PNG written to data/tmp/artifact-previews/ is served by the preview endpoint."""
        payload = b"\x89PNG dev4b preview check"
        preview = self.PREVIEWS_DIR / "dev4b_preview_check.png"
        preview.write_bytes(payload)

        try:
            with TestClient(app) as client:
                response = client.get("/api/v1/artifacts/previews/dev4b_preview_check.png")
                assert response.status_code == 200
                assert response.content == payload
                assert response.headers["content-type"] == "image/png"
        finally:
            preview.unlink(missing_ok=True)

    def test_artifacts_dir_survives_repeated_requests(self):
        """data/artifacts/ remains a valid directory after multiple list requests."""
        with TestClient(app) as client:
            for _ in range(3):
                response = client.get("/api/v1/artifacts")
                assert response.status_code == 200
        assert self.ARTIFACTS_DIR.is_dir()

    def test_list_artifacts_includes_all_supported_extensions(self):
        """All four artifact types (pdf/docx/pptx/xlsx) appear in the listing."""
        files_created = []
        for name, content in [
            ("dev4b_ext_check.pdf", b"%PDF-1.4"),
            ("dev4b_ext_check.docx", b"PK docx"),
            ("dev4b_ext_check.pptx", b"PK pptx"),
            ("dev4b_ext_check.xlsx", b"PK xlsx"),
        ]:
            p = self.ARTIFACTS_DIR / name
            p.write_bytes(content)
            files_created.append(p)

        try:
            with TestClient(app) as client:
                response = client.get("/api/v1/artifacts")
                assert response.status_code == 200
                data = response.json()
                filenames = {item["filename"] for item in data}
                for f in files_created:
                    assert f.name in filenames, f"{f.name} not found in listing"
                # Verify file_type is stripped extension (no dot)
                types = {item["file_type"] for item in data if item["filename"].startswith("dev4b_ext")}
                assert types == {"pdf", "docx", "pptx", "xlsx"}
        finally:
            for p in files_created:
                p.unlink(missing_ok=True)


