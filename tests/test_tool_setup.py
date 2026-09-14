"""
tests/test_tool_setup.py
=========================
Unit tests for backend/tools/setup.py (Day 2 — Task 2.4: Tool Registry Wiring)

Tests verify tool registry construction, tool discovery by name, custom dependency
injection, and FastAPI application lifespan integration.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.tools.contracts import Tool
from backend.tools.rag_tool import RAGSearchTool
from backend.tools.registry import ToolRegistry
from backend.tools.setup import build_tool_registry
from backend.tools.vision_tool import VisionAnalyzeTool
from backend.artifacts.tools import DocumentCreateTool, PdfCreateTool, PresentationCreateTool


class TestBuildToolRegistry:
    def test_default_build_registers_all_sovereign_tools(self):
        mock_retriever = MagicMock()
        mock_model_registry = MagicMock()
        mock_provider = MagicMock()

        registry = build_tool_registry(
            retriever=mock_retriever,
            model_registry=mock_model_registry,
            provider_registry=mock_provider,
        )

        assert isinstance(registry, ToolRegistry)
        names = registry.names()
        assert "rag.search" in names
        assert "vision.analyze" in names
        assert {"document.create", "presentation.create", "pdf.create"}.issubset(names)

        # Verify tool instances
        rag_tool = registry.get("rag.search")
        assert isinstance(rag_tool, RAGSearchTool)
        assert rag_tool.retriever is mock_retriever

        vision_tool = registry.get("vision.analyze")
        assert isinstance(vision_tool, VisionAnalyzeTool)
        assert vision_tool.provider is mock_provider

        assert isinstance(registry.get("document.create"), DocumentCreateTool)
        assert isinstance(registry.get("presentation.create"), PresentationCreateTool)
        assert isinstance(registry.get("pdf.create"), PdfCreateTool)

    def test_tool_instances_conform_to_tool_contract(self):
        mock_retriever = MagicMock()
        registry = build_tool_registry(retriever=mock_retriever)

        for name in registry.names():
            tool = registry.get(name)
            assert isinstance(tool, Tool)
            assert hasattr(tool, "execute")
            assert hasattr(tool, "name")
            assert hasattr(tool, "description")
            assert hasattr(tool, "parameters")


class TestFastAPILifespanWiring:
    def test_app_lifespan_wires_tools_into_app_state(self):
        """Verify that FastAPI lifespan populates app.state.tools with both tools."""
        with TestClient(app) as client:
            # Trigger health endpoint to activate lifespan
            response = client.get("/api/v1/health")
            assert response.status_code == 200

            # Inspect app.state.tools
            assert hasattr(app.state, "tools")
            tools: ToolRegistry = app.state.tools
            assert isinstance(tools, ToolRegistry)
            assert "rag.search" in tools.names()
            assert "vision.analyze" in tools.names()
            assert {"document.create", "presentation.create", "pdf.create"}.issubset(tools.names())
