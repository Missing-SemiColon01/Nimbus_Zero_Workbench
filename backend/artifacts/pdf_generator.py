"""Local PDF approval-note generation using the already-provisioned PyMuPDF library."""

import re
from pathlib import Path

import fitz

from backend.artifacts.contracts import ApprovalNoteSpec, Artifact, artifact_from_path
from backend.artifacts.theme import WorkbenchTheme


class PdfApprovalNoteGenerator:
    """Render an ApprovalNoteSpec into a readable, standalone PDF."""

    page_width = 595
    page_height = 842
    margin = 54
    bottom_margin = 54

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)

    def generate(self, spec: ApprovalNoteSpec, *, task_id: str) -> Artifact:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        document = fitz.open()
        page, cursor = self._new_page(document)
        page, cursor = self._line(page, cursor, spec.title, 19, WorkbenchTheme.navy, bold=True, align=fitz.TEXT_ALIGN_CENTER)
        page, cursor = self._line(page, cursor + 10, f"Date: {spec.document_date.strftime('%d %B %Y')}", 10, WorkbenchTheme.dark)
        if spec.reference_number:
            page, cursor = self._line(page, cursor, f"Reference: {spec.reference_number}", 10, WorkbenchTheme.dark)
        if spec.recipient:
            page, cursor = self._line(page, cursor, f"To: {spec.recipient}", 10, WorkbenchTheme.dark)
        page, cursor = self._line(page, cursor + 5, f"Subject: {spec.subject}", 11, WorkbenchTheme.navy, bold=True)

        sections: list[tuple[str, list[str]]] = [("Purpose", [spec.purpose])]
        if spec.background:
            sections.append(("Background", [spec.background]))
        if spec.findings:
            sections.append(("Key Findings", [f"• {finding}" for finding in spec.findings]))
        sections.extend([("Recommendation", [spec.recommendation]), ("Approval Requested", [spec.requested_approval])])
        if spec.source_references:
            sections.append(("Source References", [f"• {reference}" for reference in spec.source_references]))

        for heading, paragraphs in sections:
            page, cursor = self._ensure_space(document, page, cursor, 45)
            page, cursor = self._line(page, cursor + 8, heading, 12, WorkbenchTheme.navy, bold=True)
            for paragraph in paragraphs:
                page, cursor = self._paragraph(document, page, cursor, paragraph)
        if spec.prepared_by:
            page, cursor = self._line(page, cursor + 16, f"Prepared by: {spec.prepared_by}", 10, WorkbenchTheme.slate)

        path = self.output_dir / f"{self._safe_name(spec.subject)}.pdf"
        document.save(path, garbage=4, deflate=True)
        document.close()
        return artifact_from_path(path, artifact_type="pdf", mime_type="application/pdf", task_id=task_id, metadata={"subject": spec.subject, "theme": WorkbenchTheme.name})

    def _new_page(self, document: fitz.Document) -> tuple[fitz.Page, float]:
        page = document.new_page(width=self.page_width, height=self.page_height)
        page.draw_rect(fitz.Rect(0, 0, 7, self.page_height), color=None, fill=self._color(WorkbenchTheme.teal))
        return page, float(self.margin)

    def _ensure_space(self, document: fitz.Document, page: fitz.Page, cursor: float, needed: float) -> tuple[fitz.Page, float]:
        return self._new_page(document) if cursor + needed > self.page_height - self.bottom_margin else (page, cursor)

    def _line(self, page: fitz.Page, cursor: float, text: str, size: float, color: str, *, bold: bool = False, align: int = fitz.TEXT_ALIGN_LEFT) -> tuple[fitz.Page, float]:
        rect = fitz.Rect(self.margin, cursor, self.page_width - self.margin, cursor + size + 9)
        page.insert_textbox(rect, text, fontsize=size, fontname="hebo" if bold else "helv", color=self._color(color), align=align)
        return page, cursor + size + 9

    def _paragraph(self, document: fitz.Document, page: fitz.Page, cursor: float, text: str) -> tuple[fitz.Page, float]:
        words, line = text.split(), ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if fitz.get_text_length(candidate, fontname="helv", fontsize=10) > self.page_width - (self.margin * 2):
                page, cursor = self._ensure_space(document, page, cursor, 22)
                page, cursor = self._line(page, cursor, line, 10, WorkbenchTheme.dark)
                line = word
            else:
                line = candidate
        if line:
            page, cursor = self._ensure_space(document, page, cursor, 22)
            page, cursor = self._line(page, cursor, line, 10, WorkbenchTheme.dark)
        return page, cursor + 3

    @staticmethod
    def _color(value: str) -> tuple[float, float, float]:
        return tuple(int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")[:80] or "approval-note"
