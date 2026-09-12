"""backend.knowledge - RAG pipeline components (Dev 2)."""

from backend.knowledge.chunker import (
    Chunk,
    chunk_document,
    chunk_text,
    count_tokens,
)
from backend.knowledge.embedder import (
    DEFAULT_MODEL_NAME,
    EMBEDDING_DIMENSION,
    LocalEmbedder,
    get_embedder,
)
from backend.knowledge.ocr import (
    OCRResult,
    clean_ocr_text,
    extract_text_from_image,
    is_tesseract_available,
    ocr_image,
)
from backend.knowledge.pdf_parser import ParsedDocument, ParsedPage, parse_pdf

__all__ = [
    "parse_pdf",
    "ParsedDocument",
    "ParsedPage",
    "ocr_image",
    "OCRResult",
    "clean_ocr_text",
    "is_tesseract_available",
    "extract_text_from_image",
    "Chunk",
    "chunk_document",
    "chunk_text",
    "count_tokens",
    "LocalEmbedder",
    "get_embedder",
    "DEFAULT_MODEL_NAME",
    "EMBEDDING_DIMENSION",
]
