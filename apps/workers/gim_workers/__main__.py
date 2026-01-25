"""
Single entrypoint for IssueIndex worker jobs.

Usage:
    JOB_TYPE=collector python -m gim_workers    # Job 1: Scout + Gather -> Pub/Sub
    JOB_TYPE=embedding python -m gim_workers    # Job 2: Pub/Sub -> Nomic MoE -> DB (long-running)
    JOB_TYPE=janitor python -m gim_workers      # Prune low-survival issues
    JOB_TYPE=reco_flush python -m gim_workers   # Flush recommendation events to analytics

Health check runs on port 8080 for embedding worker (via asyncio, not threading).
"""

import asyncio
import logging
import os
import signal
import sys

import uvicorn

from gim_workers.logging_config import setup_logging
from gim_backend.ingestion.nomic_moe_embedder import NomicMoEEmbedder


class GracefulShutdown:
    """Manages graceful shutdown for both health server and worker."""
    
    def __init__(self):
        self._shutdown_event = asyncio.Event()
        self._server: uvicorn.Server | None = None
    
    def register_server(self, server: uvicorn.Server) -> None:
        self._server = server
    
    def signal_handler(self, signum: int) -> None:
        logger = logging.getLogger(__name__)
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self._shutdown_event.set()
        if self._server:
            self._server.should_exit = True
    
    @property
    def shutdown_event(self) -> asyncio.Event:
        return self._shutdown_event





async def run_health_server(shutdown: GracefulShutdown, embedder: NomicMoEEmbedder | None = None) -> None:
    """Run uvicorn health server as an asyncio task."""
    from gim_workers.health import app as health_app
    
    # Inject singleton embedder if available
    if embedder:
        health_app.state.embedder = embedder
    
    config = uvicorn.Config(
        app=health_app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        log_level="warning",
    )
    server = uvicorn.Server(config)
    shutdown.register_server(server)
    
    logger = logging.getLogger(__name__)
    logger.info("Health server starting on port 8080")
    
    await server.serve()


async def run_worker_task(
    job_type: str, 
    shutdown: GracefulShutdown, 
    embedder: NomicMoEEmbedder | None = None
) -> dict:
    """Run the specified worker job."""
    
    match job_type:
        case "collector":
            from gim_workers.jobs.collector_job import run_collector_job
            return await run_collector_job()
        
        case "embedding":
            if not embedder:
                raise ValueError("Embedding worker requires embedder instance")
            from gim_workers.jobs.embedding_worker import run_embedding_worker
            await run_embedding_worker(embedder)
            return {"status": "shutdown"}
        
        case "janitor":
            from gim_workers.jobs.janitor_job import run_janitor_job
            return await run_janitor_job()

        case "reco_flush":
            from gim_workers.jobs.reco_flush_job import run_reco_flush_job
            return await run_reco_flush_job()
        
        case _:
            raise ValueError(f"Unknown job type: {job_type}")


async def main() -> None:
    job_id = setup_logging()
    logger = logging.getLogger(__name__)
    
    job_type = os.getenv("JOB_TYPE", "collector").lower()
    
    logger.info(
        "Starting job",
        extra={"job_type": job_type, "job_id": job_id},
    )
    
    shutdown = GracefulShutdown()
    embedder: NomicMoEEmbedder | None = None
    
    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: shutdown.signal_handler(s))

    try:
        if job_type == "embedding":
            # Initialize singleton embedder model (shared state)
            # Large size (~1GB), so do it once here
            logger.info("Initializing shared NomicMoEEmbedder")
            embedder = NomicMoEEmbedder(max_workers=1)
            
            # Embedding worker needs health server running alongside
            async with asyncio.TaskGroup() as tg:
                tg.create_task(run_health_server(shutdown, embedder))
                tg.create_task(run_worker_task(job_type, shutdown, embedder))
            result = {"status": "shutdown"}
        else:
            # Other jobs don't need health server (short-running Cloud Run Jobs)
            result = await run_worker_task(job_type, shutdown)

        logger.info(
            "Job completed successfully",
            extra={"job_type": job_type, "result": result},
        )

    except* Exception as eg:
        # Handle TaskGroup exception group
        for exc in eg.exceptions:
            logger.exception(
                f"Job failed: {exc}",
                extra={"job_type": job_type},
            )
        sys.exit(1)
        
    finally:
        # Clean up shared resources
        if embedder:
            logger.info("Cleaning up shared embedder")
            embedder.close()


if __name__ == "__main__":
    asyncio.run(main())
