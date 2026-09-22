"""
backend/knowledge/embedder.py
==============================
Day 1 — Task 1.4: Local Embedder

Generates dense vector embeddings locally without any external API calls or cloud dependencies.

Key Features:
  - Model: sentence-transformers/all-MiniLM-L6-v2 (384-dimensional unit vectors).
  - Acceleration: Auto-detects CUDA / GPU (for high-VRAM sovereign servers)
    with automatic CPU fallback.
  - Normalization: L2-normalized embeddings ready for instant cosine / dot-product
    search in Qdrant.
  - Memory Management: Lazy-loaded singleton pattern so the model loads once
    and stays cached in memory.
  - Direct Chunk Support: Convenience methods to embed raw strings or `Chunk` dataclasses.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence

import numpy as np
import torch
import torch.nn.functional as F

if TYPE_CHECKING:
    from backend.knowledge.chunker import Chunk

logger = logging.getLogger(__name__)

# Default model and configuration
DEFAULT_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION: int = 384
DEFAULT_BATCH_SIZE: int = 32
DEFAULT_CACHE_DIR: Path = Path("data/knowledge/model_cache")


def _mean_pooling(model_output: Any, attention_mask: torch.Tensor) -> torch.Tensor:
    """
    Perform mean pooling on token embeddings weighted by the attention mask.
    This is the standard pooling strategy for sentence-transformers.
    """
    token_embeddings = model_output[0]  # First element contains all token embeddings
    input_mask_expanded = (
        attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    )
    sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, dim=1)
    sum_mask = torch.clamp(input_mask_expanded.sum(dim=1), min=1e-9)
    return sum_embeddings / sum_mask


class LocalEmbedder:
    """
    Local embedding engine running Transformer models on CPU or GPU.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        cache_dir: Path | str | None = None,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect hardware device
        if device:
            self.device = torch.device(device)
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
            logger.info("CUDA detected: LocalEmbedder running on GPU (%s)", torch.cuda.get_device_name(0))
        else:
            self.device = torch.device("cpu")
            logger.info("LocalEmbedder running on CPU")

        self._tokenizer: Any = None
        self._model: Any = None

    @property
    def dimension(self) -> int:
        """Embedding vector dimension (384 for all-MiniLM-L6-v2)."""
        return EMBEDDING_DIMENSION

    @property
    def is_loaded(self) -> bool:
        """True if tokenizer and weights are loaded in memory."""
        return self._tokenizer is not None and self._model is not None

    def load(self) -> None:
        """Load tokenizer and model weights into memory if not already loaded."""
        if self.is_loaded:
            return

        logger.info("Loading embedding model '%s' on %s...", self.model_name, self.device)
        from transformers import AutoModel, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            cache_dir=str(self.cache_dir),
        )
        self._model = AutoModel.from_pretrained(
            self.model_name,
            cache_dir=str(self.cache_dir),
        ).to(self.device)
        self._model.eval()
        logger.info("Embedding model '%s' loaded successfully.", self.model_name)

    def embed_texts(
        self,
        texts: Sequence[str],
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> list[list[float]]:
        """
        Embed a sequence of text strings into normalized vector embeddings.

        Parameters
        ----------
        texts:
            List of strings to embed.
        batch_size:
            Number of texts processed per forward pass.

        Returns
        -------
        list[list[float]]:
            List of 384-dimensional normalized float vectors.
        """
        if not texts:
            return []

        self.load()

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = list(texts[i : i + batch_size])
            # Handle empty strings gracefully to avoid tokenizer warnings
            safe_batch = [t if t and t.strip() else " " for t in batch]

            encoded = self._tokenizer(
                safe_batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                model_output = self._model(**encoded)
                sentence_embeddings = _mean_pooling(model_output, encoded["attention_mask"])
                # L2 normalize embeddings so cosine similarity == dot product
                normalized = F.normalize(sentence_embeddings, p=2, dim=1)

            # Move to CPU and convert to float lists
            batch_vectors = normalized.cpu().tolist()
            all_embeddings.extend(batch_vectors)

        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a single search query string into a normalized vector.

        Parameters
        ----------
        query:
            The search query string.

        Returns
        -------
        list[float]:
            384-dimensional float vector.
        """
        results = self.embed_texts([query])
        return results[0]

    def embed_chunks(
        self,
        chunks: Sequence[Chunk],
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> list[list[float]]:
        """
        Extract contents from Chunk objects and return their vector embeddings.

        Parameters
        ----------
        chunks:
            List of Chunk instances from backend.knowledge.chunker.
        batch_size:
            Batch size for inference.

        Returns
        -------
        list[list[float]]:
            Parallel list of vector embeddings matching the chunk order.
        """
        texts = [c.content for c in chunks]
        return self.embed_texts(texts, batch_size=batch_size)

    @staticmethod
    def compute_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
        """
        Compute cosine similarity between two normalized vectors via dot product.
        Returns score in range [-1.0, 1.0].
        """
        a = np.asarray(vec_a, dtype=np.float32)
        b = np.asarray(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))


# -- global singleton accessor -------------------------------------------------
_EMBEDDER_INSTANCE: LocalEmbedder | None = None


def get_embedder(
    model_name: str = DEFAULT_MODEL_NAME,
    cache_dir: Path | str | None = None,
) -> LocalEmbedder:
    """
    Get or initialize the shared LocalEmbedder singleton instance.
    Ensures weights are loaded once in memory and shared across requests.
    """
    global _EMBEDDER_INSTANCE
    if _EMBEDDER_INSTANCE is None or _EMBEDDER_INSTANCE.model_name != model_name:
        _EMBEDDER_INSTANCE = LocalEmbedder(model_name=model_name, cache_dir=cache_dir)
    return _EMBEDDER_INSTANCE
