"""
backend/tools/vision_tool.py
=============================
Day 2 — Task 2.2: Multimodal Vision Tool

Enables autonomous visual document understanding, chart inspection, and OCR fallback
using the sovereign vision model (qwen2.5-vl:7b via Ollama).

Capabilities:
  - Tool Name: "vision.analyze"
  - Inputs:
      - "image_path" (str, required): Path to image or rendered document page.
      - "prompt" (str, optional): Instruction for the vision model.
  - Base64 Encoding: Encodes image into base64 payload required by Ollama vision API.
  - Dynamic Routing: Resolves model with capabilities={"vision"} and modality="image".
  - Graceful Error Handling: Validates file existence and traps inference errors cleanly.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Any

from backend.core.config import get_settings
from backend.models.contracts import ModelDefinition, ModelRequest, ModelResponse
from backend.models.providers import ModelProvider, ModelProviderRegistry, OllamaProvider
from backend.models.registry import ModelRegistry
from backend.models.router import ModelRouter
from backend.tools.contracts import Tool, ToolResult

logger = logging.getLogger(__name__)

DEFAULT_VISION_PROMPT: str = (
    "Examine this document image thoroughly. Transcribe all text, numbers, stamps, "
    "and signatures, and describe any diagrams, charts, or defects visible."
)

SUPPORTED_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"}


def encode_image_to_base64(image_source: str | Path | bytes) -> str:
    """
    Load an image from path or bytes and return a base64-encoded ASCII string.
    """
    if isinstance(image_source, bytes):
        return base64.b64encode(image_source).decode("utf-8")

    path = Path(image_source)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image format '{path.suffix}'. "
            f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    image_bytes = path.read_bytes()
    return base64.b64encode(image_bytes).decode("utf-8")


class VisionAnalyzeTool(Tool):
    """
    Autonomous tool for analyzing page images, blueprints, and scanned schematics.
    """

    name = "vision.analyze"
    description = (
        "Analyze an image file or rendered document page using the sovereign multimodal vision model. "
        "Transcribes handwriting, tables, and stamps, and extracts visual defect findings or diagram details."
    )
    parameters = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the image file to analyze (PNG, JPG, WEBP, etc.).",
            },
            "prompt": {
                "type": "string",
                "description": "Specific question or instruction for the vision model (optional).",
                "default": DEFAULT_VISION_PROMPT,
            },
        },
        "required": ["image_path"],
    }

    def __init__(
        self,
        provider: ModelProvider | ModelProviderRegistry | None = None,
        registry: ModelRegistry | None = None,
        router: ModelRouter | None = None,
    ) -> None:
        self.settings = get_settings()

        # Initialize or resolve ModelRegistry
        if registry:
            self.registry = registry
        elif self.settings.models_config.exists():
            self.registry = ModelRegistry(self.settings.models_config)
        else:
            self.registry = None

        # Initialize or resolve ModelRouter
        if router:
            self.router = router
        elif self.registry:
            self.router = ModelRouter(self.registry)
        else:
            self.router = None

        # Initialize or resolve Provider / ProviderRegistry
        if provider:
            self.provider = provider
        else:
            ollama_url = self.settings.ollama_base_url
            self.provider = ModelProviderRegistry({"ollama": OllamaProvider(ollama_url)})

    def _resolve_model(self, request: ModelRequest) -> ModelDefinition:
        """Find the configured vision model."""
        if self.router:
            return self.router.select(request)

        # Fallback default vision definition if router is not present
        return ModelDefinition(
            id="vision",
            runtime="ollama",
            model="qwen2.5-vl:7b",
            capabilities={"vision", "document_understanding"},
            modalities={"text", "image"},
            priority=10,
        )

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        """
        Execute visual analysis on the target image.
        """
        raw_path = arguments.get("image_path")
        if not raw_path or not str(raw_path).strip():
            return ToolResult(
                success=False,
                output={},
                error="Argument 'image_path' is required and cannot be empty.",
            )

        prompt = arguments.get("prompt") or DEFAULT_VISION_PROMPT

        # 1. Base64 Encode Image
        try:
            base64_image = encode_image_to_base64(raw_path)
        except Exception as exc:
            logger.error("Failed to read image for vision analysis: %s", exc)
            return ToolResult(
                success=False,
                output={},
                error=f"Image load error: {exc}",
            )

        # 2. Construct ModelRequest
        request = ModelRequest(
            prompt=prompt,
            images=[base64_image],
            required_capabilities={"vision"},
            required_modality="image",
        )

        # 3. Resolve Vision Model
        try:
            model = self._resolve_model(request)
        except Exception as exc:
            logger.error("Failed to resolve vision model: %s", exc)
            return ToolResult(
                success=False,
                output={},
                error=f"Model routing error: {exc}",
            )

        # 4. Invoke Vision Model
        try:
            logger.info("Executing vision.analyze on '%s' with model '%s'...", raw_path, model.model)
            response: ModelResponse = await self.provider.generate(model, request)

            output_data = {
                "analysis": response.content,
                "model": model.id,
                "image_path": str(raw_path),
            }

            # If execution context has tool_results list, record it
            if context and "tool_results" in context and isinstance(context["tool_results"], list):
                context["tool_results"].append({"tool": self.name, "output": output_data})

            return ToolResult(
                success=True,
                output=output_data,
            )

        except Exception as exc:
            logger.error("Vision model generation failed: %s", exc, exc_info=True)
            return ToolResult(
                success=False,
                output={},
                error=f"Vision model inference error: {exc}",
            )
