"""
tests/test_local_integration_flow.py
====================================
Dev 4B Phase 4: Local Integration Flow

Validates the full local API pipeline end-to-end without GPU or Docker dependencies:
  1. GET /api/v1/health & GET /api/v1/models (Local sovereign health & model registry validation)
  2. POST /api/v1/ingest/upload (PDF multipart upload, disk persistence in data/uploads)
  3. POST /api/v1/knowledge/search (Grounding search across ingested document chunks)
  4. POST /api/v1/tasks (Autonomous agent task generation with model mock/fallback)
  5. Deliverable creation into data/artifacts/ via ToolRegistry (spreadsheet deliverable)
  6. GET /api/v1/artifacts & GET /api/v1/artifacts/{filename}/download (Verification of deliverable access)
"""

from pathlib import Path

import fitz
import httpx
import pytest

from backend.main import app
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider


class FakeLocalProvider(ModelProvider):
    def __init__(self, response: str = "Analysis confirmed. Operational limits acceptable."):
        self.response = response
        self.calls: list[tuple[ModelDefinition, ModelRequest]] = []

    async def generate(self, model: ModelDefinition, request: ModelRequest) -> ModelResponse:
        self.calls.append((model, request))
        return ModelResponse(content=self.response, model_id=model.id)


def _generate_test_pdf(path: Path, title: str, body: str) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), title, fontsize=16)
    page.insert_text((72, 100), body, fontsize=11)
    doc.save(str(path))
    doc.close()
    return path


@pytest.mark.asyncio
async def test_full_local_integration_pipeline(tmp_path: Path):
    """
    End-to-end integration test verifying the complete Dev 4 local runtime flow:
    Health -> Models -> Upload -> Search -> Task -> Artifact Tool -> Artifact API
    """
    provider = FakeLocalProvider()

    # 1. Startup via lifespan
    async with app.router.lifespan_context(app):
        # Register mock provider so task calls run without live Ollama
        app.state.runtime.providers.register("ollama", provider)

        # Ensure settings points to default data dir and sovereign mode is active
        app.state.settings.data_dir = Path("data")
        assert app.state.settings.sovereign_mode is True

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            # -----------------------------------------------------------------
            # Step 1: Health & Models
            # -----------------------------------------------------------------
            health_res = await client.get("/api/v1/health")
            assert health_res.status_code == 200
            assert health_res.json() == {"status": "ok", "sovereign_mode": True}

            models_res = await client.get("/api/v1/models")
            assert models_res.status_code == 200
            model_ids = [m["id"] for m in models_res.json()]
            assert "reasoning" in model_ids
            assert "vision" in model_ids

            # -----------------------------------------------------------------
            # Step 2: Ingest & Upload PDF to data/uploads
            # -----------------------------------------------------------------
            upload_filename = "phase4_integration_doc.pdf"
            sample_pdf = _generate_test_pdf(
                tmp_path / upload_filename,
                title="INDUSTRIAL SENSOR CALIBRATION LOG",
                body="Turbine sensor TS-900 calibrated at 1200 RPM. Error tolerance within 0.05 percent.",
            )

            files = {"file": (upload_filename, sample_pdf.read_bytes(), "application/pdf")}
            data = {"document_id": "phase4_sensor_doc_01"}

            upload_res = await client.post("/api/v1/ingest/upload", files=files, data=data)
            assert upload_res.status_code == 201
            upload_body = upload_res.json()
            assert upload_body["status"] == "success"
            assert upload_body["document_id"] == "phase4_sensor_doc_01"
            assert upload_body["filename"] == upload_filename

            # Confirm file persisted on disk in data/uploads
            persisted_upload = Path("data/uploads") / upload_filename
            assert persisted_upload.exists()
            assert persisted_upload.stat().st_size > 0

            # -----------------------------------------------------------------
            # Step 3: Knowledge Search Across Ingested Chunks
            # -----------------------------------------------------------------
            search_res = await client.post(
                "/api/v1/knowledge/search",
                json={
                    "query": "Turbine sensor RPM calibration",
                    "top_k": 3,
                    "document_id": "phase4_sensor_doc_01",
                },
            )
            assert search_res.status_code == 200
            search_body = search_res.json()
            assert search_body["total_results"] >= 1
            assert "TS-900" in search_body["results"][0]["content"]

            # -----------------------------------------------------------------
            # Step 4: Autonomous Task Execution
            # -----------------------------------------------------------------
            task_res = await client.post(
                "/api/v1/tasks",
                json={
                    "request": f"Analyze turbine sensor TS-900 calibration readings from document {upload_filename}",
                    "task_type": "reasoning",
                },
            )
            assert task_res.status_code == 201
            task_body = task_res.json()
            assert task_body["task_id"]
            assert task_body["status"] == "completed"
            assert task_body["selected_model"] == "reasoning"
            assert "Operational limits acceptable" in task_body["response"]

            # -----------------------------------------------------------------
            # Step 5: Deliverable Creation via Artifact Tool (Spreadsheet)
            # -----------------------------------------------------------------
            spreadsheet_tool = app.state.tools.get("spreadsheet.create")
            context = {"task_id": task_body["task_id"]}

            sheet_res = await spreadsheet_tool.execute(
                {
                    "title": "Turbine Sensor TS-900 Summary",
                    "sheets": [
                        {
                            "title": "Readings",
                            "columns": [
                                {"key": "metric", "header": "Metric", "width": 20},
                                {"key": "value", "header": "Value", "width": 15},
                            ],
                            "rows": [
                                {"metric": "Turbine RPM", "value": 1200},
                                {"metric": "Tolerance Error %", "value": 0.05},
                            ],
                        }
                    ],
                },
                context=context,
            )
            assert sheet_res.success is True
            sheet_filename = Path(sheet_res.output["storage_uri"]).name

            # -----------------------------------------------------------------
            # Step 6: Artifact Listing & Download Verification
            # -----------------------------------------------------------------
            artifacts_res = await client.get("/api/v1/artifacts")
            assert artifacts_res.status_code == 200
            artifact_names = [a["filename"] for a in artifacts_res.json()]
            assert sheet_filename in artifact_names

            download_res = await client.get(f"/api/v1/artifacts/{sheet_filename}/download")
            assert download_res.status_code == 200
            assert len(download_res.content) > 0
            assert "spreadsheet" in download_res.headers["content-type"]

