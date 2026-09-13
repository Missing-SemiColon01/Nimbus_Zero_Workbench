"""Local structural validation for DOCX and PPTX deliverables."""

from pathlib import Path

from docx import Document
from pptx import Presentation

from backend.artifacts.contracts import Artifact, ArtifactValidation


class OfficeArtifactValidator:
    """Verify that editable Office artifacts open and contain expected content."""

    def validate(self, artifact: Artifact, *, required_text: list[str] | None = None) -> ArtifactValidation:
        path = Path(artifact.storage_uri)
        if artifact.type not in {"docx", "pptx"}:
            return ArtifactValidation(
                artifact_id=artifact.id,
                valid=False,
                checks={"supported_type": False},
                findings=["Artifact type must be docx or pptx."],
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
        return ArtifactValidation(
            artifact_id=artifact.id,
            valid=all(checks.values()),
            checks=checks,
            findings=findings,
        )

    @staticmethod
    def _extract_content(path: Path, artifact_type: str) -> tuple[str, int]:
        if artifact_type == "docx":
            document = Document(path)
            text = "\n".join(paragraph.text for paragraph in document.paragraphs)
            return text, len(document.paragraphs)

        presentation = Presentation(path)
        slide_text = []
        for slide in presentation.slides:
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    slide_text.append(shape.text)
        return "\n".join(slide_text), len(presentation.slides)
