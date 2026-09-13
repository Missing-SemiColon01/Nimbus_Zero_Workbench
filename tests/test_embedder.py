"""
tests/test_embedder.py
=======================
Unit tests for backend/knowledge/embedder.py (Day 1 — Task 1.4: Local Embedder)

Tests verify local vector embedding generation, 384-dimensional output,
L2-normalization, semantic similarity accuracy, and Chunk dataclass integration.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from backend.knowledge.chunker import Chunk
from backend.knowledge.embedder import (
    EMBEDDING_DIMENSION,
    LocalEmbedder,
    get_embedder,
)


@pytest.fixture(scope="module")
def shared_embedder() -> LocalEmbedder:
    """Fixture providing a shared LocalEmbedder loaded once for this test module."""
    embedder = get_embedder()
    embedder.load()
    return embedder


class TestEmbedderBasics:
    def test_dimension_is_384(self, shared_embedder: LocalEmbedder):
        assert shared_embedder.dimension == 384
        assert shared_embedder.dimension == EMBEDDING_DIMENSION

    def test_lazy_loading(self):
        new_embedder = LocalEmbedder()
        assert new_embedder.is_loaded is False
        new_embedder.load()
        assert new_embedder.is_loaded is True

    def test_singleton_accessor_returns_same_instance(self):
        e1 = get_embedder()
        e2 = get_embedder()
        assert e1 is e2


class TestEmbeddingGeneration:
    def test_embed_query_produces_normalized_vector(self, shared_embedder: LocalEmbedder):
        query = "Sovereign AI workbench inspection procedure"
        vec = shared_embedder.embed_query(query)

        assert isinstance(vec, list)
        assert len(vec) == 384

        # Verify unit length (L2 norm should be ~1.0)
        norm = math.sqrt(sum(x * x for x in vec))
        assert pytest.approx(norm, rel=1e-3) == 1.0

    def test_embed_texts_batching(self, shared_embedder: LocalEmbedder):
        texts = [
            "Safety inspection protocol",
            "Emergency valve pressure limit",
            "Sovereign deployment on edge hardware",
            "Optical character recognition pipeline",
        ]
        embeddings = shared_embedder.embed_texts(texts, batch_size=2)

        assert len(embeddings) == 4
        for emb in embeddings:
            assert len(emb) == 384
            norm = math.sqrt(sum(x * x for x in emb))
            assert pytest.approx(norm, rel=1e-3) == 1.0

    def test_empty_list_returns_empty(self, shared_embedder: LocalEmbedder):
        assert shared_embedder.embed_texts([]) == []

    def test_empty_string_does_not_crash(self, shared_embedder: LocalEmbedder):
        embeddings = shared_embedder.embed_texts(["", "   ", "Valid text"])
        assert len(embeddings) == 3
        assert len(embeddings[0]) == 384


class TestSemanticSimilarity:
    def test_semantic_ranking(self, shared_embedder: LocalEmbedder):
        """Relevant documents must have higher cosine similarity than unrelated topics."""
        query_vec = shared_embedder.embed_query("safety valve pressure rating")

        relevant_vec = shared_embedder.embed_query("Emergency pressure relief valve threshold is 150 PSI")
        irrelevant_vec = shared_embedder.embed_query("The Renaissance era was known for Italian oil paintings")

        sim_relevant = shared_embedder.compute_similarity(query_vec, relevant_vec)
        sim_irrelevant = shared_embedder.compute_similarity(query_vec, irrelevant_vec)

        assert sim_relevant > sim_irrelevant
        assert sim_relevant > 0.5
        assert sim_irrelevant < 0.3


class TestChunkIntegration:
    def test_embed_chunks(self, shared_embedder: LocalEmbedder):
        chunks = [
            Chunk(
                chunk_id="doc1_p1_c0",
                document_id="doc1",
                filename="spec.pdf",
                page_number=1,
                content="Hardware requirements for sovereign cluster.",
                token_count=7,
                chunk_index=0,
            ),
            Chunk(
                chunk_id="doc1_p1_c1",
                document_id="doc1",
                filename="spec.pdf",
                page_number=1,
                content="NVIDIA GPU VRAM allocation guidelines.",
                token_count=6,
                chunk_index=1,
            ),
        ]

        embeddings = shared_embedder.embed_chunks(chunks)
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 384
        assert len(embeddings[1]) == 384
