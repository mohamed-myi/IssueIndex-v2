"""
Local Nomic MoE embedder with Matryoshka dimension truncation.

Model: nomic-ai/nomic-embed-text-v2-moe
Output: 256-dim vectors via Matryoshka truncation
Memory: ~958MB (FP16) or ~512MB (Q8 quantization)
Context: 512 tokens maximum
"""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ModuleNotFoundError:  # pragma: no cover
    # This symbol is patched in unit tests. At runtime, local embedding requires
    # the optional sentence-transformers dependency.
    class SentenceTransformer:  # noqa: D101
        def __init__(self, *_: object, **__: object) -> None:
            raise ModuleNotFoundError(
                "Missing dependency 'sentence-transformers'. Install it to enable local Nomic embeddings."
            )

logger = logging.getLogger(__name__)

EMBEDDING_DIM: int = 256
MAX_TOKENS: int = 512
MODEL_NAME: str = "nomic-ai/nomic-embed-text-v2-moe"


class NomicMoEEmbedder:
    """
    Generates 256-dim embeddings using nomic-embed-text-v2-moe.

    Uses Matryoshka representation learning to truncate to 256 dims.
    Supports document and query prefixing per Nomic requirements.

    The MoE model requires specific prefixes:
    - Documents: "search_document: " for indexing
    - Queries: "search_query: " for retrieval
    """

    BATCH_SIZE: int = 25

    def __init__(self, max_workers: int = 1):
        self._model = None
        self._load_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        # Import torch here to set thread limit before model load
        try:
            import torch
            # Limit CPU threads to prevent OOM on constrained instances
            torch.set_num_threads(2)
        except ImportError:
            logger.warning("torch not available; thread limiting skipped")

    def _load_model(self):
        """Lazy load model on first embedding request to avoid import-time overhead"""
        if self._model is None:
            with self._load_lock:
                # Double-check inside lock
                if self._model is None:
                    logger.info(f"Loading embedding model: {MODEL_NAME}")
                    self._model = SentenceTransformer(
                        MODEL_NAME,
                        trust_remote_code=True,
                    )
                    logger.info(f"Model loaded; output dim will be truncated to {EMBEDDING_DIM}")
        return self._model

    def warmup(self):
        """Force load the model."""
        self._load_model()

    def _truncate_and_normalize(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Apply Matryoshka truncation to 256 dims and re-normalize.

        Matryoshka embeddings preserve semantic meaning at smaller dimensions
        because the model was trained to front-load information into earlier dimensions.
        Re-normalization ensures unit vectors after truncation.
        """
        # Truncate to target dimension
        truncated = embeddings[:, :EMBEDDING_DIM]

        # Re-normalize to unit vectors after truncation
        norms = np.linalg.norm(truncated, axis=1, keepdims=True)
        # Avoid division by zero for zero vectors
        norms = np.where(norms == 0, 1, norms)
        normalized = truncated / norms

        return normalized

    def _encode_sync(
        self,
        texts: list[str],
        prefix_type: Literal["document", "query"],
    ) -> list[list[float]]:
        """
        Synchronous encoding with prefix and Matryoshka truncation.

        Runs in thread pool to avoid blocking the event loop.
        """
        if not texts:
            return []

        model = self._load_model()

        # Apply prefix per Nomic MoE requirements
        prefix = "search_document: " if prefix_type == "document" else "search_query: "
        prefixed_texts = [f"{prefix}{text}" for text in texts]

        embeddings = model.encode(
            prefixed_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        # Apply Matryoshka truncation and re-normalize
        truncated_normalized = self._truncate_and_normalize(embeddings)

        return truncated_normalized.tolist()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed documents with search_document prefix.

        Use for indexing issues, resumes, and other content to be searched.
        """
        if not texts:
            return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._encode_sync,
            texts,
            "document",
        )

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """
        Embed queries with search_query prefix.

        Use for search queries and user intent matching.
        """
        if not texts:
            return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._executor,
            self._encode_sync,
            texts,
            "query",
        )

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Backward-compatible batch embedding method.

        Defaults to document embedding for compatibility with existing code.
        """
        return await self.embed_documents(texts)

    def close(self):
        """Cleanup executor resources"""
        self._executor.shutdown(wait=False)
