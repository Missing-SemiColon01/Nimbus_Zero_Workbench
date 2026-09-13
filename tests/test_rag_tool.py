"""
tests/test_rag_tool.py
=======================
Unit tests for backend/tools/rag_tool.py (Day 2 — Task 2.1: RAG Search Tool)

Tests verify Tool interface compliance, argument validation, retrieval execution,
AgentState context synchronization, and ToolRegistry registration.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.agents.state import AgentState
from backend.tools.contracts import Tool, ToolResult
from backend.tools.rag_tool import RAGSearchTool
from backend.tools.registry import ToolRegistry


# -- fixtures ------------------------------------------------------------------

@pytest.fixture
def sample_hits():
    return [
        {
            "content": "Emergency valve threshold: 140 PSI.",
            "source": "safety_spec.pdf",
            "page": 2,
            "chunk_id": "c_001",
            "document_id": "spec_doc",
            "score": 0.88,
            "metadata": {},
        },
        {
            "content": "Inspection scheduled for maintenance.",
            "source": "safety_spec.pdf",
            "page": 3,
            "chunk_id": "c_002",
            "document_id": "spec_doc",
            "score": 0.72,
            "metadata": {},
        },
    ]


@pytest.fixture
def mock_retriever(sample_hits):
    retriever = MagicMock()
    retriever.search.return_value = sample_hits
    return retriever


# -- tests ---------------------------------------------------------------------

class TestRAGSearchToolInterface:
    def test_tool_metadata(self):
        tool = RAGSearchTool(retriever=MagicMock())
        assert isinstance(tool, Tool)
        assert tool.name == "rag.search"
        assert "search" in tool.description.lower()
        assert "query" in tool.parameters["properties"]
        assert "query" in tool.parameters["required"]


class TestRAGSearchToolExecution:
    @pytest.mark.asyncio
    async def test_empty_query_returns_error(self, mock_retriever):
        tool = RAGSearchTool(retriever=mock_retriever)

        # Empty string
        res = await tool.execute({"query": ""}, context={})
        assert res.success is False
        assert "query" in res.error.lower()

        # Missing query key
        res2 = await tool.execute({}, context={})
        assert res2.success is False

        # Whitespace only
        res3 = await tool.execute({"query": "   "}, context={})
        assert res3.success is False

    @pytest.mark.asyncio
    async def test_successful_search(self, mock_retriever, sample_hits):
        tool = RAGSearchTool(retriever=mock_retriever)

        res = await tool.execute(
            {"query": "valve operating pressure", "top_k": 3, "document_id": "doc123"},
            context={},
        )

        assert isinstance(res, ToolResult)
        assert res.success is True
        assert res.output == sample_hits
        assert len(res.output) == 2

        # Verify arguments forwarded to retriever
        mock_retriever.search.assert_called_once_with(
            query="valve operating pressure",
            top_k=3,
            score_threshold=None,
            filter_doc_id="doc123",
        )

    @pytest.mark.asyncio
    async def test_sync_with_agent_state(self, mock_retriever, sample_hits):
        tool = RAGSearchTool(retriever=mock_retriever)
        state = AgentState(
            task_id="t1",
            user_request="Check valve safety",
        )

        assert len(state.retrieved_context) == 0

        res = await tool.execute(
            {"query": "valve inspection"},
            context={"state": state},
        )

        assert res.success is True
        # Verify state.retrieved_context was populated
        assert len(state.retrieved_context) == 2
        assert state.retrieved_context[0]["content"] == "Emergency valve threshold: 140 PSI."
        assert state.retrieved_context[0]["page"] == 2

    @pytest.mark.asyncio
    async def test_sync_with_dict_context(self, mock_retriever):
        tool = RAGSearchTool(retriever=mock_retriever)
        context = {"retrieved_context": []}

        res = await tool.execute({"query": "valve inspection"}, context=context)
        assert res.success is True
        assert len(context["retrieved_context"]) == 2

    @pytest.mark.asyncio
    async def test_retriever_exception_handled_gracefully(self):
        retriever = MagicMock()
        retriever.search.side_effect = RuntimeError("Qdrant index connection failed")

        tool = RAGSearchTool(retriever=retriever)
        res = await tool.execute({"query": "test query"}, context={})

        assert res.success is False
        assert res.output == []
        assert "Qdrant index connection failed" in (res.error or "")


class TestRegistryIntegration:
    @pytest.mark.asyncio
    async def test_registered_and_executable_from_registry(self, mock_retriever, sample_hits):
        registry = ToolRegistry()
        tool = RAGSearchTool(retriever=mock_retriever)
        registry.register(tool)

        assert "rag.search" in registry.names()
        retrieved_tool = registry.get("rag.search")
        assert retrieved_tool is tool

        res = await retrieved_tool.execute({"query": "safety valve"}, context={})
        assert res.success is True
        assert len(res.output) == 2
