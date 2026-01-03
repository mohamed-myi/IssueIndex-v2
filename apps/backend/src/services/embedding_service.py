"""
Application-scoped embedding service for query vectorization.
Wraps NomicEmbedder as a singleton to avoid reloading the model per request.
Uses asyncio.Lock with double-check pattern for thread safety in multi-worker environments.
"""

import asyncio
import logging
from typing import Optional

from src.ingestion.embeddings import NomicEmbedder, EMBEDDING_DIM

logger = logging.getLogger(__name__)

# Module-level singleton with lock for thread-safe initialization
_embedder: Optional[NomicEmbedder] = None
_embedder_lock: asyncio.Lock = asyncio.Lock()


async def get_embedder() -> NomicEmbedder:
    """
    Returns the singleton NomicEmbedder instance.
    Uses double-check locking to prevent race conditions in multi-worker environments.
    Model loads lazily on first embed call.
    """
    global _embedder
    
    # Fast path: already initialized
    if _embedder is not None:
        return _embedder
    
    # Slow path: acquire lock and double-check
    async with _embedder_lock:
        # Another worker may have initialized while waiting
        if _embedder is None:
            logger.info("Initializing embedding service singleton")
            _embedder = NomicEmbedder()
    
    return _embedder


async def embed_query(text: str) -> Optional[list[float]]:
    """
    Embeds a single search query text into a 768-dim vector.
    Uses the singleton embedder to avoid model reload overhead.
    
    Args:
        text: The search query to embed
        
    Returns:
        768-dimensional normalized embedding vector, or None if embedding fails
    """
    try:
        embedder = await get_embedder()
        embeddings = await embedder.embed_batch([text])
        if embeddings and len(embeddings) > 0:
            return embeddings[0]
        return None
    except Exception as e:
        logger.warning(f"Embedding query failed: {e}")
        return None


async def embed_queries(texts: list[str]) -> list[Optional[list[float]]]:
    """
    Embeds multiple search queries in a single batch.
    More efficient than calling embed_query repeatedly.
    
    Args:
        texts: List of search queries to embed
        
    Returns:
        List of 768-dimensional normalized embedding vectors (None for failed embeddings)
    """
    if not texts:
        return []
    
    try:
        embedder = await get_embedder()
        return await embedder.embed_batch(texts)
    except Exception as e:
        logger.warning(f"Batch embedding failed: {e}")
        return [None] * len(texts)


async def close_embedder() -> None:
    """
    Cleanup embedder resources. Called on application shutdown.
    Acquires lock to prevent race with initialization.
    """
    global _embedder
    
    async with _embedder_lock:
        if _embedder is not None:
            logger.info("Closing embedding service")
            _embedder.close()
            _embedder = None


def reset_embedder_for_testing() -> None:
    """For testing only; resets singleton state without lock (not async-safe)."""
    global _embedder
    _embedder = None


__all__ = [
    "EMBEDDING_DIM",
    "get_embedder",
    "embed_query",
    "embed_queries", 
    "close_embedder",
    "reset_embedder_for_testing",
]

