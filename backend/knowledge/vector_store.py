"""
backend/knowledge/vector_store.py
==================================
Day 1 — Task 1.5: Local Vector Store (Qdrant Embedded)

Provides persistent, local-mode vector indexing and similarity search using Qdrant.

Key Features:
  - Zero External Servers: Runs embedded via Qdrant local disk mode or :memory:.
  - Deterministic Point IDs: Generates stable UUID5s from chunk_id to prevent duplicates
    upon re-ingestion.
  - Rich Payloads: Stores full Chunk metadata (filename, page_number, token_count, etc.).
  - Filtered Search: Supports filtering by document_id alongside cosine similarity search.
  - Sovereign Compliance: 100% offline, persistent across application restarts.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

from qdrant_client import QdrantClient, models

from backend.knowledge.chunker import Chunk
from backend.knowledge.embedder import (
    DEFAULT_MODEL_NAME,
    EMBEDDING_DIMENSION,
    LocalEmbedder,
    get_embedder,
)

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME: str = "sovereign_knowledge"
DEFAULT_STORAGE_PATH: Path = Path("data/knowledge/qdrant")


@dataclass
class SearchResult:
    """A retrieved knowledge chunk paired with its similarity score."""

    chunk: Chunk
    score: float

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for agent state injection or API response."""
        data = self.chunk.to_dict()
        data["score"] = round(self.score, 4)
        return data


class VectorStore:
    """
    Qdrant-powered local vector database for knowledge retrieval.
    """

    def __init__(
        self,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        storage_path: Path | str | None = DEFAULT_STORAGE_PATH,
        embedder: LocalEmbedder | None = None,
        dimension: int = EMBEDDING_DIMENSION,
    ) -> None:
        self.collection_name = collection_name
        self.dimension = dimension
        self.embedder = embedder or get_embedder()

        # Initialize Qdrant client in local disk mode or memory mode
        if storage_path == ":memory:":
            self.storage_path = ":memory:"
            self.client = QdrantClient(location=":memory:")
            logger.info("Initialized Qdrant in transient :memory: mode.")
        else:
            path = Path(storage_path) if storage_path else DEFAULT_STORAGE_PATH
            path.mkdir(parents=True, exist_ok=True)
            self.storage_path = path
            self.client = QdrantClient(path=str(self.storage_path))
            logger.info("Initialized Qdrant in persistent disk mode at '%s'.", self.storage_path)

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create Qdrant collection with cosine distance if it does not already exist."""
        exists = self.client.collection_exists(collection_name=self.collection_name)
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.dimension,
                    distance=models.Distance.COSINE,
                ),
            )
            logger.info("Created Qdrant collection '%s' (dim=%d, distance=COSINE).", self.collection_name, self.dimension)

    def count(self) -> int:
        """Return total number of points stored in this collection."""
        info = self.client.get_collection(collection_name=self.collection_name)
        return info.points_count or 0

    def add_chunks(
        self,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]] | None = None,
        batch_size: int = 64,
    ) -> int:
        """
        Index a sequence of Chunks into the vector store.

        Parameters
        ----------
        chunks:
            List of Chunk dataclass objects to store.
        vectors:
            Optional precomputed vectors. If None, generated via self.embedder.
        batch_size:
            Batch size for vector upserts into Qdrant.

        Returns
        -------
        int:
            Number of points successfully indexed.
        """
        if not chunks:
            return 0

        # Compute embeddings if not provided
        if vectors is None:
            logger.debug("Generating vector embeddings for %d chunks...", len(chunks))
            embeddings = self.embedder.embed_chunks(chunks)
        else:
            embeddings = list(vectors)

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch between chunks count ({len(chunks)}) and embeddings count ({len(embeddings)})."
            )

        points: list[models.PointStruct] = []
        for chunk, vector in zip(chunks, embeddings):
            # Deterministic UUID5 based on chunk_id ensures idempotency (no duplicates on re-run)
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            payload = {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "filename": chunk.filename,
                "page_number": chunk.page_number,
                "content": chunk.content,
                "token_count": chunk.token_count,
                "chunk_index": chunk.chunk_index,
                "metadata": chunk.metadata,
            }
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=list(vector),
                    payload=payload,
                )
            )

        # Batch upsert into Qdrant
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )

        logger.info("Indexed %d chunks into collection '%s'.", len(chunks), self.collection_name)
        return len(chunks)

    def search_vector(
        self,
        query_vector: Sequence[float],
        top_k: int = 5,
        score_threshold: float | None = None,
        filter_doc_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Search for closest chunks given a precomputed query vector.

        Parameters
        ----------
        query_vector:
            384-dimensional query vector.
        top_k:
            Maximum number of nearest neighbors to return.
        score_threshold:
            Optional minimum cosine similarity cutoff [0.0 - 1.0].
        filter_doc_id:
            Optional document_id to restrict search scope.

        Returns
        -------
        list[SearchResult]:
            Ranked results with similarity scores.
        """
        query_filter: models.Filter | None = None
        if filter_doc_id:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=filter_doc_id),
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=list(query_vector),
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,
        )

        results: list[SearchResult] = []
        for scored_point in response.points:
            p = scored_point.payload or {}
            chunk = Chunk(
                chunk_id=p.get("chunk_id", str(scored_point.id)),
                document_id=p.get("document_id", ""),
                filename=p.get("filename", ""),
                page_number=p.get("page_number", 1),
                content=p.get("content", ""),
                token_count=p.get("token_count", 0),
                chunk_index=p.get("chunk_index", 0),
                metadata=p.get("metadata", {}),
            )
            results.append(SearchResult(chunk=chunk, score=float(scored_point.score)))

        return results

    def search(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float | None = None,
        filter_doc_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Semantic search for relevant chunks given a natural language query string.

        Parameters
        ----------
        query:
            Natural language question or search phrase.
        top_k:
            Maximum chunks to retrieve (default: 5).
        score_threshold:
            Optional minimum similarity score cutoff.
        filter_doc_id:
            Optional document_id filter.

        Returns
        -------
        list[SearchResult]:
            Ranked chunks with similarity scores.
        """
        query_vector = self.embedder.embed_query(query)
        return self.search_vector(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
            filter_doc_id=filter_doc_id,
        )

    def delete_document(self, document_id: str) -> None:
        """Delete all chunks belonging to a specific document_id."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )
        logger.info("Deleted document '%s' from collection '%s'.", document_id, self.collection_name)

    def clear(self) -> None:
        """Clear all indexed points by recreating the collection."""
        self.client.delete_collection(collection_name=self.collection_name)
        self._ensure_collection()
        logger.info("Cleared all points from collection '%s'.", self.collection_name)

    def close(self) -> None:
        """Release local Qdrant resources such as file locks."""
        close = getattr(self.client, "close", None)
        if callable(close):
            close()


# -- global singleton accessor -------------------------------------------------
_VECTOR_STORE_INSTANCE: VectorStore | None = None


def get_vector_store(
    storage_path: Path | str | None = DEFAULT_STORAGE_PATH,
    collection_name: str = DEFAULT_COLLECTION_NAME,
) -> VectorStore:
    """
    Get or create the global persistent VectorStore singleton instance.
    """
    global _VECTOR_STORE_INSTANCE
    if _VECTOR_STORE_INSTANCE is None:
        _VECTOR_STORE_INSTANCE = VectorStore(
            collection_name=collection_name,
            storage_path=storage_path,
        )
    return _VECTOR_STORE_INSTANCE


def reset_vector_store() -> None:
    """Close and clear the global VectorStore singleton."""
    global _VECTOR_STORE_INSTANCE
    if _VECTOR_STORE_INSTANCE is not None:
        _VECTOR_STORE_INSTANCE.close()
        _VECTOR_STORE_INSTANCE = None
