"""
backend/schemas/knowledge.py
=============================
Pydantic data schemas for knowledge ingestion and retrieval API endpoints.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Payload for triggering document ingestion via filepath."""

    file_path: str = Field(..., description="Absolute or relative path to the PDF document.")
    document_id: str | None = Field(None, description="Optional custom document identifier.")
    chunk_size: int = Field(500, ge=50, le=4000, description="Target token size per chunk.")
    chunk_overlap: int = Field(50, ge=0, le=1000, description="Token overlap between adjacent chunks.")


class IngestResponse(BaseModel):
    """Result metrics returned after document ingestion."""

    document_id: str
    filename: str
    document_path: str | None = Field(None, description="Saved local PDF path usable as a task document reference.")
    page_count: int
    chunk_count: int
    ocr_pages: int
    duration_seconds: float
    status: str
    error: str | None = None


class KnowledgeSearchRequest(BaseModel):
    """Payload for semantic search against the knowledge base."""

    query: str = Field(..., min_length=1, description="Natural language search question.")
    top_k: int = Field(5, ge=1, le=50, description="Maximum number of chunks to retrieve.")
    document_id: str | None = Field(None, description="Optional document ID filter.")
    score_threshold: float | None = Field(None, ge=0.0, le=1.0, description="Minimum similarity cutoff.")


class KnowledgeSearchResponse(BaseModel):
    """Ranked context results returned by semantic search."""

    query: str
    total_results: int
    results: list[dict[str, Any]]


class ToolInfo(BaseModel):
    """Description and schema of a registered sovereign tool."""

    name: str
    description: str
    parameters: dict[str, Any]
