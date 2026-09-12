"""
backend/knowledge/chunker.py
=============================
Day 1 — Task 1.3: Text Chunker

Splits parsed documents and page text into semantic, token-bounded chunks
with sliding window overlap and rich source metadata.

Key Capabilities:
  - Token-accurate sizing via tiktoken (cl100k_base) with character fallback.
  - Recursive boundary splitting: paragraphs (\\n\\n) -> sentences (. ?) -> words.
  - Structured Metadata: Every chunk preserves document_id, filename, page_number,
    token_count, and sequential index for citation in agent responses.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from backend.knowledge.pdf_parser import ParsedDocument, ParsedPage

logger = logging.getLogger(__name__)

# -- tokenizer setup -----------------------------------------------------------
_ENCODER: Any = None


def _get_encoder() -> Any:
    """Lazily load tiktoken encoder with fallback."""
    global _ENCODER
    if _ENCODER is None:
        try:
            import tiktoken

            _ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception as exc:
            logger.debug("tiktoken unavailable (%s), falling back to character approximation.", exc)
            _ENCODER = False
    return _ENCODER


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a string.

    Uses tiktoken cl100k_base encoding. If tiktoken is not functional,
    falls back to standard heuristic (~4 characters per token).
    """
    if not text or not text.strip():
        return 0

    encoder = _get_encoder()
    if encoder:
        try:
            return len(encoder.encode(text, disallowed_special=()))
        except Exception:
            pass

    # Heuristic fallback: ~4 chars per token in English
    return max(1, len(text) // 4)


# -- data contract -------------------------------------------------------------
@dataclass
class Chunk:
    """
    Individual text chunk stored in the vector database and passed to agents.
    """

    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    content: str
    token_count: int
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert chunk to dictionary for LangGraph context or API response."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "filename": self.filename,
            "page": self.page_number,
            "content": self.content,
            "token_count": self.token_count,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
        }


# -- splitting engine ----------------------------------------------------------
_SEPARATORS: list[str] = ["\n\n", "\n", ". ", "? ", "! ", " "]


def _split_text_recursively(
    text: str,
    max_tokens: int,
    separators: list[str] | None = None,
) -> list[str]:
    """
    Split text recursively by paragraphs, sentences, or words until each segment
    fits within max_tokens.
    """
    stripped = text.strip()
    if not stripped:
        return []

    if count_tokens(stripped) <= max_tokens:
        return [stripped]

    if separators is None:
        separators = list(_SEPARATORS)

    # Find the highest priority separator present in the text
    chosen_sep: str | None = None
    remaining_seps: list[str] = []
    for idx, sep in enumerate(separators):
        if sep in stripped:
            chosen_sep = sep
            remaining_seps = separators[idx + 1 :]
            break

    if chosen_sep is None:
        # Monolithic block without available separators: slice by character limit
        char_limit = max(10, max_tokens * 3)
        return [stripped[i : i + char_limit] for i in range(0, len(stripped), char_limit)]

    splits = stripped.split(chosen_sep)
    segments: list[str] = []

    for idx, part in enumerate(splits):
        p_strip = part.strip()
        if not p_strip:
            continue

        # Check if this part alone fits or needs deeper splitting with remaining separators
        if count_tokens(p_strip) <= max_tokens:
            segments.append(p_strip)
        else:
            sub_segments = _split_text_recursively(p_strip, max_tokens, remaining_seps)
            segments.extend(sub_segments)

    return segments


def chunk_text(
    text: str,
    filename: str = "document",
    page_number: int = 1,
    document_id: str | None = None,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    start_index: int = 0,
    extra_metadata: dict[str, Any] | None = None,
) -> list[Chunk]:
    """
    Split raw text into sliding-window overlapping Chunks.

    Parameters
    ----------
    text:
        Input text to chunk.
    filename:
        Source file name for citation.
    page_number:
        Page number where text originated (1-indexed).
    document_id:
        Unique identifier for the parent document. If None, derived from filename.
    chunk_size:
        Target maximum tokens per chunk (default: 500).
    chunk_overlap:
        Token overlap between consecutive chunks (default: 50).
    start_index:
        Starting index for sequential chunk numbering.
    extra_metadata:
        Additional custom key-values attached to each chunk.

    Returns
    -------
    list[Chunk]:
        Sequential list of token-bounded Chunk objects.
    """
    cleaned = text.strip()
    if not cleaned:
        return []

    if chunk_overlap >= chunk_size:
        raise ValueError(f"chunk_overlap ({chunk_overlap}) must be smaller than chunk_size ({chunk_size})")

    doc_id = document_id or re.sub(r"[^\w\-]", "_", Path(filename).stem)
    base_meta = extra_metadata.copy() if extra_metadata else {}

    # Break into atomic segments that fit within chunk_size
    atomic_segments = _split_text_recursively(cleaned, chunk_size)
    if not atomic_segments:
        return []

    chunks: list[Chunk] = []
    current_tokens: list[str] = []
    accumulated_count = 0
    current_chunk_idx = start_index

    i = 0
    while i < len(atomic_segments):
        seg = atomic_segments[i]
        seg_tokens = count_tokens(seg)

        # If adding this segment exceeds chunk_size and we already have content
        if accumulated_count + seg_tokens > chunk_size and current_tokens:
            chunk_content = "".join(current_tokens).strip()
            cid = f"{doc_id}_p{page_number}_c{current_chunk_idx}"
            chunks.append(
                Chunk(
                    chunk_id=cid,
                    document_id=doc_id,
                    filename=filename,
                    page_number=page_number,
                    content=chunk_content,
                    token_count=count_tokens(chunk_content),
                    chunk_index=current_chunk_idx,
                    metadata=base_meta,
                )
            )
            current_chunk_idx += 1

            # Rewind backwards to build the overlap buffer for the next chunk
            overlap_accum = 0
            overlap_segments: list[str] = []
            for prev_seg in reversed(current_tokens):
                p_count = count_tokens(prev_seg)
                if overlap_accum + p_count <= chunk_overlap:
                    overlap_segments.insert(0, prev_seg)
                    overlap_accum += p_count
                else:
                    break

            current_tokens = overlap_segments
            accumulated_count = overlap_accum

        current_tokens.append(seg)
        accumulated_count += seg_tokens
        i += 1

    # Emit the trailing chunk
    if current_tokens:
        trailing_content = "".join(current_tokens).strip()
        if trailing_content:
            cid = f"{doc_id}_p{page_number}_c{current_chunk_idx}"
            chunks.append(
                Chunk(
                    chunk_id=cid,
                    document_id=doc_id,
                    filename=filename,
                    page_number=page_number,
                    content=trailing_content,
                    token_count=count_tokens(trailing_content),
                    chunk_index=current_chunk_idx,
                    metadata=base_meta,
                )
            )

    return chunks


def chunk_document(
    doc: ParsedDocument,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    document_id: str | None = None,
) -> list[Chunk]:
    """
    Split a ParsedDocument into Chunks, preserving page numbers and document metadata.

    Parameters
    ----------
    doc:
        ParsedDocument instance produced by pdf_parser.parse_pdf().
    chunk_size:
        Target maximum tokens per chunk (default: 500).
    chunk_overlap:
        Token overlap between consecutive chunks (default: 50).
    document_id:
        Optional custom document ID. Defaults to source filename stem.

    Returns
    -------
    list[Chunk]:
        All chunks across all pages with full metadata.
    """
    filename = doc.source_path.name
    doc_id = document_id or re.sub(r"[^\w\-]", "_", doc.source_path.stem)

    all_chunks: list[Chunk] = []
    global_index = 0

    for page in doc.pages:
        page_text = page.text.strip()
        if not page_text:
            continue

        page_meta = {
            "used_ocr": page.used_ocr,
            "image_count": page.image_count,
            "total_doc_pages": doc.page_count,
        }

        page_chunks = chunk_text(
            text=page_text,
            filename=filename,
            page_number=page.page_number,
            document_id=doc_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            start_index=global_index,
            extra_metadata=page_meta,
        )

        all_chunks.extend(page_chunks)
        global_index += len(page_chunks)

    logger.info(
        "Chunked document '%s' (%d pages) into %d chunks (avg %d tokens/chunk)",
        filename,
        doc.page_count,
        len(all_chunks),
        round(sum(c.token_count for c in all_chunks) / len(all_chunks)) if all_chunks else 0,
    )
    return all_chunks
