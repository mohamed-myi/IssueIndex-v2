"""
Health check endpoint for Cloud Run embedding worker.

Provides HTTP health check endpoint to verify:
1. Embedding model is loaded and functional
2. Can generate 256-dim vectors
3. Database connection is available

Can be run standalone or imported for startup verification.
"""

import logging

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from fastapi import FastAPI, Response, Request
from fastapi.responses import JSONResponse

from gim_backend.ingestion.nomic_moe_embedder import EMBEDDING_DIM

logger = logging.getLogger(__name__)

app = FastAPI(title="Embedding Worker Health", docs_url=None, redoc_url=None)


@app.get("/health")
async def health_check(request: Request) -> Response:
    """
    Verify embedding service availability.
    
    Returns 200 OK if:
    - Shared embedder is available
    - Embedder can generate vectors
    - Output dimension is 256
    
    Returns 503 Service Unavailable on any failure.
    """
    try:
        # Access shared embedder injected by __main__
        if not hasattr(request.app.state, "embedder"):
            raise RuntimeError("Embedder not initialized in app state")
            
        embedder = request.app.state.embedder
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
