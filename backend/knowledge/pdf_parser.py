"""
backend/knowledge/pdf_parser.py
================================
Day 1 — Task 1.1: PDF Parser

Extracts text and images from a PDF file.

Strategy (two-pass per page):
  Pass 1 — PyMuPDF (fitz) text extraction  ->  fast, zero-network, exact Unicode
  Pass 2 — Tesseract OCR on page images    ->  only triggered when Pass 1 yields
             very little text (scanned / image-heavy pages)

Output is a single ParsedDocument dataclass so callers never touch fitz objects.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)

# -- tunables ------------------------------------------------------------------
# If a page has fewer characters than this we consider it "image-heavy" and
# fall back to OCR.  Tweak if you find pages switching too eagerly.
_MIN_TEXT_CHARS_BEFORE_OCR: int = 50

# DPI used when rendering a page to a bitmap for Tesseract.
# 200 is a solid trade-off between quality and speed on a dev laptop.
_OCR_DPI: int = 200


# -- data contracts ------------------------------------------------------------
@dataclass
class ParsedPage:
    """Single page extracted from a PDF."""

    page_number: int           # 1-indexed (human-friendly)
    text: str                  # plain text (may be from OCR)
    used_ocr: bool             # True when Tesseract was invoked for this page
    image_count: int           # number of embedded images found on the page
    width_pt: float            # page width in PDF points
    height_pt: float           # page height in PDF points


@dataclass
class ParsedDocument:
    """Full result of parsing one PDF file."""

    source_path: Path
    page_count: int
    pages: list[ParsedPage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    # -- convenience helpers --------------------------------------------------
    def full_text(self) -> str:
        """Concatenate all pages with a clear page separator."""
        parts: list[str] = []
        for page in self.pages:
            parts.append(f"[PAGE {page.page_number}]\n{page.text.strip()}")
        return "\n\n".join(parts)

    @property
    def ocr_page_count(self) -> int:
        """How many pages needed OCR fallback."""
        return sum(1 for p in self.pages if p.used_ocr)


# -- internal helpers ----------------------------------------------------------
def _render_page_to_pil(page: fitz.Page, dpi: int = _OCR_DPI) -> Image.Image:
    """Render a fitz page to a Pillow Image ready for Tesseract."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)   # 72 pt = 1 inch in PDF world
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(img_bytes))


def _ocr_page(page: fitz.Page, dpi: int = _OCR_DPI) -> str:
    """Run OCR on a rendered page image via the OCR engine."""
    from backend.knowledge.ocr import ocr_image

    pil_image = _render_page_to_pil(page, dpi)
    result = ocr_image(pil_image)
    return result.text if result.has_text else ""


def _extract_page(fitz_page: fitz.Page) -> ParsedPage:
    """
    Extract text from a single fitz Page object.

    Flow:
      1. Try PyMuPDF text extraction first (fast path).
      2. If the result is below _MIN_TEXT_CHARS_BEFORE_OCR, attempt OCR.
      3. Count embedded images (useful metadata for the chunker later).
    """
    page_num = fitz_page.number + 1   # convert 0-indexed to 1-indexed
    rect = fitz_page.rect

    # Pass 1 -- PyMuPDF native text
    raw_text: str = fitz_page.get_text("text")
    text = raw_text.strip()
    used_ocr = False

    # Pass 2 -- OCR fallback for scanned/image-heavy pages
    if len(text) < _MIN_TEXT_CHARS_BEFORE_OCR:
        logger.debug(
            "Page %d: only %d chars from PyMuPDF -- attempting OCR",
            page_num,
            len(text),
        )
        try:
            ocr_text = _ocr_page(fitz_page).strip()
            if ocr_text:
                text = ocr_text
                used_ocr = True
                logger.debug("Page %d: OCR yielded %d chars", page_num, len(ocr_text))
        except Exception as exc:      # OCR failing must NOT break the whole parse
            logger.warning("Page %d: OCR failed -- %s", page_num, exc)

    # Count embedded images (pass to ParsedPage for downstream use)
    image_count = len(fitz_page.get_images(full=False))

    return ParsedPage(
        page_number=page_num,
        text=text,
        used_ocr=used_ocr,
        image_count=image_count,
        width_pt=rect.width,
        height_pt=rect.height,
    )


# -- public API ----------------------------------------------------------------
def parse_pdf(source: str | Path, pages: Sequence[int] | None = None) -> ParsedDocument:
    """
    Parse a PDF file and return a ParsedDocument.

    Parameters
    ----------
    source:
        Absolute or relative path to the PDF file.
    pages:
        Optional list of 1-indexed page numbers to parse.
        None (default) means parse all pages.

    Returns
    -------
    ParsedDocument
        Structured result with per-page text and metadata.

    Raises
    ------
    FileNotFoundError
        When source does not exist on disk.
    ValueError
        When source is not a valid PDF, or a page number is out of range.
    """
    source_path = Path(source).resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"PDF not found: {source_path}")

    logger.info("Parsing PDF: %s", source_path.name)

    try:
        doc: fitz.Document = fitz.open(str(source_path))
    except Exception as exc:
        raise ValueError(f"Cannot open PDF '{source_path.name}': {exc}") from exc

    # Determine which fitz page indices (0-based) to process
    if pages is not None:
        fitz_indices = []
        for p in pages:
            if not (1 <= p <= doc.page_count):
                raise ValueError(
                    f"Page {p} is out of range for '{source_path.name}' "
                    f"(1-{doc.page_count})"
                )
            fitz_indices.append(p - 1)
    else:
        fitz_indices = list(range(doc.page_count))

    # Store page_count BEFORE closing the document.
    # PyMuPDF raises ValueError if you access .page_count on a closed Document.
    total_pages: int = doc.page_count

    parsed_pages: list[ParsedPage] = []
    for idx in fitz_indices:
        fitz_page = doc.load_page(idx)
        parsed_page = _extract_page(fitz_page)
        parsed_pages.append(parsed_page)

    # Grab PDF metadata (author, title, etc.) -- may be empty dicts
    raw_meta: dict = doc.metadata or {}
    # Filter out empty strings so downstream code gets clean data
    metadata = {k: v for k, v in raw_meta.items() if v}

    doc.close()

    result = ParsedDocument(
        source_path=source_path,
        page_count=total_pages,
        pages=parsed_pages,
        metadata=metadata,
    )

    logger.info(
        "Parsed '%s': %d/%d pages, %d needed OCR",
        source_path.name,
        len(parsed_pages),
        result.page_count,
        result.ocr_page_count,
    )
    return result
