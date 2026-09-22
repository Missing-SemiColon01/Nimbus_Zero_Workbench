"""
backend/knowledge/retriever.py
===============================
Day 1 — Task 1.6: End-to-End Ingestion Pipeline & Retriever

Unifies all Day 1 pipeline components (Parser -> OCR -> Chunker -> Embedder -> Vector Store)
into a cohesive interface for document ingestion and semantic context retrieval.

Key Capabilities:
  - ingest_document: End-to-end PDF ingestion (parse -> OCR fallback -> chunk -> embed -> Qdrant).
  - ingest_text: Direct raw text ingestion for snippet notes and scratchpads.
  - search: Returns structured dicts formatted exactly for AgentState.retrieved_context
    with source citations (filename, page, chunk_id, content, score).
  - Standalone CLI: Runnable via `python -m backend.knowledge.retriever`.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from backend.knowledge.chunker import Chunk, chunk_document, chunk_text
from backend.knowledge.embedder import LocalEmbedder, get_embedder
from backend.knowledge.pdf_parser import ParsedDocument, parse_pdf
from backend.knowledge.vector_store import (
    SearchResult,
    VectorStore,
    get_vector_store,
    reset_vector_store,
)

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """Summary metrics of a document ingestion run."""

    document_id: str
    filename: str
    page_count: int
    chunk_count: int
    ocr_pages: int
    duration_seconds: float
    status: str = "success"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "page_count": self.page_count,
            "chunk_count": self.chunk_count,
            "ocr_pages": self.ocr_pages,
            "duration_seconds": round(self.duration_seconds, 3),
            "status": self.status,
            "error": self.error,
        }


class KnowledgeRetriever:
    """
    Facade orchestrating the complete sovereign RAG knowledge pipeline.
    """

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embedder: LocalEmbedder | None = None,
        default_top_k: int = 10,
        default_ef: int = 128,
    ) -> None:
        self.embedder = embedder or get_embedder()
        self.vector_store = vector_store or get_vector_store()
        self.default_top_k = default_top_k
        self.default_ef = default_ef

    def ingest_document(
        self,
        source: str | Path,
        document_id: str | None = None,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> IngestResult:
        """
        Run end-to-end ingestion on a PDF file:
          1. Parse PDF pages via PyMuPDF.
          2. Run OCR fallback on image-heavy / scanned pages.
          3. Chunk text into token-bounded sliding window pieces.
          4. Embed chunks with local transformer embeddings.
          5. Store dense vectors and payloads in local Qdrant collection.

        Parameters
        ----------
        source:
            Path to the PDF file.
        document_id:
            Custom document identifier (defaults to file stem).
        chunk_size:
            Target token size per chunk.
        chunk_overlap:
            Token overlap between adjacent chunks.

        Returns
        -------
        IngestResult:
            Detailed metrics on chunks stored, pages processed, and timing.
        """
        start_time = time.time()
        path = Path(source)
        doc_id = document_id or path.stem

        if not path.exists():
            raise FileNotFoundError(f"Cannot ingest non-existent document: {path}")

        logger.info("Ingesting document '%s' (ID: %s)...", path.name, doc_id)

        try:
            # 1. Parse PDF + OCR fallback
            parsed_doc: ParsedDocument = parse_pdf(path)

            # 2. Split into token-bounded chunks
            chunks: list[Chunk] = chunk_document(
                doc=parsed_doc,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                document_id=doc_id,
            )

            # 3. Embed & Store in Qdrant
            if chunks:
                self.vector_store.add_chunks(chunks)

            duration = time.time() - start_time
            logger.info(
                "Successfully ingested '%s': %d pages, %d chunks in %.2fs",
                path.name,
                parsed_doc.page_count,
                len(chunks),
                duration,
            )

            return IngestResult(
                document_id=doc_id,
                filename=path.name,
                page_count=parsed_doc.page_count,
                chunk_count=len(chunks),
                ocr_pages=parsed_doc.ocr_page_count,
                duration_seconds=duration,
                status="success",
            )

        except Exception as exc:
            duration = time.time() - start_time
            logger.error("Failed to ingest document '%s': %s", path.name, exc, exc_info=True)
            return IngestResult(
                document_id=doc_id,
                filename=path.name,
                page_count=0,
                chunk_count=0,
                ocr_pages=0,
                duration_seconds=duration,
                status="failed",
                error=str(exc),
            )

    def ingest_text(
        self,
        text: str,
        document_id: str,
        filename: str = "snippet.txt",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        metadata: dict[str, Any] | None = None,
    ) -> IngestResult:
        """
        Ingest raw text directly into the knowledge base (useful for notes or web clips).
        """
        start_time = time.time()
        chunks = chunk_text(
            text=text,
            filename=filename,
            page_number=1,
            document_id=document_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            extra_metadata=metadata,
        )

        if chunks:
            self.vector_store.add_chunks(chunks)

        duration = time.time() - start_time
        return IngestResult(
            document_id=document_id,
            filename=filename,
            page_count=1,
            chunk_count=len(chunks),
            ocr_pages=0,
            duration_seconds=duration,
            status="success",
        )

    def search(
        self,
        query: str,
        top_k: int | None = None,
        score_threshold: float | None = None,
        filter_doc_id: str | None = None,
        ef: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Semantic search returning structured context dicts ready for AgentState injection.

        Returns
        -------
        list[dict[str, Any]]:
            List of dicts formatted with:
            {
                "content": str,
                "source": str,
                "page": int,
                "chunk_id": str,
                "document_id": str,
                "score": float,
                "metadata": dict
            }
        """
        search_results: list[SearchResult] = self.vector_store.search(
            query=query,
            top_k=top_k or self.default_top_k,
            score_threshold=score_threshold,
            filter_doc_id=filter_doc_id,
            ef=ef or self.default_ef,
        )

        context_list: list[dict[str, Any]] = []
        for sr in search_results:
            c = sr.chunk
            context_list.append(
                {
                    "content": c.content,
                    "source": c.filename,
                    "page": c.page_number,
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "score": round(sr.score, 4),
                    "metadata": c.metadata,
                }
            )

        return context_list

    def search_chunks(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float | None = None,
        filter_doc_id: str | None = None,
    ) -> list[SearchResult]:
        """Return typed SearchResult objects instead of dictionaries."""
        return self.vector_store.search(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            filter_doc_id=filter_doc_id,
        )

    def delete_document(self, document_id: str) -> None:
        """Purge all chunks associated with a specific document from the store."""
        self.vector_store.delete_document(document_id)

    def count(self) -> int:
        """Return total number of indexed knowledge chunks."""
        return self.vector_store.count()


# -- global singleton accessor -------------------------------------------------
_RETRIEVER_INSTANCE: KnowledgeRetriever | None = None


def get_retriever() -> KnowledgeRetriever:
    """Get or create the global KnowledgeRetriever singleton."""
    global _RETRIEVER_INSTANCE
    if _RETRIEVER_INSTANCE is None:
        _RETRIEVER_INSTANCE = KnowledgeRetriever()
    return _RETRIEVER_INSTANCE


def reset_retriever() -> None:
    """Close and clear global retriever resources."""
    global _RETRIEVER_INSTANCE
    _RETRIEVER_INSTANCE = None
    reset_vector_store()


# -- CLI standalone runner -----------------------------------------------------
if __name__ == "__main__":
    import sys

    print("=== Sovereign AI Knowledge Retriever (Day 1 Pipeline Demo) ===")
    retriever = get_retriever()

    if len(sys.argv) > 1:
        doc_path = sys.argv[1]
        print(f"Ingesting: {doc_path}")
        res = retriever.ingest_document(doc_path, chunk_size=1000, chunk_overlap=200)
        print(f"Ingest Result: {res.to_dict()}")

    test_query = "pressure valve safety findings"
    print(f"\nSearching for: '{test_query}'")
    hits = retriever.search(test_query, top_k=10, ef=128)
    if not hits:
        print("No chunks currently indexed. Ingest a document first.")
    for i, hit in enumerate(hits, 1):
        print(f"\n[{i}] Source: {hit['source']} (Page {hit['page']}) | Score: {hit['score']}")
        print(f"    Content: {hit['content'][:150]}...")
