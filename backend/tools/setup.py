"""
backend/tools/setup.py
======================
Day 2 — Task 2.4: Tool Registry Wiring

Builds and configures the default ToolRegistry containing all sovereign workbench tools:
  - "rag.search": Semantic vector retrieval with exact page citations.
  - "vision.analyze": Multimodal vision document understanding & OCR fallback.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings, get_settings
from backend.knowledge.retriever import KnowledgeRetriever, get_retriever
from backend.models.providers import ModelProvider, ModelProviderRegistry, OllamaProvider
from backend.models.registry import ModelRegistry
from backend.tools.rag_tool import RAGSearchTool
from backend.tools.registry import ToolRegistry
from backend.tools.vision_tool import VisionAnalyzeTool

logger = logging.getLogger(__name__)


def build_tool_registry(
    settings: Settings | None = None,
    model_registry: ModelRegistry | None = None,
    provider_registry: ModelProviderRegistry | ModelProvider | None = None,
    retriever: KnowledgeRetriever | None = None,
) -> ToolRegistry:
    """
    Construct and populate the central ToolRegistry with all available sovereign tools.

    Parameters
    ----------
    settings:
        Application settings instance (defaults to get_settings()).
    model_registry:
        Optional ModelRegistry for model resolution.
    provider_registry:
        Optional ModelProviderRegistry for model inference.
    retriever:
        Optional KnowledgeRetriever for RAG retrieval.

    Returns
    -------
    ToolRegistry:
        Configured registry ready for agent execution and API routes.
    """
    cfg = settings or get_settings()
    registry = ToolRegistry()

    # 1. Register RAG Search Tool
    rag_retriever = retriever or get_retriever()
    rag_tool = RAGSearchTool(retriever=rag_retriever)
    registry.register(rag_tool)
    logger.info("Registered tool: '%s'", rag_tool.name)

    # 2. Register Vision Analyze Tool
    resolved_model_registry = model_registry
    if resolved_model_registry is None and cfg.models_config.exists():
        resolved_model_registry = ModelRegistry(cfg.models_config)

    resolved_providers = provider_registry
    if resolved_providers is None:
        resolved_providers = ModelProviderRegistry({"ollama": OllamaProvider(cfg.ollama_base_url)})

    vision_tool = VisionAnalyzeTool(
        provider=resolved_providers,
        registry=resolved_model_registry,
    )
    registry.register(vision_tool)
    logger.info("Registered tool: '%s'", vision_tool.name)

    return registry
