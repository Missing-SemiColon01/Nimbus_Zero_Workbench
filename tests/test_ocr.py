"""
tests/test_ocr.py
==================
Unit tests for backend/knowledge/ocr.py (Day 1 — Task 1.2: OCR Engine)

Tests are fully self-contained using PIL to generate in-memory images and
unittest.mock to simulate Tesseract responses and missing binary states.
"""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image, ImageDraw

from backend.knowledge.ocr import (
    OCRResult,
    _load_image,
    clean_ocr_text,
    extract_text_from_image,
    is_tesseract_available,
    ocr_image,
)


# -- fixtures / helpers --------------------------------------------------------

def _create_sample_image(text: str = "Test") -> Image.Image:
    """Create a small in-memory RGB image with some painted text."""
    img = Image.new("RGB", (200, 60), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((10, 20), text, fill=(0, 0, 0))
    return img


# -- tests ---------------------------------------------------------------------

class TestOCRResult:
    def test_has_text_true_on_clean_text(self):
        result = OCRResult(text="Inspection passed at valve #4", is_available=True)
        assert result.has_text is True

    def test_has_text_false_when_empty(self):
        result = OCRResult(text="   \n  ", is_available=True)
        assert result.has_text is False

    def test_has_text_false_when_unavailable(self):
        result = OCRResult(
            text="[OCR unavailable: Tesseract OCR is not installed on the system]",
            is_available=False,
        )
        assert result.has_text is False

    def test_has_text_false_on_ocr_error(self):
        result = OCRResult(
            text="[OCR error: Subprocess timeout]",
            is_available=False,
            error="Subprocess timeout",
        )
        assert result.has_text is False


class TestCleanOcrText:
    def test_reconnects_hyphenated_words(self):
        raw = "The sovereign archi-\ntecture is robust."
        cleaned = clean_ocr_text(raw)
        assert "architecture" in cleaned
        assert "archi-\ntecture" not in cleaned

    def test_strips_form_feed_and_non_breaking_spaces(self):
        raw = "Hello\x0cWorld\xa02024"
        cleaned = clean_ocr_text(raw)
        assert cleaned == "HelloWorld 2024"

    def test_collapses_excessive_blank_lines(self):
        raw = "Line 1\n\n\n\n\nLine 2"
        cleaned = clean_ocr_text(raw)
        assert cleaned == "Line 1\n\nLine 2"

    def test_empty_input_returns_empty(self):
        assert clean_ocr_text("") == ""
        assert clean_ocr_text(None) == ""  # type: ignore


class TestImageLoading:
    def test_load_pil_image_returns_same(self):
        img = _create_sample_image()
        loaded = _load_image(img)
        assert loaded is img

    def test_load_from_bytes(self):
        img = _create_sample_image()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        loaded = _load_image(img_bytes)
        assert isinstance(loaded, Image.Image)
        assert loaded.size == (200, 60)

    def test_load_from_path(self, tmp_path):
        img = _create_sample_image()
        path = tmp_path / "sample.png"
        img.save(path)

        loaded = _load_image(path)
        assert isinstance(loaded, Image.Image)

    def test_load_from_string_path(self, tmp_path):
        img = _create_sample_image()
        path = tmp_path / "sample.png"
        img.save(path)

        loaded = _load_image(str(path))
        assert isinstance(loaded, Image.Image)

    def test_load_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            _load_image(tmp_path / "does_not_exist.png")

    def test_load_unsupported_type_raises(self):
        with pytest.raises(TypeError):
            _load_image(12345)  # type: ignore


class TestTesseractAvailability:
    def test_cached_when_unavailable(self):
        with patch("backend.knowledge.ocr.pytesseract.get_tesseract_version", side_effect=FileNotFoundError("not found")):
            available = is_tesseract_available(force_recheck=True)
            assert available is False

    def test_cached_when_available(self):
        with patch("backend.knowledge.ocr.pytesseract.get_tesseract_version", return_value="5.3.0"):
            available = is_tesseract_available(force_recheck=True)
            assert available is True


class TestOcrImage:
    def test_graceful_fallback_when_tesseract_missing(self):
        """When Tesseract is not installed, ocr_image must NOT raise an exception."""
        with patch("backend.knowledge.ocr.is_tesseract_available", return_value=False):
            img = _create_sample_image()
            result = ocr_image(img)
            assert result.is_available is False
            assert "[OCR unavailable" in result.text
            assert result.has_text is False

    def test_successful_ocr_mocked(self):
        """When Tesseract runs successfully, returns cleaned text."""
        img = _create_sample_image()
        mock_text = "Valve pressure: 120 PSI\x0c"

        with patch("backend.knowledge.ocr.is_tesseract_available", return_value=True), \
             patch("backend.knowledge.ocr.pytesseract.image_to_string", return_value=mock_text):
            result = ocr_image(img)
            assert result.is_available is True
            assert result.text == "Valve pressure: 120 PSI"
            assert result.has_text is True

    def test_compute_confidence_mocked(self):
        """When compute_confidence=True, calculates average confidence from word data."""
        img = _create_sample_image()
        mock_data = {
            "text": ["Valve", "pressure", ""],
            "conf": [95, 85, -1],  # -1 represents non-word entries in Tesseract
        }

        with patch("backend.knowledge.ocr.is_tesseract_available", return_value=True), \
             patch("backend.knowledge.ocr.pytesseract.image_to_string", return_value="Valve pressure"), \
             patch("backend.knowledge.ocr.pytesseract.image_to_data", return_value=mock_data):
            result = ocr_image(img, compute_confidence=True)
            assert result.is_available is True
            assert result.confidence == 90.0

    def test_ocr_runtime_exception_handled_gracefully(self):
        """Runtime exception during OCR extraction returns error result without crashing."""
        img = _create_sample_image()

        with patch("backend.knowledge.ocr.is_tesseract_available", return_value=True), \
             patch("backend.knowledge.ocr.pytesseract.image_to_string", side_effect=RuntimeError("Engine crash")):
            result = ocr_image(img)
            assert result.is_available is False
            assert "[OCR error" in result.text
            assert "Engine crash" in (result.error or "")


class TestExtractTextFromImage:
    def test_returns_plain_text_on_success(self):
        img = _create_sample_image()
        with patch("backend.knowledge.ocr.ocr_image", return_value=OCRResult(text="Extracted text", is_available=True)):
            text = extract_text_from_image(img)
            assert text == "Extracted text"

    def test_returns_fallback_when_ocr_fails(self):
        img = _create_sample_image()
        with patch("backend.knowledge.ocr.ocr_image", return_value=OCRResult(text="[OCR unavailable]", is_available=False)):
            text = extract_text_from_image(img, fallback_text="DEFAULT")
            assert text == "DEFAULT"
