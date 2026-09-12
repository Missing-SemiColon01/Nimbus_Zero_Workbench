"""
tests/test_pdf_parser.py
=========================
Unit tests for backend/knowledge/pdf_parser.py (Day 1 — Task 1.1)

Tests are fully self-contained — they generate tiny in-memory PDFs via
PyMuPDF so no external PDF fixture files are needed.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
import pytest

from backend.knowledge.pdf_parser import (
    ParsedDocument,
    ParsedPage,
    parse_pdf,
)


# -- helpers -------------------------------------------------------------------

def _make_pdf(tmp_path: Path, pages: list[str], filename: str = "test.pdf") -> Path:
    """Create a minimal PDF with one text string per page."""
    pdf_path = tmp_path / filename
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


# -- tests ---------------------------------------------------------------------

class TestParsedPageDataclass:
    def test_fields_accessible(self):
        p = ParsedPage(
            page_number=1,
            text="hello",
            used_ocr=False,
            image_count=0,
            width_pt=595.0,
            height_pt=842.0,
        )
        assert p.page_number == 1
        assert p.text == "hello"
        assert p.used_ocr is False


class TestParsedDocumentHelpers:
    def test_full_text_joins_pages(self, tmp_path):
        pdf_path = _make_pdf(tmp_path, ["First page text.", "Second page text."])
        doc = parse_pdf(pdf_path)
        full = doc.full_text()
        assert "[PAGE 1]" in full
        assert "[PAGE 2]" in full
        assert "First page" in full
        assert "Second page" in full

    def test_ocr_page_count_zero_for_digital_pdf(self, tmp_path):
        pdf_path = _make_pdf(tmp_path, ["Enough text to skip OCR " * 5])
        doc = parse_pdf(pdf_path)
        assert doc.ocr_page_count == 0


class TestParsePdf:
    def test_returns_parsed_document(self, tmp_path):
        pdf_path = _make_pdf(tmp_path, ["Hello World"])
        result = parse_pdf(pdf_path)
        assert isinstance(result, ParsedDocument)

    def test_page_count_matches(self, tmp_path):
        pdf_path = _make_pdf(tmp_path, ["Page 1", "Page 2", "Page 3"])
        result = parse_pdf(pdf_path)
        assert result.page_count == 3
        assert len(result.pages) == 3

    def test_text_extracted(self, tmp_path):
        pdf_path = _make_pdf(tmp_path, ["The quick brown fox jumps over the lazy dog."])
        result = parse_pdf(pdf_path)
        assert "quick brown fox" in result.pages[0].text

    def test_page_numbers_are_one_indexed(self, tmp_path):
        pdf_path = _make_pdf(tmp_path, ["A", "B", "C"])
        result = parse_pdf(pdf_path)
        numbers = [p.page_number for p in result.pages]
        assert numbers == [1, 2, 3]

    def test_source_path_stored(self, tmp_path):
        pdf_path = _make_pdf(tmp_path, ["content"])
        result = parse_pdf(pdf_path)
        assert result.source_path == pdf_path.resolve()

    def test_selective_pages(self, tmp_path):
        pdf_path = _make_pdf(tmp_path, ["Alpha", "Beta", "Gamma"])
        result = parse_pdf(pdf_path, pages=[1, 3])
        assert len(result.pages) == 2
        assert result.pages[0].page_number == 1
        assert result.pages[1].page_number == 3
        assert "Alpha" in result.pages[0].text
        assert "Gamma" in result.pages[1].text

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_pdf(tmp_path / "missing.pdf")

    def test_invalid_page_number_raises(self, tmp_path):
        pdf_path = _make_pdf(tmp_path, ["Only one page"])
        with pytest.raises(ValueError, match="out of range"):
            parse_pdf(pdf_path, pages=[5])

    def test_accepts_string_path(self, tmp_path):
        pdf_path = _make_pdf(tmp_path, ["String path test"])
        result = parse_pdf(str(pdf_path))          # str, not Path
        assert len(result.pages) == 1

    def test_width_height_populated(self, tmp_path):
        pdf_path = _make_pdf(tmp_path, ["Page size check"])
        result = parse_pdf(pdf_path)
        page = result.pages[0]
        assert page.width_pt > 0
        assert page.height_pt > 0
