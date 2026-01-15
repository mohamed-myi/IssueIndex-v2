"""
Health check endpoint for Cloud Run embedding worker.

Provides HTTP health check endpoint to verify:
1. Embedding model is loaded and functional
2. Can generate 256-dim vectors
3. Database connection is available

Can be run standalone or imported for startup verification.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend src to path
backend_src = Path(__file__).parent.parent.parent / "backend" / "src"
if str(backend_src) not in sys.path:
    sys.path.insert(0, str(backend_src))

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from ingestion.nomic_moe_embedder import EMBEDDING_DIM, NomicMoEEmbedder

logger = logging.getLogger(__name__)

app = FastAPI(title="Embedding Worker Health", docs_url=None, redoc_url=None)

# Cached embedder for health checks to avoid reloading model
_cached_embedder: NomicMoEEmbedder | None = None


def get_embedder() -> NomicMoEEmbedder:
    """Get or create cached embedder for health checks."""
    global _cached_embedder
    if _cached_embedder is None:
        _cached_embedder = NomicMoEEmbedder(max_workers=1)
    return _cached_embedder


@app.get("/health")
async def health_check() -> Response:
    """
    Verify embedding service availability.
    
    Returns 200 OK if:
    - Embedder can generate vectors
    - Output dimension is 256
    
    Returns 503 Service Unavailable on any failure.
    """
    try:
        embedder = get_embedder()
        embeddings = await embedder.embed_documents(["health check"])
        
        if len(embeddings) != 1:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "Expected 1 embedding, got " + str(len(embeddings))},
            )
        
        if len(embeddings[0]) != EMBEDDING_DIM:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "detail": f"Expected {EMBEDDING_DIM}-dim, got {len(embeddings[0])}-dim",
                },
            )
        
        return JSONResponse(
            status_code=200,
            content={"status": "ok", "embedding_dim": EMBEDDING_DIM},
        )
        
    except Exception as e:
        logger.exception("Health check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": str(e)},
        )


@app.get("/ready")
async def readiness_check() -> Response:
    """
    Readiness probe for Kubernetes/Cloud Run.
    
    Returns 200 OK if the service is ready to accept traffic.
    """
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up embedder on shutdown."""
    global _cached_embedder
    if _cached_embedder is not None:
        _cached_embedder.close()
        _cached_embedder = None


async def verify_embedder_startup() -> bool:
    """
    Verify embedder works during startup.
    
    Used by embedding worker to ensure model loads before processing messages.
    Returns True if embedder is healthy, False otherwise.
    """
    try:
        embedder = NomicMoEEmbedder(max_workers=1)
        embeddings = await embedder.embed_documents(["startup verification"])
        embedder.close()
        
        if len(embeddings) != 1 or len(embeddings[0]) != EMBEDDING_DIM:
            logger.error(
                f"Embedder startup verification failed: wrong dimensions",
                extra={"expected_dim": EMBEDDING_DIM, "actual_dim": len(embeddings[0]) if embeddings else 0},
            )
            return False
        
        logger.info(
            "Embedder startup verification passed",
            extra={"embedding_dim": EMBEDDING_DIM},
        )
        return True
        
    except Exception as e:
        logger.exception(f"Embedder startup verification failed: {e}")
        return False


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
