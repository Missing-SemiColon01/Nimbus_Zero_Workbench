"""Local structural validation for DOCX and PPTX deliverables."""

import subprocess
from pathlib import Path

from docx import Document
from pptx import Presentation

from backend.artifacts.contracts import Artifact, ArtifactValidation
from backend.artifacts.office_renderer import LibreOfficeRenderer


class OfficeArtifactValidator:
    """Verify that editable Office artifacts open and contain expected content."""

    def __init__(self, renderer: LibreOfficeRenderer | None = None):
        self.renderer = renderer

    def validate(self, artifact: Artifact, *, required_text: list[str] | None = None, render_preview: bool = False) -> ArtifactValidation:
        path = Path(artifact.storage_uri)
        if artifact.type not in {"docx", "pptx", "xlsx"}:
            return ArtifactValidation(
                artifact_id=artifact.id,
                valid=False,
                checks={"supported_type": False},
                findings=["Artifact type must be docx, pptx, or xlsx."],
            )
        if not path.is_file():
            return ArtifactValidation(
                artifact_id=artifact.id,
                valid=False,
                checks={"file_exists": False},
                findings=["Artifact file does not exist."],
            )
        try:
            text, unit_count = self._extract_content(path, artifact.type)
        except (OSError, ValueError, KeyError, TypeError) as error:
            return ArtifactValidation(
                artifact_id=artifact.id,
                valid=False,
                checks={"artifact_opened": False},
                findings=[f"Artifact could not be opened: {error}"],
            )

        expected = required_text or []
        checks = {
            "artifact_opened": True,
            "has_content": unit_count > 0 and bool(text.strip()),
            "required_text_present": all(value in text for value in expected),
        }
        findings = []
        if not checks["has_content"]:
            findings.append("Artifact has no readable content.")
        if not checks["required_text_present"]:
            findings.append("Artifact is missing expected content.")
        preview_path = None
        if render_preview:
            if not self.renderer:
                checks["preview_rendered"] = False
                findings.append("LibreOffice renderer was not configured.")
            else:
                try:
                    _, preview_path = self.renderer.render(path, preview_name=artifact.id)
                    checks["preview_rendered"] = True
                except (FileNotFoundError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                    checks["preview_rendered"] = False
                    findings.append(f"Visual preview could not be rendered: {error}")
        core_valid = checks["artifact_opened"] and checks["has_content"] and checks["required_text_present"]
        return ArtifactValidation(
            artifact_id=artifact.id,
            valid=core_valid,
            checks=checks,
            findings=findings,
            preview_path=str(preview_path.resolve()) if preview_path else None,
        )

    @staticmethod
    def _extract_content(path: Path, artifact_type: str) -> tuple[str, int]:
        if artifact_type == "docx":
            document = Document(path)
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
            return text, len(document.paragraphs)

        if artifact_type == "xlsx":
            from openpyxl import load_workbook
            wb = load_workbook(path, read_only=True, data_only=True)
            cell_texts = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    cell_texts.extend(str(v) for v in row if v is not None)
            sheet_count = len(wb.worksheets)
            wb.close()
            return "\n".join(cell_texts), sheet_count

        presentation = Presentation(path)
        slide_text = []
        for slide in presentation.slides:
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    slide_text.append(shape.text)
        return "\n".join(slide_text), len(presentation.slides)
