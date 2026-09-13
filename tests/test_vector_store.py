"""
tests/test_vector_store.py
===========================
Unit tests for backend/knowledge/vector_store.py (Day 1 — Task 1.5: Local Vector Store)

Tests verify in-memory and persistent Qdrant vector indexing, semantic search,
deterministic UUID deduplication, metadata filtering, and document deletion.
"""

from __future__ import annotations

import pytest

from backend.knowledge.chunker import Chunk
from backend.knowledge.embedder import get_embedder
from backend.knowledge.vector_store import (
    SearchResult,
    VectorStore,
)


@pytest.fixture(scope="module")
def shared_embedder():
    """Load embedder once for tests."""
    embedder = get_embedder()
    embedder.load()
    return embedder


@pytest.fixture
def memory_store(shared_embedder):
    """Provide a fresh in-memory Qdrant VectorStore for each test."""
    return VectorStore(
        collection_name="test_knowledge",
        storage_path=":memory:",
        embedder=shared_embedder,
    )


class TestVectorStoreBasics:
    def test_initial_collection_is_empty(self, memory_store: VectorStore):
        assert memory_store.count() == 0

    def test_add_empty_chunks_returns_zero(self, memory_store: VectorStore):
        assert memory_store.add_chunks([]) == 0
        assert memory_store.count() == 0


class TestVectorStoreIndexing:
    def test_add_chunks_indexes_points(self, memory_store: VectorStore):
        chunks = [
            Chunk(
                chunk_id="doc1_p1_c0",
                document_id="doc1",
                filename="inspection.pdf",
                page_number=1,
                content="Emergency relief valve operating pressure limit is 120 PSI.",
                token_count=10,
                chunk_index=0,
            ),
            Chunk(
                chunk_id="doc1_p2_c1",
                document_id="doc1",
                filename="inspection.pdf",
                page_number=2,
                content="Turbine bearing temperatures were measured within safe margins.",
                token_count=9,
                chunk_index=1,
            ),
        ]

        indexed_count = memory_store.add_chunks(chunks)
        assert indexed_count == 2
        assert memory_store.count() == 2

    def test_deterministic_id_deduplication(self, memory_store: VectorStore):
        """Re-indexing the exact same chunk should overwrite it, not create duplicate points."""
        chunk = Chunk(
            chunk_id="doc1_p1_c0",
            document_id="doc1",
            filename="inspection.pdf",
            page_number=1,
            content="Emergency relief valve operating pressure limit is 120 PSI.",
            token_count=10,
            chunk_index=0,
        )

        memory_store.add_chunks([chunk])
        assert memory_store.count() == 1

        # Re-add identical chunk
        memory_store.add_chunks([chunk])
        assert memory_store.count() == 1


class TestVectorStoreSearch:
    def test_semantic_search_ranks_relevant_chunk_first(self, memory_store: VectorStore):
        chunks = [
            Chunk(
                chunk_id="valve_c0",
                document_id="doc_safety",
                filename="safety_findings.pdf",
                page_number=3,
                content="Critical failure in high pressure relief valve #4 at 140 PSI.",
                token_count=12,
                chunk_index=0,
            ),
            Chunk(
                chunk_id="paint_c0",
                document_id="doc_general",
                filename="facility_notes.pdf",
                page_number=1,
                content="Repainting of outer perimeter fence is scheduled for next month.",
                token_count=11,
                chunk_index=0,
            ),
        ]
        memory_store.add_chunks(chunks)

        results = memory_store.search("What is the valve pressure threshold?", top_k=2)

        assert len(results) == 2
        top = results[0]
        assert isinstance(top, SearchResult)
        assert top.chunk.chunk_id == "valve_c0"
        assert top.chunk.page_number == 3
        assert top.score > 0.5
        assert top.score > results[1].score

    def test_search_result_to_dict(self, memory_store: VectorStore):
        chunk = Chunk(
            chunk_id="c_test",
            document_id="doc1",
            filename="doc.pdf",
            page_number=5,
            content="Corrosion detected on pipe joint.",
            token_count=6,
            chunk_index=0,
        )
        memory_store.add_chunks([chunk])

        results = memory_store.search("pipe corrosion", top_k=1)
        res_dict = results[0].to_dict()

        assert res_dict["chunk_id"] == "c_test"
        assert res_dict["filename"] == "doc.pdf"
        assert res_dict["page"] == 5
        assert res_dict["content"] == "Corrosion detected on pipe joint."
        assert "score" in res_dict


class TestVectorStoreFilteringAndDeletion:
    def test_filter_by_document_id(self, memory_store: VectorStore):
        chunks = [
            Chunk(
                chunk_id="docA_c0",
                document_id="doc_alpha",
                filename="alpha.pdf",
                page_number=1,
                content="Inspection safety protocol checklist.",
                token_count=5,
                chunk_index=0,
            ),
            Chunk(
                chunk_id="docB_c0",
                document_id="doc_beta",
                filename="beta.pdf",
                page_number=1,
                content="Inspection safety protocol checklist duplicate.",
                token_count=5,
                chunk_index=0,
            ),
        ]
        memory_store.add_chunks(chunks)

        # Search restricted to doc_alpha only
        results = memory_store.search("safety protocol", top_k=5, filter_doc_id="doc_alpha")

        assert len(results) == 1
        assert results[0].chunk.document_id == "doc_alpha"

    def test_delete_document(self, memory_store: VectorStore):
        chunks = [
            Chunk(
                chunk_id="c1",
                document_id="doc_to_delete",
                filename="del.pdf",
                page_number=1,
                content="Temporary record.",
                token_count=2,
                chunk_index=0,
            ),
            Chunk(
                chunk_id="c2",
                document_id="doc_to_keep",
                filename="keep.pdf",
                page_number=1,
                content="Permanent record.",
                token_count=2,
                chunk_index=0,
            ),
        ]
        memory_store.add_chunks(chunks)
        assert memory_store.count() == 2

        memory_store.delete_document("doc_to_delete")
        assert memory_store.count() == 1

        remaining = memory_store.search("record", top_k=5)
        assert len(remaining) == 1
        assert remaining[0].chunk.document_id == "doc_to_keep"

    def test_clear_collection(self, memory_store: VectorStore):
        chunks = [
            Chunk(
                chunk_id="c1",
                document_id="d1",
                filename="d1.pdf",
                page_number=1,
                content="Test point.",
                token_count=2,
                chunk_index=0,
            )
        ]
        memory_store.add_chunks(chunks)
        assert memory_store.count() == 1

        memory_store.clear()
        assert memory_store.count() == 0
