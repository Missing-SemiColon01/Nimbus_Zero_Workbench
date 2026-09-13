"""
tests/test_vision.py
=====================
Unit tests for backend/tools/vision_tool.py (Day 2 — Task 2.2: Multimodal Vision Tool)

Tests verify Tool interface compliance, base64 image encoding, ModelRequest
construction, vision model invocation, context recording, and ToolRegistry integration.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.tools.contracts import Tool, ToolResult
from backend.tools.registry import ToolRegistry
from backend.tools.vision_tool import (
    DEFAULT_VISION_PROMPT,
    VisionAnalyzeTool,
    encode_image_to_base64,
)


# -- fixtures / helpers --------------------------------------------------------

def _create_dummy_image(path: Path) -> Path:
    """Create a minimal PNG image file."""
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img.save(path, format="PNG")
    return path


@pytest.fixture
def dummy_png(tmp_path: Path) -> Path:
    return _create_dummy_image(tmp_path / "test_valve.png")


@pytest.fixture
def mock_vision_model() -> ModelDefinition:
    return ModelDefinition(
        id="vision",
        runtime="ollama",
        model="qwen2.5-vl:7b",
        capabilities={"vision", "document_understanding"},
        modalities={"text", "image"},
        priority=10,
    )


@pytest.fixture
def mock_provider() -> MagicMock:
    provider = MagicMock()
    provider.generate = AsyncMock(
        return_value=ModelResponse(
            content="Visual analysis: Valve shows surface rust and pressure gauge reads 120 PSI.",
            model_id="vision",
        )
    )
    return provider


# -- tests ---------------------------------------------------------------------

class TestBase64Encoding:
    def test_encode_from_path(self, dummy_png: Path):
        b64 = encode_image_to_base64(dummy_png)
        assert isinstance(b64, str)
        assert len(b64) > 0

        # Verify decoded bytes are valid PNG
        decoded = base64.b64decode(b64)
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"

    def test_encode_from_bytes(self):
        raw_bytes = b"fake_image_data"
        b64 = encode_image_to_base64(raw_bytes)
        assert b64 == base64.b64encode(raw_bytes).decode("utf-8")

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            encode_image_to_base64(tmp_path / "non_existent.png")

    def test_unsupported_extension_raises(self, tmp_path: Path):
        txt_file = tmp_path / "document.txt"
        txt_file.write_text("Hello")
        with pytest.raises(ValueError, match="Unsupported image format"):
            encode_image_to_base64(txt_file)


class TestVisionToolInterface:
    def test_tool_metadata(self):
        tool = VisionAnalyzeTool()
        assert isinstance(tool, Tool)
        assert tool.name == "vision.analyze"
        assert "vision" in tool.description.lower()
        assert "image_path" in tool.parameters["properties"]
        assert "image_path" in tool.parameters["required"]


class TestVisionToolExecution:
    @pytest.mark.asyncio
    async def test_missing_image_path_returns_error(self, mock_provider):
        tool = VisionAnalyzeTool(provider=mock_provider)

        res = await tool.execute({}, context={})
        assert res.success is False
        assert "image_path" in res.error.lower()

        res2 = await tool.execute({"image_path": "   "}, context={})
        assert res2.success is False

    @pytest.mark.asyncio
    async def test_successful_analysis(self, dummy_png: Path, mock_provider, mock_vision_model):
        tool = VisionAnalyzeTool(provider=mock_provider)
        tool._resolve_model = MagicMock(return_value=mock_vision_model)

        res = await tool.execute(
            {"image_path": str(dummy_png), "prompt": "Check valve defects"},
            context={},
        )

        assert isinstance(res, ToolResult)
        assert res.success is True
        assert "analysis" in res.output
        assert "surface rust" in res.output["analysis"]
        assert res.output["model"] == "vision"
        assert res.output["image_path"] == str(dummy_png)

        # Verify ModelRequest construction
        mock_provider.generate.assert_awaited_once()
        call_model, call_request = mock_provider.generate.await_args[0]
        assert call_model.id == "vision"
        assert call_request.prompt == "Check valve defects"
        assert call_request.required_capabilities == {"vision"}
        assert call_request.required_modality == "image"
        assert len(call_request.images) == 1

    @pytest.mark.asyncio
    async def test_default_prompt_applied_when_omitted(self, dummy_png: Path, mock_provider, mock_vision_model):
        tool = VisionAnalyzeTool(provider=mock_provider)
        tool._resolve_model = MagicMock(return_value=mock_vision_model)

        res = await tool.execute({"image_path": str(dummy_png)}, context={})
        assert res.success is True

        _, call_request = mock_provider.generate.await_args[0]
        assert call_request.prompt == DEFAULT_VISION_PROMPT

    @pytest.mark.asyncio
    async def test_tool_results_recorded_in_context(self, dummy_png: Path, mock_provider, mock_vision_model):
        tool = VisionAnalyzeTool(provider=mock_provider)
        tool._resolve_model = MagicMock(return_value=mock_vision_model)
        context = {"tool_results": []}

        res = await tool.execute({"image_path": str(dummy_png)}, context=context)
        assert res.success is True
        assert len(context["tool_results"]) == 1
        assert context["tool_results"][0]["tool"] == "vision.analyze"

    @pytest.mark.asyncio
    async def test_provider_failure_returns_error_cleanly(self, dummy_png: Path, mock_vision_model):
        failing_provider = MagicMock()
        failing_provider.generate = AsyncMock(side_effect=RuntimeError("Ollama connection timeout"))

        tool = VisionAnalyzeTool(provider=failing_provider)
        tool._resolve_model = MagicMock(return_value=mock_vision_model)

        res = await tool.execute({"image_path": str(dummy_png)}, context={})
        assert res.success is False
        assert "Ollama connection timeout" in (res.error or "")


class TestRegistryIntegration:
    @pytest.mark.asyncio
    async def test_registered_and_executable(self, dummy_png: Path, mock_provider, mock_vision_model):
        registry = ToolRegistry()
        tool = VisionAnalyzeTool(provider=mock_provider)
        tool._resolve_model = MagicMock(return_value=mock_vision_model)
        registry.register(tool)

        assert "vision.analyze" in registry.names()
        retrieved_tool = registry.get("vision.analyze")
        assert retrieved_tool is tool

        res = await retrieved_tool.execute({"image_path": str(dummy_png)}, context={})
        assert res.success is True
