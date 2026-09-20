"""Offline LibreOffice conversion for Office-artifact visual QA."""

import asyncio
import shutil
import subprocess
from pathlib import Path

import fitz


class LibreOfficeRenderer:
    """Convert DOCX/PPTX to PDF and render the first page as a local PNG preview."""

    def __init__(self, output_dir: Path, *, soffice_path: Path | None = None, timeout_seconds: int = 60):
        self.output_dir = Path(output_dir)
        self.soffice_path = soffice_path or self.find_executable()
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def find_executable() -> Path | None:
        executable = shutil.which("soffice")
        candidates = [
            Path(executable) if executable else None,
            Path("C:/Program Files/LibreOffice/program/soffice.exe"),
            Path("C:/Program Files (x86)/LibreOffice/program/soffice.exe"),
        ]
        return next((candidate for candidate in candidates if candidate and candidate.is_file()), None)

    async def render(self, source_path: Path, *, preview_name: str) -> tuple[Path, Path]:
        if not self.soffice_path:
            raise RuntimeError("LibreOffice (soffice) is not installed or not discoverable.")
        if not source_path.is_file():
            raise FileNotFoundError(f"Artifact file does not exist: {source_path}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        command = [str(self.soffice_path), "--headless", "--convert-to", "pdf", "--outdir", str(self.output_dir), str(source_path)]
        result = await asyncio.to_thread(
            subprocess.run,
            command,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        pdf_path = self.output_dir / f"{source_path.stem}.pdf"
        if result.returncode != 0 or not pdf_path.is_file():
            detail = result.stderr.strip() or result.stdout.strip() or "no PDF output produced"
            raise RuntimeError(f"LibreOffice conversion failed: {detail}")
        preview_path = self.output_dir / f"{preview_name}-page-1.png"
        document = fitz.open(pdf_path)
        if document.page_count == 0:
            document.close()
            raise RuntimeError("LibreOffice produced a PDF with no pages.")
        document[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(preview_path)
        document.close()
        return pdf_path, preview_path
