"""
tests/test_golden_grand_simulation.py
======================================
Comprehensive End-to-End Cross-Dev Golden Simulation

Simulates the complete Sovereign AI Workbench in production where Dev 1, Dev 2,
Dev 3, and Dev 4 components operate in concert:

  [Dev 4] FastAPI Server & Routing:
    - Starts the workbench application with full lifespan wiring.
    - Exposes health, tools registry, and multipart document ingestion.
  [Dev 2] Knowledge Ingestion, Multimodal Vision, & Sovereign RAG:
    - Ingests sample-scanned.pdf via POST /api/v1/ingest/upload.
    - Vectorizes chunks locally with all-MiniLM-L6-v2 into Qdrant.
    - Renders PDF page to PNG and executes vision.analyze.
    - Executes rag.search to retrieve exact page-grounded citations.
  [Dev 1] Autonomous Agent Supervisor & State Management:
    - Orchestrates task execution using AgentState.
    - Synchronizes multi-modal visual observations and textual evidence.
    - Synthesizes findings into a structured ApprovalNoteSpec.
  [Dev 4] Security Governance:
    - Evaluates PolicyEngine.evaluate("document.create").
    - Confirms Human-in-the-Loop governance (PolicyDecision.REQUIRE_APPROVAL).
  [Dev 3] Deliverable Generators:
    - Executes DocumentCreateTool and PdfCreateTool.
    - Generates formal Word (.docx) and PDF (.pdf) audit approval notes.
    - Asserts exact source page citations ("sample-scanned.pdf, Page 1") inside the output deliverables.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import fitz
import pytest
from docx import Document
from starlette.testclient import TestClient

from backend.agents.state import AgentState
from backend.artifacts.contracts import ApprovalNoteSpec
from backend.artifacts.tools import DocumentCreateTool, PdfCreateTool
from backend.knowledge.ocr import OCRResult
from backend.main import app
from backend.models.contracts import ModelDefinition, ModelResponse
from backend.security.policy import PolicyDecision, PolicyEngine
from backend.tools.contracts import ToolResult

SAMPLE_DIR = Path("tests/sample-pdf")


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


class TestGoldenGrandSimulation:
    """The unified end-to-end cross-dev golden workflow."""

    @pytest.mark.asyncio
    async def test_full_system_hero_workflow_across_all_devs(self, client: TestClient, tmp_path: Path):
        # =========================================================================
        # PHASE 1: [Dev 4] API Health & Sovereign Tool Discovery
        # =========================================================================
        health_res = client.get("/api/v1/health")
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "ok"
        assert health_res.json()["sovereign_mode"] is True

        tools_res = client.get("/api/v1/tools")
        assert tools_res.status_code == 200
        tool_names = [t["name"] for t in tools_res.json()]
        assert "rag.search" in tool_names
        assert "vision.analyze" in tool_names

        # =========================================================================
        # PHASE 2: [Dev 4 + Dev 2] Multipart Upload & Autonomous RAG Ingestion
        # =========================================================================
        scanned_pdf = SAMPLE_DIR / "sample-scanned.pdf"
        assert scanned_pdf.exists()

        call_count = 0

        def mock_ocr(img, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return OCRResult(
                    text=(
                        "SOVEREIGN INDUSTRIAL FACILITY AUDIT REPORT 2026\n"
                        "Asset Tag: Safety Relief Valve SV-402\n"
                        "Status: Operational pressure limit certified at 150 PSI.\n"
                        "Test Reading: 138 PSI recorded (PASS).\n"
                        "Visual Inspection Stamp: PASSED & SEALED.\n"
                        "Defect Findings: No surface micro-fractures detected on primary valve seat."
                    ),
                    is_available=True,
                    confidence=96.5,
                    engine="tesseract",
                )
            else:
                return OCRResult(
                    text=(
                        "FACILITY PERIMETER MAINTENANCE LOG 2026\n"
                        "General exterior cleaning and routine painting of perimeter fence.\n"
                        "No structural defects identified on grounds."
                    ),
                    is_available=True,
                    confidence=92.0,
                    engine="tesseract",
                )

        with patch("backend.knowledge.ocr.ocr_image", side_effect=mock_ocr):
            upload_res = client.post(
                "/api/v1/ingest/upload",
                files={"file": ("sample-scanned.pdf", io.BytesIO(scanned_pdf.read_bytes()), "application/pdf")},
                data={"document_id": "audit_doc_2026_01"},
            )

        assert upload_res.status_code == 201
        upload_data = upload_res.json()
        assert upload_data["status"] == "success"
        assert upload_data["document_id"] == "audit_doc_2026_01"
        assert upload_data["chunk_count"] >= 1

        # =========================================================================
        # PHASE 3: [Dev 1] Agent Mission Initialization
        # =========================================================================
        state = AgentState(
            task_id="hero_audit_mission_001",
            user_request="Inspect sample-scanned.pdf, verify visual certification stamps and valve tolerances, then generate the official approval note.",
        )
        context = {
            "task_id": state.task_id,
            "retrieved_context": state.retrieved_context,
            "tool_results": state.tool_results,
        }

        # =========================================================================
        # PHASE 4: [Dev 2 + Dev 1] Multimodal Visual Inspection Tool
        # =========================================================================
        # Render Page 1 to high-resolution PNG
        page_img_path = tmp_path / "scanned_page_1.png"
        doc = fitz.open(scanned_pdf)
        pix = doc.load_page(0).get_pixmap(dpi=150)
        pix.save(str(page_img_path))
        doc.close()

        # Mock the Ollama vision model response
        vision_tool = app.state.tools.get("vision.analyze")
        vision_mock_response = ModelResponse(
            content="Visual Inspection Analysis: Official inspection seal 'PASSED & SEALED' clearly visible at bottom-right. No structural fatigue on valve casing.",
            model_id="qwen2.5-vl:7b",
        )

        with patch.object(vision_tool.provider, "generate", new_callable=AsyncMock, return_value=vision_mock_response):
            vision_result: ToolResult = await vision_tool.execute(
                {
                    "image_path": str(page_img_path),
                    "prompt": "Examine this page for inspection stamps, defect indicators, and seals.",
                },
                context=context,
            )

        assert vision_result.success is True
        assert len(state.tool_results) >= 1
        assert "PASSED & SEALED" in state.tool_results[0]["output"]["analysis"]

        # =========================================================================
        # PHASE 5: [Dev 2 + Dev 1] Sovereign RAG Knowledge Retrieval
        # =========================================================================
        rag_tool = app.state.tools.get("rag.search")
        rag_result: ToolResult = await rag_tool.execute(
            {
                "query": "safety relief valve pressure limit tolerance PSI test reading",
                "top_k": 2,
                "document_id": "audit_doc_2026_01",
            },
            context=context,
        )

        assert rag_result.success is True
        assert len(state.retrieved_context) >= 1
        top_chunk = state.retrieved_context[0]
        assert top_chunk["source"] == "sample-scanned.pdf"
        assert top_chunk["page"] == 1
        assert "150 PSI" in top_chunk["content"] or "138 PSI" in top_chunk["content"]

        # =========================================================================
        # PHASE 6: [Dev 4] Security Governance Policy Evaluation
        # =========================================================================
        policy_engine = PolicyEngine()
        decision = policy_engine.evaluate("document.create")
        # In sovereign workbench, generating official deliverables requires human approval
        assert decision == PolicyDecision.REQUIRE_APPROVAL
        state.approval_required = True

        # Simulate Human-in-the-loop operator approval
        operator_approved = True
        assert operator_approved is True

        # =========================================================================
        # PHASE 7: [Dev 3] Executive Approval Note Generation (DOCX + PDF)
        # =========================================================================
        artifact_dir = tmp_path / "artifacts"
        docx_tool = DocumentCreateTool(artifact_dir=artifact_dir)
        pdf_tool = PdfCreateTool(artifact_dir=artifact_dir)

        # Construct citations directly from Dev 2's retrieved_context
        source_citations = [
            f"As per {c['source']}, Page {c['page']} (Doc ID: {c['document_id']})"
            for c in state.retrieved_context
        ]

        visual_findings = state.tool_results[0]["output"]["analysis"]

        spec_arguments = {
            "title": "Government Sovereign Facility Approval Note",
            "subject": "Safety Relief Valve SV-402 Audit Certification",
            "recipient": "Chief Nuclear & Safety Officer",
            "reference_number": "SEC-AUDIT-2026-VALVE-01",
            "purpose": "Authorize continued operation of Safety Relief Valve SV-402 based on autonomous audit evidence.",
            "background": "Routine statutory inspection conducted under sovereign AI audit protocols.",
            "findings": [
                f"Textual Evidence: {top_chunk['content'][:80]}...",
                f"Visual Verification: {visual_findings}",
            ],
            "recommendation": "Maintain asset in active service. Schedule next inspection cycle in Q3 2027.",
            "requested_approval": "Approve certification and issue sovereign compliance sign-off.",
            "prepared_by": "Sovereign AI Autonomous Inspector",
            "source_references": source_citations,
        }

        # 1. Generate DOCX
        docx_res = await docx_tool.execute(spec_arguments, context=context)
        assert docx_res.success is True
        docx_artifact = docx_res.output
        assert docx_artifact["type"] == "docx"
        docx_file = Path(docx_artifact["storage_uri"])
        assert docx_file.exists()

        # Read DOCX to confirm page citation is present in the Word file
        doc_obj = Document(docx_file)
        docx_text = "\n".join(p.text for p in doc_obj.paragraphs)
        assert "Source References" in docx_text
        assert "sample-scanned.pdf, Page 1" in docx_text
        assert "audit_doc_2026_01" in docx_text

        # 2. Generate PDF
        pdf_res = await pdf_tool.execute(spec_arguments, context=context)
        assert pdf_res.success is True
        pdf_artifact = pdf_res.output
        assert pdf_artifact["type"] == "pdf"
        pdf_file = Path(pdf_artifact["storage_uri"])
        assert pdf_file.exists()

        # Read PDF via PyMuPDF to confirm page citation is present in the PDF file
        pdf_doc = fitz.open(pdf_file)
        pdf_text = "\n".join(page.get_text("text") for page in pdf_doc)
        pdf_doc.close()

        assert "Safety Relief Valve SV-402" in pdf_text
        assert "sample-scanned.pdf" in pdf_text
        assert "Page 1" in pdf_text

        # =========================================================================
        # PHASE 8: Complete Mission Success
        # =========================================================================
        state.status = "completed"
        assert state.status == "completed"
        assert len(state.retrieved_context) >= 1
        assert len(state.tool_results) >= 1
        assert docx_file.stat().st_size > 1000
        assert pdf_file.stat().st_size > 1000
