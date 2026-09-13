from pathlib import Path

import fitz
from docx import Document
from pptx import Presentation

from backend.artifacts import (
    ApprovalNoteSpec,
    DocxGenerator,
    PdfApprovalNoteGenerator,
    PptxGenerator,
    PresentationSpec,
    SlideLayout,
    SlideSpec,
)
from backend.artifacts.contracts import ChartSeries


def test_docx_generator_creates_openable_approval_note(tmp_path: Path):
    artifact = DocxGenerator(tmp_path).generate(
        ApprovalNoteSpec(
            subject="Pump P-101 repair approval",
            recipient="Maintenance Manager",
            purpose="Obtain approval for the proposed repair.",
            findings=["Abnormal vibration observed during inspection."],
            recommendation="Repair the bearing assembly during the next shutdown.",
            requested_approval="Approve the repair work order.",
            source_references=["Inspection report IR-101, page 3"],
        ),
        task_id="task-123",
    )

    path = Path(artifact.storage_uri)
    assert path.exists()
    assert artifact.type == "docx"
    assert "Pump P-101 repair approval" in "\n".join(p.text for p in Document(path).paragraphs)


def test_pptx_generator_supports_all_day_one_layouts(tmp_path: Path):
    slides = [
        SlideSpec(layout=SlideLayout.TITLE, title="Inspection review", subtitle="September 2026"),
        SlideSpec(layout=SlideLayout.EXECUTIVE_SUMMARY, title="Executive summary", bullets=["Action is required"]),
        SlideSpec(layout=SlideLayout.TWO_COLUMN, title="Assessment", left_heading="Findings", left_items=["Vibration"], right_heading="Impact", right_items=["Reliability risk"]),
        SlideSpec(layout=SlideLayout.ARCHITECTURE, title="Workflow", diagram_nodes=["Report", "Analysis", "Approval"]),
        SlideSpec(layout=SlideLayout.DATA_CHART, title="Trend", chart_categories=["Jan", "Feb"], chart_series=[ChartSeries(name="Risk", values=[2, 4])]),
        SlideSpec(layout=SlideLayout.RECOMMENDATION, title="Decision", recommendation="Approve the repair", decision_points=["Assign owner", "Schedule shutdown"]),
    ]
    artifact = PptxGenerator(tmp_path).generate(PresentationSpec(title="Inspection review", slides=slides), task_id="task-123")

    path = Path(artifact.storage_uri)
    assert path.exists()
    assert artifact.type == "pptx"
    assert artifact.metadata["slide_count"] == 6
    assert len(Presentation(path).slides) == 6


def test_pdf_generator_creates_readable_approval_note(tmp_path: Path):
    artifact = PdfApprovalNoteGenerator(tmp_path).generate(
        ApprovalNoteSpec(
            subject="Pump P-101 repair approval",
            purpose="Obtain approval for the proposed repair.",
            findings=["Abnormal vibration observed during inspection."],
            recommendation="Repair the bearing assembly during the next shutdown.",
            requested_approval="Approve the repair work order.",
        ),
        task_id="task-123",
    )

    document = fitz.open(artifact.storage_uri)
    assert document.page_count == 1
    assert "Pump P-101 repair approval" in document[0].get_text()
    document.close()
