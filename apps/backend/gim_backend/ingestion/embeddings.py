

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .gatherer import IssueData

logger = logging.getLogger(__name__)

EMBEDDING_DIM: int = 256


@dataclass
class EmbeddedIssue:
    issue: IssueData
    embedding: list[float]


@runtime_checkable
class EmbeddingProvider(Protocol):

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class DocumentQueryEmbedder(Protocol):

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        ...


class NomicEmbedder:

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
        model = self._load_model()
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
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
        self._executor.shutdown(wait=False)


async def embed_issue_stream(
    issues: AsyncIterator[IssueData],
    provider: EmbeddingProvider,
    batch_size: int | None = None,
) -> AsyncIterator[EmbeddedIssue]:
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
            if batch_number % 10 == 0:
                logger.info(
                    f"Embedding progress: {total_embedded} issues embedded (batch {batch_number})",
                    extra={"issues_embedded": total_embedded, "batch_number": batch_number},
                )
            batch.clear()


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
