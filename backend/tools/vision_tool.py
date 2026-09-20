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

import asyncio
import base64
import io
import logging
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image

from backend.core.config import get_settings
from backend.knowledge.ocr import extract_text_from_image, ocr_image
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

SUPPORTED_EXTENSIONS: set[str] = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif", ".pdf"
}


def render_pdf_page_to_image(pdf_source: str | Path | bytes, page_number: int = 1, dpi: int = 200) -> bytes:
    """
    Render a specific page of a PDF file to PNG image bytes.
    page_number is 1-indexed.
    """
    if isinstance(pdf_source, bytes):
        doc = fitz.open(stream=pdf_source, filetype="pdf")
    else:
        path = Path(pdf_source)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")
        doc = fitz.open(str(path))

    try:
        if doc.page_count == 0:
            raise ValueError("PDF document contains no pages.")
        if not (1 <= page_number <= doc.page_count):
            raise ValueError(f"Page number {page_number} is out of range (1 to {doc.page_count}).")

        page = doc.load_page(page_number - 1)
        matrix = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()


def encode_image_to_base64(image_source: str | Path | bytes) -> str:
    """
    Load an image from path or bytes and return a base64-encoded ASCII string.
    If given a PDF path or bytes, automatically renders the first page.
    """
    if isinstance(image_source, bytes):
        if image_source.startswith(b"%PDF"):
            png_bytes = render_pdf_page_to_image(image_source, page_number=1)
            return base64.b64encode(png_bytes).decode("utf-8")
        return base64.b64encode(image_source).decode("utf-8")

    path = Path(image_source)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported image format '{path.suffix}'. "
            f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if suffix == ".pdf":
        png_bytes = render_pdf_page_to_image(path, page_number=1)
        return base64.b64encode(png_bytes).decode("utf-8")

    image_bytes = path.read_bytes()
    return base64.b64encode(image_bytes).decode("utf-8")


class VisionAnalyzeTool(Tool):
    """
    Autonomous tool for analyzing page images, blueprints, scanned PDFs, and equipment photos.
    """

    name = "vision.analyze"
    description = (
        "Analyze an image file, diagram, photo, or rendered PDF page using the sovereign multimodal vision model. "
        "Automatically renders scanned PDFs, runs OCR extraction, transcribes handwriting and stamps, and extracts "
        "visual defect findings, charts, or equipment details."
    )
    parameters = {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string",
                "description": "Path to the image file or PDF document to analyze (PNG, JPG, PDF, etc.).",
            },
            "document_path": {
                "type": "string",
                "description": "Optional alias for image_path to analyze a document or scanned PDF.",
            },
            "page_number": {
                "type": "integer",
                "description": "Optional page number to render and analyze for multi-page PDFs (1-indexed, default: 1).",
                "default": 1,
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
        Execute visual analysis and OCR on the target image or scanned PDF.
        """
        raw_path = arguments.get("image_path") or arguments.get("document_path")
        if not raw_path or not str(raw_path).strip():
            return ToolResult(
                success=False,
                output={},
                error="Argument 'image_path' or 'document_path' is required and cannot be empty.",
            )

        prompt = arguments.get("prompt") or DEFAULT_VISION_PROMPT
        page_number = int(arguments.get("page_number", 1))

        # 1. Base64 Encode Image & Render PDF Page if applicable
        try:
            target_path = Path(raw_path)
            is_pdf = target_path.is_file() and target_path.suffix.lower() == ".pdf"
            if is_pdf:
                raw_bytes = await asyncio.to_thread(render_pdf_page_to_image, target_path, page_number=page_number)
                base64_image = base64.b64encode(raw_bytes).decode("utf-8")
            else:
                base64_image = encode_image_to_base64(raw_path)
                raw_bytes = base64.b64decode(base64_image)
        except Exception as exc:
            logger.error("Failed to read/render image for vision analysis: %s", exc)
            return ToolResult(
                success=False,
                output={},
                error=f"Image load error: {exc}",
            )

        # 2. Extract OCR text from the rendered image / document
        ocr_text = ""
        try:
            ocr_result = await asyncio.to_thread(ocr_image, raw_bytes)
            if ocr_result.has_text:
                ocr_text = ocr_result.text.strip()
        except Exception as ocr_exc:
            logger.warning("OCR extraction during vision analysis failed: %s", ocr_exc)

        # 3. Construct ModelRequest with image payload
        # If OCR text is available, enrich the prompt so vision model has full multimodal context
        model_prompt = prompt
        if ocr_text:
            model_prompt = (
                f"{prompt}\n\n"
                f"[Transcribed Text from OCR]:\n{ocr_text}"
            )

        request = ModelRequest(
            prompt=model_prompt,
            images=[base64_image],
            required_capabilities={"vision"},
            required_modality="image",
        )

        # 4. Resolve Vision Model
        try:
            model = self._resolve_model(request)
        except Exception as exc:
            logger.error("Failed to resolve vision model: %s", exc)
            return ToolResult(
                success=False,
                output={},
                error=f"Model routing error: {exc}",
            )

        # 5. Invoke Vision Model
        try:
            logger.info("Executing vision.analyze on '%s' with model '%s'...", raw_path, model.model)
            response: ModelResponse = await self.provider.generate(model, request)

            combined_result_parts: list[str] = []
            if ocr_text:
                combined_result_parts.append(f"OCR Transcription:\n{ocr_text}")
            combined_result_parts.append(f"Visual Analysis:\n{response.content}")
            combined_result = "\n\n".join(combined_result_parts)

            output_data = {
                "analysis": response.content,
                "ocr_text": ocr_text,
                "combined_result": combined_result,
                "model": model.id,
                "image_path": str(raw_path),
                "is_pdf": is_pdf,
                "page_number": page_number if is_pdf else None,
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
