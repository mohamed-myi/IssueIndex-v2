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


class VertexEmbedder:
    """Generates 768-dim embeddings using Google Vertex AI text-embedding-004"""

    # Vertex AI text-embedding-004 has a 20K token limit per request.
    # With ~1000 tokens per issue (4000 char body), batch of 10 stays under limit.
    BATCH_SIZE: int = 10

    def __init__(self, project: str, region: str = "us-central1"):
        import vertexai
        from vertexai.language_models import TextEmbeddingModel

        vertexai.init(project=project, location=region)
        self._model = TextEmbeddingModel.from_pretrained("text-embedding-004")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        from vertexai.language_models import TextEmbeddingInput

        if not texts:
            return []

        # text-embedding-004 supports output_dimensionality to match DB schema
        inputs = [TextEmbeddingInput(text, "RETRIEVAL_DOCUMENT") for text in texts]
        embeddings = self._model.get_embeddings(
            inputs,
            output_dimensionality=768
        )
        return [e.values for e in embeddings]

    def close(self):
        pass


async def embed_issue_stream(
    issues: AsyncIterator[IssueData],
    provider: EmbeddingProvider,
    batch_size: int | None = None,
) -> AsyncIterator[EmbeddedIssue]:
    """
    Consumes issue stream, batches for embedding API, yields embedded issues.
    Memory ceiling: holds at most batch_size issues + embeddings at once.

    Uses provider.BATCH_SIZE if available, otherwise defaults to 25.
    """
    # Use provider-specific batch size to respect API limits (e.g. Vertex AI 20K tokens)
    effective_batch_size = batch_size or getattr(provider, "BATCH_SIZE", 25)
    batch: list[IssueData] = []
    total_embedded = 0
    batch_number = 0

    async for issue in issues:
        batch.append(issue)

        if len(batch) >= effective_batch_size:
            batch_number += 1
            texts = [f"{i.title}\n{i.body_text}" for i in batch]
            try:
                embeddings = await provider.embed_batch(texts)
            except Exception as e:
                logger.error(
                    f"Embedding API failed at batch {batch_number} (total {total_embedded} embedded so far): {e}",
                    extra={"batch_number": batch_number, "embedded_so_far": total_embedded, "error": str(e)},
                )
                raise

            for iss, emb in zip(batch, embeddings):
                yield EmbeddedIssue(issue=iss, embedding=emb)

            total_embedded += len(batch)
            # Log progress every 10 batches (100 issues with batch_size=10) to avoid log spam
            if batch_number % 10 == 0:
                logger.info(
                    f"Embedding progress: {total_embedded} issues embedded (batch {batch_number})",
                    extra={"issues_embedded": total_embedded, "batch_number": batch_number},
                )
            batch.clear()

    # Flush remaining partial batch
    if batch:
        batch_number += 1
        texts = [f"{i.title}\n{i.body_text}" for i in batch]
        try:
            embeddings = await provider.embed_batch(texts)
        except Exception as e:
            logger.error(
                f"Embedding API failed at final batch {batch_number} (total {total_embedded} embedded so far): {e}",
                extra={"batch_number": batch_number, "embedded_so_far": total_embedded, "error": str(e)},
            )
            raise

        for iss, emb in zip(batch, embeddings):
            yield EmbeddedIssue(issue=iss, embedding=emb)
        total_embedded += len(batch)

    logger.info(
        f"Embedding complete: {total_embedded} issues in {batch_number} batches",
        extra={"total_embedded": total_embedded, "total_batches": batch_number},
    )

