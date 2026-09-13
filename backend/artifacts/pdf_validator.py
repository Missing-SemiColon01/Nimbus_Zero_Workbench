"""Local quality checks and preview rendering for generated PDF artifacts."""

from pathlib import Path

import fitz

from backend.artifacts.contracts import Artifact, ArtifactValidation


class PdfArtifactValidator:
    """Validate readability and render a temporary PNG preview without network access."""

    def __init__(self, preview_dir: Path):
        self.preview_dir = Path(preview_dir)

    def validate(self, artifact: Artifact, *, required_text: list[str] | None = None) -> ArtifactValidation:
        if artifact.type != "pdf":
            return ArtifactValidation(
                artifact_id=artifact.id,
                valid=False,
                checks={"is_pdf": False},
                findings=["Artifact type must be pdf."],
            )

        path = Path(artifact.storage_uri)
        if not path.is_file():
            return ArtifactValidation(
                artifact_id=artifact.id,
                valid=False,
                checks={"file_exists": False},
                findings=["PDF artifact file does not exist."],
            )

        try:
            document = fitz.open(path)
            page_count = document.page_count
            extracted_text = "\n".join(page.get_text() for page in document)
            has_text = bool(extracted_text.strip())
            expected = required_text or []
            expected_text_present = all(value in extracted_text for value in expected)
            preview_path = self._render_first_page(document, artifact.id) if page_count else None
            document.close()
        except (fitz.FileDataError, OSError, RuntimeError) as error:
            return ArtifactValidation(
                artifact_id=artifact.id,
                valid=False,
                checks={"pdf_opened": False},
                findings=[f"PDF could not be opened: {error}"],
            )

        checks = {
            "pdf_opened": True,
            "has_pages": page_count > 0,
            "has_extractable_text": has_text,
            "required_text_present": expected_text_present,
            "preview_rendered": preview_path is not None,
        }
        findings = []
        if not checks["has_pages"]:
            findings.append("PDF has no pages.")
        if not checks["has_extractable_text"]:
            findings.append("PDF contains no extractable text.")
        if not checks["required_text_present"]:
            findings.append("PDF is missing expected content.")
        if not checks["preview_rendered"]:
            findings.append("PDF preview could not be rendered.")
        return ArtifactValidation(
            artifact_id=artifact.id,
            valid=all(checks.values()),
            checks=checks,
            findings=findings,
            preview_path=str(preview_path.resolve()) if preview_path else None,
        )

    def _render_first_page(self, document: fitz.Document, artifact_id: str) -> Path:
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = self.preview_dir / f"{artifact_id}-page-1.png"
        pixmap = document[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        pixmap.save(preview_path)
        return preview_path
