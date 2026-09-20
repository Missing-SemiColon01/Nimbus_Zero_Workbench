"""
backend/tools/rag_tool.py
==========================
Day 2 — Task 2.1: RAG Search Tool

Exposes the sovereign RAG retrieval pipeline as an autonomous Tool conforming
to the Tool interface in backend.tools.contracts.

Capabilities:
  - Tool Name: "rag.search"
  - Arguments:
      - "query" (str, required): Natural language search query.
      - "top_k" (int, optional, default=5): Number of chunks to retrieve.
      - "document_id" (str, optional): Restrict search to a specific document.
      - "score_threshold" (float, optional): Minimum cosine similarity cutoff.
  - Output: List of chunk dicts { content, source, page, chunk_id, document_id, score }.
  - State Sync: Automatically appends retrieved chunks to AgentState.retrieved_context
    when provided in context.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from backend.knowledge.retriever import KnowledgeRetriever, get_retriever
from backend.tools.contracts import Tool, ToolResult

logger = logging.getLogger(__name__)


class RAGSearchTool(Tool):
    """
    Autonomous tool for semantic search across ingested sovereign documents.
    """

    name = "rag.search"
    description = (
        "Search the sovereign knowledge base (inspection reports, technical specs, manuals) "
        "using semantic vector search. Returns relevant text chunks with exact page numbers "
        "and source filenames for audit citations."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search question or topic.",
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of relevant chunks to retrieve (default: 5).",
                "default": 5,
            },
            "document_id": {
                "type": "string",
                "description": "Optional document ID to restrict search scope to a single document.",
            },
            "score_threshold": {
                "type": "number",
                "description": "Optional minimum similarity score cutoff (0.0 to 1.0).",
            },
        },
        "required": ["query"],
    }

    def __init__(self, retriever: KnowledgeRetriever | None = None) -> None:
        self.retriever = retriever or get_retriever()

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        """
        Execute semantic search and optionally populate agent state context.

        Parameters
        ----------
        arguments:
            Dict containing 'query', optional 'top_k', 'document_id', 'score_threshold'.
        context:
            Execution context, optionally containing 'state' (AgentState) or 'retrieved_context'.

        Returns
        -------
        ToolResult:
            ToolResult containing list of retrieved chunks or error details.
        """
        query = arguments.get("query", "").strip() if isinstance(arguments.get("query"), str) else ""
        if not query:
            return ToolResult(
                success=False,
                output=[],
                error="Argument 'query' is required and must be a non-empty string.",
            )

        top_k = int(arguments.get("top_k", 5))
        document_id = arguments.get("document_id")
        score_threshold = arguments.get("score_threshold")
        if score_threshold is not None:
            score_threshold = float(score_threshold)

        try:
            hits = await asyncio.to_thread(
                self.retriever.search,
                query=query,
                top_k=top_k,
                score_threshold=score_threshold,
                filter_doc_id=document_id,
            )

            # Sync with AgentState if present in execution context
            self._sync_context(hits, context)

            logger.info("rag.search executed for query '%s' -> %d hits", query, len(hits))
            return ToolResult(
                success=True,
                output=hits,
            )

        except Exception as exc:
            logger.error("rag.search execution failed: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                output=[],
                error=f"RAG search error: {exc}",
            )

    def _sync_context(self, hits: list[dict[str, Any]], context: dict[str, Any]) -> None:
        """Helper to append retrieved chunks into AgentState.retrieved_context."""
        if not context:
            return

        # 1. Check if context has an AgentState instance
        state = context.get("state")
        if hasattr(state, "retrieved_context") and isinstance(state.retrieved_context, list):
            state.retrieved_context.extend(hits)
            return

        # 2. Check if context is a dictionary representing state
        if "retrieved_context" in context and isinstance(context["retrieved_context"], list):
            context["retrieved_context"].extend(hits)
