"""Streaming embedding generation for issue vectorization"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .gatherer import IssueData

logger = logging.getLogger(__name__)

EMBEDDING_DIM: int = 768


@dataclass
class EmbeddedIssue:
    issue: IssueData
    embedding: list[float]


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers; enables mock injection in tests"""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class NomicEmbedder:
    """
    Generates 768-dim embeddings using nomic-ai/nomic-embed-text-v1.5.
    Model lazy loads on first embed call to avoid import-time overhead.
    """

    MODEL_NAME: str = "nomic-ai/nomic-embed-text-v1.5"
    BATCH_SIZE: int = 25

    def __init__(self):
        self._model = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info(f"Loading embedding model: {self.MODEL_NAME}")
            self._model = SentenceTransformer(
                self.MODEL_NAME,
                trust_remote_code=True,
            )
            logger.info("Embedding model loaded")
        return self._model

    def _encode_sync(self, texts: list[str]) -> list[list[float]]:
        """Synchronous encoding runs in thread pool to avoid blocking"""
        model = self._load_model()
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Encodes texts in executor to keep event loop responsive"""
        if not texts:
            return []

        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            self._executor,
            self._encode_sync,
            texts,
        )
        return embeddings

    def close(self):
        """Cleanup executor resources"""
        self._executor.shutdown(wait=False)


async def embed_issue_stream(
    issues: AsyncIterator[IssueData],
    provider: EmbeddingProvider,
    batch_size: int = 25,
) -> AsyncIterator[EmbeddedIssue]:
    """
    Consumes issue stream, batches for embedding API, yields embedded issues.
    Memory ceiling: holds at most batch_size issues + embeddings at once.
    """
    batch: list[IssueData] = []

    async for issue in issues:
        batch.append(issue)

        if len(batch) >= batch_size:
            texts = [f"{i.title}\n{i.body_text}" for i in batch]
            embeddings = await provider.embed_batch(texts)

            for iss, emb in zip(batch, embeddings):
                yield EmbeddedIssue(issue=iss, embedding=emb)

            batch.clear()

    # Flush remaining partial batch
    if batch:
        texts = [f"{i.title}\n{i.body_text}" for i in batch]
        embeddings = await provider.embed_batch(texts)

        for iss, emb in zip(batch, embeddings):
            yield EmbeddedIssue(issue=iss, embedding=emb)

