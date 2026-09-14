"""Read-only tool adapter for local artifact validation and visual QA."""

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.artifacts.contracts import Artifact
from backend.artifacts.office_renderer import LibreOfficeRenderer
from backend.artifacts.office_validator import OfficeArtifactValidator
from backend.artifacts.pdf_validator import PdfArtifactValidator
from backend.tools.contracts import Tool, ToolResult


class ArtifactValidateTool(Tool):
    """Validate a locally stored generated artifact without altering the original file."""

    name = "artifact.validate"
    description = "Validate a local DOCX, PPTX, or PDF artifact and optionally render a local QA preview."
    parameters = {
        "type": "object",
        "properties": {
            "artifact": {"type": "object", "description": "Artifact metadata returned by an artifact creation tool."},
            "required_text": {"type": "array", "items": {"type": "string"}},
            "render_preview": {"type": "boolean", "default": True},
        },
        "required": ["artifact"],
    }

    def __init__(self, preview_dir: Path):
        self.preview_dir = Path(preview_dir)

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        try:
            artifact = Artifact.model_validate(arguments.get("artifact"))
        except ValidationError as error:
            return ToolResult(success=False, output=None, error=f"Invalid artifact metadata: {error}")
        required_text = arguments.get("required_text", [])
        if not isinstance(required_text, list) or not all(isinstance(item, str) for item in required_text):
            return ToolResult(success=False, output=None, error="required_text must be a list of strings.")
        render_preview = arguments.get("render_preview", True)
        if not isinstance(render_preview, bool):
            return ToolResult(success=False, output=None, error="render_preview must be a boolean.")

        if artifact.type == "pdf":
            validation = PdfArtifactValidator(self.preview_dir).validate(artifact, required_text=required_text)
        elif artifact.type in {"docx", "pptx"}:
            renderer = LibreOfficeRenderer(self.preview_dir) if render_preview else None
            validation = OfficeArtifactValidator(renderer).validate(artifact, required_text=required_text, render_preview=render_preview)
        else:
            return ToolResult(success=False, output=None, error=f"Unsupported artifact type: {artifact.type}")
        output = validation.model_dump(mode="json")
        return ToolResult(
            success=validation.valid,
            output=output,
            error=None if validation.valid else "; ".join(validation.findings),
            artifacts=[validation.preview_path] if validation.preview_path else [],
        )
