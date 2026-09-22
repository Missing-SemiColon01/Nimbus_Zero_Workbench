"""
backend/knowledge/ocr.py
=========================
Day 1 — Task 1.2: OCR Engine

Performs Optical Character Recognition on page images, scanned documents,
and standalone image files.

Architecture & Strategy:
  - Primary Engine: Tesseract via pytesseract.
  - Graceful Fallback: If Tesseract binary is not installed on the system,
    it logs a clear warning and returns a structured fallback indicator
    rather than crashing the pipeline.
  - Multi-Input Support: Accepts PIL Image, file Path, str path, or raw bytes.
  - Text Cleaning: Fixes line-break hyphenations and normalizes OCR artifacts.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None  # type: ignore

logger = logging.getLogger(__name__)

# Cached availability flag: None = untested, True = ready, False = unavailable
_TESSERACT_AVAILABLE: bool | None = None


@dataclass
class OCRResult:
    """Structured result of an OCR extraction."""

    text: str
    is_available: bool = True
    confidence: float | None = None
    engine: str = "tesseract"
    error: str | None = None

    @property
    def has_text(self) -> bool:
        """True if non-empty text was extracted and OCR was operational."""
        return self.is_available and bool(self.text.strip()) and not self.text.startswith("[OCR")


def is_tesseract_available(force_recheck: bool = False) -> bool:
    """
    Check if pytesseract library AND the Tesseract binary are accessible.

    The check result is cached to avoid repeated subprocess/lookup overhead.
    """
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is not None and not force_recheck:
        return _TESSERACT_AVAILABLE

    if pytesseract is None:
        _TESSERACT_AVAILABLE = False
        return False

    try:
        # Calling get_tesseract_version validates that the binary is in PATH
        # and executable.
        _ = pytesseract.get_tesseract_version()
        _TESSERACT_AVAILABLE = True
        logger.info("Tesseract binary detected and available for OCR.")
    except Exception as exc:
        _TESSERACT_AVAILABLE = False
        logger.warning(
            "Tesseract OCR is not available on this system (%s). "
            "OCR operations will return fallback placeholders without crashing.",
            exc,
        )

    return _TESSERACT_AVAILABLE


def clean_ocr_text(raw_text: str) -> str:
    """
    Post-process raw OCR output to improve downstream chunking and retrieval.

    Fixes:
      1. Word hyphenations split across line breaks (e.g. 'struc-\\nture' -> 'structure')
      2. Form feed and control characters
      3. Excessive consecutive blank lines (> 2 newlines collapsed to 2)
      4. Trailing spaces on lines
    """
    if not raw_text:
        return ""

    # Replace form feed character
    text = raw_text.replace("\x0c", "").replace("\xa0", " ")

    # Reconnect hyphenated words split across newlines (e.g., 'trans-\\nformer' -> 'transformer')
    text = re.sub(r"(\w+)-\s*\n\s*(\w+)", r"\1\2", text)

    # Normalize carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip whitespace from individual lines
    lines = [line.strip() for line in text.split("\n")]

    # Collapse more than two consecutive empty lines
    cleaned_lines: list[str] = []
    consecutive_empty = 0
    for line in lines:
        if not line:
            consecutive_empty += 1
            if consecutive_empty <= 1:
                cleaned_lines.append("")
        else:
            consecutive_empty = 0
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def _load_image(image_input: Image.Image | Path | str | bytes) -> Image.Image:
    """Load various image input formats into a PIL Image."""
    if isinstance(image_input, Image.Image):
        return image_input

    if isinstance(image_input, (str, Path)):
        path = Path(image_input)
        if not path.exists():
            raise FileNotFoundError(f"Image file does not exist: {path}")
        return Image.open(path)

    if isinstance(image_input, bytes):
        return Image.open(io.BytesIO(image_input))

    raise TypeError(
        f"Unsupported image input type: {type(image_input)}. "
        "Expected PIL.Image.Image, Path, str, or bytes."
    )


def ocr_image(
    image: Image.Image | Path | str | bytes,
    lang: str = "eng",
    psm: int = 6,  # PSM 6 = Assume a single uniform block of text (better for documents)
    compute_confidence: bool = True,  # Enable confidence by default for quality
) -> OCRResult:
    """
    Extract text from an image using Tesseract OCR.

    Parameters
    ----------
    image:
        PIL Image, filesystem Path, string path, or image bytes.
    lang:
        Tesseract language code (default: 'eng').
    psm:
        Page segmentation mode (default: 6 - Assume a single uniform block of text).
        PSM 3 = Fully automatic page segmentation (original)
        PSM 6 = Assume a single uniform block of text (better for documents)
    compute_confidence:
        If True, calculates average word-level confidence score [0.0 - 100.0].
        Enabled by default for quality assessment.

    Returns
    -------
    OCRResult:
        Contains extracted text, availability flag, engine, confidence, and any error.
    """
    try:
        pil_image = _load_image(image)
    except Exception as exc:
        logger.error("Failed to load image for OCR: %s", exc)
        return OCRResult(
            text="",
            is_available=False,
            error=f"Image load error: {exc}",
        )

    # Check if Tesseract engine binary is installed
    if not is_tesseract_available():
        return OCRResult(
            text="[OCR unavailable: Tesseract OCR is not installed on the system]",
            is_available=False,
            error="Tesseract binary not found in PATH",
        )

    try:
        config = f"--psm {psm}"
        raw_text: str = pytesseract.image_to_string(pil_image, lang=lang, config=config)
        cleaned_text = clean_ocr_text(raw_text)

        confidence: float | None = None
        if compute_confidence:
            try:
                data: dict[str, list[Any]] = pytesseract.image_to_data(
                    pil_image,
                    lang=lang,
                    config=config,
                    output_type=pytesseract.Output.DICT,
                )
                confs = [
                    float(c)
                    for c in data.get("conf", [])
                    if str(c).lstrip("-").replace(".", "", 1).isdigit() and float(c) >= 0
                ]
                if confs:
                    confidence = round(sum(confs) / len(confs), 2)
            except Exception as conf_exc:
                logger.debug("Could not compute OCR confidence: %s", conf_exc)

        return OCRResult(
            text=cleaned_text,
            is_available=True,
            confidence=confidence,
            engine="tesseract",
        )

    except Exception as exc:
        logger.warning("OCR extraction failed: %s", exc)
        return OCRResult(
            text=f"[OCR error: {exc}]",
            is_available=False,
            error=str(exc),
        )


def extract_text_from_image(
    image: Image.Image | Path | str | bytes,
    fallback_text: str = "",
) -> str:
    """
    Convenience wrapper returning plain extracted text.

    If OCR is unavailable or fails, returns fallback_text (default empty string).
    """
    result = ocr_image(image)
    if result.has_text:
        return result.text
    return fallback_text
