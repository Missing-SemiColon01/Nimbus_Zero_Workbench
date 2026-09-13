import asyncio
from pathlib import Path

from backend.artifacts.tools import DocumentCreateTool, PresentationCreateTool


def test_document_tool_generates_local_artifact(tmp_path: Path):
    result = asyncio.run(
        DocumentCreateTool(tmp_path).execute(
            {
                "subject": "Pump repair approval",
                "purpose": "Request approval for repair work.",
                "recommendation": "Repair the pump during the next shutdown.",
                "requested_approval": "Approve the repair work order.",
            },
            {"task_id": "task-42"},
        )
    )

    assert result.success
    assert result.output["task_id"] == "task-42"
    assert Path(result.artifacts[0]).exists()


def test_presentation_tool_returns_validation_error_without_task_id(tmp_path: Path):
    result = asyncio.run(PresentationCreateTool(tmp_path).execute({"title": "Review", "slides": []}, {}))

    assert not result.success
    assert result.error == "Artifact generation requires context.task_id"
