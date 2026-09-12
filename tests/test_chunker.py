"""
tests/test_chunker.py
======================
Unit tests for backend/knowledge/chunker.py (Day 1 — Task 1.3: Text Chunker)

Tests verify token-bounded sliding window chunking, metadata propagation,
overlap continuity, and integration with ParsedDocument.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.knowledge.chunker import (
    Chunk,
    chunk_document,
    chunk_text,
    count_tokens,
)
from backend.knowledge.pdf_parser import ParsedDocument, ParsedPage


# -- helpers -------------------------------------------------------------------

def _generate_long_text(words_count: int = 400) -> str:
    """Generate a multi-paragraph text block for testing chunk splits."""
    paragraphs = []
    current_word = 0
    while current_word < words_count:
        p_len = min(50, words_count - current_word)
        para = " ".join([f"word{current_word + i}" for i in range(p_len)]) + "."
        paragraphs.append(para)
        current_word += p_len
    return "\n\n".join(paragraphs)


# -- tests ---------------------------------------------------------------------

class TestTokenCounting:
    def test_empty_string_returns_zero(self):
        assert count_tokens("") == 0
        assert count_tokens("   ") == 0

    def test_short_sentence_count(self):
        tokens = count_tokens("Smart India Hackathon sovereign workbench.")
        assert tokens > 0
        assert tokens < 15

    def test_token_count_scales_with_length(self):
        short_count = count_tokens("Safety inspection report.")
        long_count = count_tokens("Safety inspection report. " * 20)
        assert long_count > short_count * 10


class TestChunkDataclass:
    def test_to_dict_keys(self):
        c = Chunk(
            chunk_id="doc1_p1_c0",
            document_id="doc1",
            filename="report.pdf",
            page_number=1,
            content="Safety valve inspected.",
            token_count=5,
            chunk_index=0,
            metadata={"used_ocr": False},
        )
        d = c.to_dict()
        assert d["chunk_id"] == "doc1_p1_c0"
        assert d["document_id"] == "doc1"
        assert d["filename"] == "report.pdf"
        assert d["page"] == 1
        assert d["content"] == "Safety valve inspected."
        assert d["token_count"] == 5
        assert d["chunk_index"] == 0
        assert d["metadata"] == {"used_ocr": False}


class TestChunkText:
    def test_empty_text_returns_empty_list(self):
        assert chunk_text("") == []
        assert chunk_text("   \n\t  ") == []

    def test_single_small_chunk(self):
        text = "This is a brief inspection note that fits in a single chunk."
        chunks = chunk_text(text, filename="note.txt", chunk_size=100, chunk_overlap=10)
        assert len(chunks) == 1
        assert chunks[0].content == text
        assert chunks[0].page_number == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].chunk_id == "note_p1_c0"

    def test_invalid_overlap_raises_value_error(self):
        with pytest.raises(ValueError, match="chunk_overlap"):
            chunk_text("Some text", chunk_size=50, chunk_overlap=50)

        with pytest.raises(ValueError, match="chunk_overlap"):
            chunk_text("Some text", chunk_size=50, chunk_overlap=100)

    def test_multichunk_splits_long_text(self):
        long_text = _generate_long_text(words_count=500)
        chunks = chunk_text(
            long_text,
            filename="long_doc.pdf",
            chunk_size=100,
            chunk_overlap=20,
        )
        assert len(chunks) > 1

        # Check sequential indexing
        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_index == idx
            assert chunk.chunk_id == f"long_doc_p1_c{idx}"
            assert chunk.token_count > 0

    def test_overlap_contains_shared_context(self):
        """Ensure consecutive chunks share overlapping tokens."""
        text = "Sentence one is here. Sentence two follows it. Sentence three is next. Sentence four concludes."
        chunks = chunk_text(text, chunk_size=12, chunk_overlap=5)
        if len(chunks) >= 2:
            # First chunk end or second chunk start should share words
            words_c0 = set(chunks[0].content.split())
            words_c1 = set(chunks[1].content.split())
            shared = words_c0.intersection(words_c1)
            assert len(shared) > 0

    def test_custom_metadata_propagated(self):
        chunks = chunk_text(
            "Sample text for metadata check.",
            extra_metadata={"author": "Dev 2", "section": "Summary"},
        )
        assert len(chunks) == 1
        assert chunks[0].metadata["author"] == "Dev 2"
        assert chunks[0].metadata["section"] == "Summary"


class TestChunkDocument:
    def test_chunks_multiple_pages_retaining_page_numbers(self):
        pages = [
            ParsedPage(
                page_number=1,
                text="Page 1: Overview and introduction to sovereign AI architecture.",
                used_ocr=False,
                image_count=0,
                width_pt=595.0,
                height_pt=842.0,
            ),
            ParsedPage(
                page_number=2,
                text="Page 2: Hardware specifications and GPU memory constraints.",
                used_ocr=True,
                image_count=2,
                width_pt=595.0,
                height_pt=842.0,
            ),
        ]
        doc = ParsedDocument(
            source_path=Path("docs/architecture_spec.pdf"),
            page_count=2,
            pages=pages,
        )

        chunks = chunk_document(doc, chunk_size=100, chunk_overlap=10)
        assert len(chunks) == 2

        # Page 1 chunk check
        assert chunks[0].page_number == 1
        assert chunks[0].filename == "architecture_spec.pdf"
        assert chunks[0].chunk_index == 0
        assert chunks[0].metadata["used_ocr"] is False
        assert "Overview and introduction" in chunks[0].content

        # Page 2 chunk check
        assert chunks[1].page_number == 2
        assert chunks[1].chunk_index == 1
        assert chunks[1].metadata["used_ocr"] is True
        assert chunks[1].metadata["image_count"] == 2
        assert "Hardware specifications" in chunks[1].content

    def test_skips_empty_pages_cleanly(self):
        pages = [
            ParsedPage(
                page_number=1,
                text="Page 1 has valid content.",
                used_ocr=False,
                image_count=0,
                width_pt=595.0,
                height_pt=842.0,
            ),
            ParsedPage(
                page_number=2,
                text="     \n  ",  # empty page
                used_ocr=False,
                image_count=1,
                width_pt=595.0,
                height_pt=842.0,
            ),
            ParsedPage(
                page_number=3,
                text="Page 3 also has valid content.",
                used_ocr=False,
                image_count=0,
                width_pt=595.0,
                height_pt=842.0,
            ),
        ]
        doc = ParsedDocument(
            source_path=Path("docs/sample.pdf"),
            page_count=3,
            pages=pages,
        )

        chunks = chunk_document(doc)
        assert len(chunks) == 2
        assert chunks[0].page_number == 1
        assert chunks[1].page_number == 3
        assert chunks[1].chunk_index == 1
