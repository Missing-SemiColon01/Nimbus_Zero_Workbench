"""Tool-layer adapters for locally generated DOCX, PPTX, and PDF artifacts."""

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.artifacts.contracts import ApprovalNoteSpec, PresentationSpec
from backend.artifacts.docx_generator import DocxGenerator
from backend.artifacts.pptx_generator import PptxGenerator
from backend.artifacts.pdf_generator import PdfApprovalNoteGenerator
from backend.tools.contracts import Tool, ToolResult


class DocumentCreateTool(Tool):
    """Create a local approval-note DOCX from an ApprovalNoteSpec payload."""

    name = "document.create"
    description = "Create a local DOCX approval note from structured approval content."
    parameters = {
        "type": "object",
        "properties": {
            "subject": {"type": "string"},
            "purpose": {"type": "string"},
            "recommendation": {"type": "string"},
            "requested_approval": {"type": "string"},
            "findings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["subject", "purpose", "recommendation", "requested_approval"],
    }

    def __init__(self, artifact_dir: Path):
        self.generator = DocxGenerator(artifact_dir)

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        return _generate(
            generator=self.generator,
            spec_type=ApprovalNoteSpec,
            arguments=arguments,
            context=context,
        )


class PresentationCreateTool(Tool):
    """Create a local editable PPTX from a PresentationSpec payload."""

    name = "presentation.create"
    description = "Create a local editable PPTX presentation from a structured presentation specification."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "slides": {"type": "array", "items": {"type": "object"}},
        },
        "required": ["title", "slides"],
    }

    def __init__(self, artifact_dir: Path):
        self.generator = PptxGenerator(artifact_dir)

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        return _generate(
            generator=self.generator,
            spec_type=PresentationSpec,
            arguments=arguments,
            context=context,
        )


class PdfCreateTool(Tool):
    """Create a local approval-note PDF from an ApprovalNoteSpec payload."""

    name = "pdf.create"
    description = "Create a local PDF approval note from structured approval content."
    parameters = DocumentCreateTool.parameters

    def __init__(self, artifact_dir: Path):
        self.generator = PdfApprovalNoteGenerator(artifact_dir)

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        return _generate(
            generator=self.generator,
            spec_type=ApprovalNoteSpec,
            arguments=arguments,
            context=context,
        )


class SpreadsheetCreateTool(Tool):
    """Create a local styled XLSX spreadsheet from a SpreadsheetSpec payload."""

    name = "spreadsheet.create"
    description = "Create a local styled XLSX spreadsheet from structured spreadsheet data."
    parameters = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "sheets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "columns": {"type": "array", "items": {"type": "object"}},
                        "rows": {"type": "array", "items": {"type": "object"}},
                        "summary_row": {"type": "boolean"},
                    },
                    "required": ["title", "columns"],
                },
            },
        },
        "required": ["title", "sheets"],
    }

    def __init__(self, artifact_dir: Path):
        from backend.artifacts.xlsx_generator import XlsxGenerator
        self.generator = XlsxGenerator(artifact_dir)

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        from backend.artifacts.contracts import SpreadsheetSpec
        return _generate(
            generator=self.generator,
            spec_type=SpreadsheetSpec,
            arguments=arguments,
            context=context,
        )



def _generate(*, generator: Any, spec_type: Any, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
    """Keep validation and filesystem failures inside the normal tool-result contract."""
    task_id = context.get("task_id")
    if not task_id:
        return ToolResult(success=False, output=None, error="Artifact generation requires context.task_id")
    try:
        spec = spec_type.model_validate(arguments)
        artifact = generator.generate(spec, task_id=task_id)
    except (OSError, ValidationError, ValueError) as error:
        return ToolResult(success=False, output=None, error=str(error))
    return ToolResult(
        success=True,
        output=artifact.model_dump(mode="json"),
        artifacts=[artifact.storage_uri],
    )
