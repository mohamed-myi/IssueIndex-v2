

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

    BATCH_SIZE: int = 25

    def __init__(self, max_workers: int = 1):
        self._model = None
        self._load_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

        try:
            import torch


            torch.set_num_threads(2)
        except ImportError:
            logger.warning("torch not available; thread limiting skipped")

    def _load_model(self):
        if self._model is None:
            with self._load_lock:

                if self._model is None:
                    logger.info(f"Loading embedding model: {MODEL_NAME}")
                    self._model = SentenceTransformer(
                        MODEL_NAME,
                        trust_remote_code=True,
                    )
                    logger.info(f"Model loaded; output dim will be truncated to {EMBEDDING_DIM}")
        return self._model

    def warmup(self):
        self._load_model()

    def _truncate_and_normalize(self, embeddings: np.ndarray) -> np.ndarray:

        truncated = embeddings[:, :EMBEDDING_DIM]


        norms = np.linalg.norm(truncated, axis=1, keepdims=True)

        norms = np.where(norms == 0, 1, norms)
        normalized = truncated / norms

        return normalized

    def _encode_sync(
        self,
        texts: list[str],
        prefix_type: Literal["document", "query"],
    ) -> list[list[float]]:
        if not texts:
            return []

        model = self._load_model()


        prefix = "search_document: " if prefix_type == "document" else "search_query: "
        prefixed_texts = [f"{prefix}{text}" for text in texts]

        embeddings = model.encode(
            prefixed_texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )


        truncated_normalized = self._truncate_and_normalize(embeddings)

        return truncated_normalized.tolist()

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
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
        return await self.embed_documents(texts)

    def close(self):
        self._executor.shutdown(wait=False)
