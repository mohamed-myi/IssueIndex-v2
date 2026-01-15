"""
Single entrypoint for IssueIndex worker jobs.

Usage:
    JOB_TYPE=collector python -m src    # Job 1: Scout + Gather -> Pub/Sub
    JOB_TYPE=embedding python -m src    # Job 2: Pub/Sub -> Nomic MoE -> DB (long-running)
    JOB_TYPE=janitor python -m src      # Prune low-survival issues
    JOB_TYPE=reco_flush python -m src   # Flush recommendation events to analytics
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure src packages are importable
src_path = Path(__file__).parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from logging_config import setup_logging


async def main() -> None:
    job_id = setup_logging()
    logger = logging.getLogger(__name__)
    
    job_type = os.getenv("JOB_TYPE", "collector").lower()
    
    logger.info(
        f"Starting job",
        extra={"job_type": job_type, "job_id": job_id},
    )

    try:
        match job_type:
            case "collector":
                # Job 1: Scout + Gather issues -> Publish to Pub/Sub
                from jobs.collector_job import run_collector_job
                result = await run_collector_job()
            
            case "embedding":
                # Job 2: Pub/Sub -> Local Nomic MoE -> Persist to DB (long-running worker)
                # Start health server in background thread for Cloud Run health checks
                import threading
                import uvicorn
                from health import app as health_app
                
                def run_health_server():
                    uvicorn.run(health_app, host="0.0.0.0", port=8080, log_level="warning")
                
                health_thread = threading.Thread(target=run_health_server, daemon=True)
                health_thread.start()
                logger.info("Health server started on port 8080")
                
                from jobs.embedding_worker import run_embedding_worker
                await run_embedding_worker()
                result = {"status": "shutdown"}
            
            case "janitor":
                from jobs.janitor_job import run_janitor_job
                result = await run_janitor_job()

            case "reco_flush":
                from jobs.reco_flush_job import run_reco_flush_job
                result = await run_reco_flush_job()
            
            case _:
                raise ValueError(f"Unknown job type: {job_type}")

        logger.info(
            "Job completed successfully",
            extra={"job_type": job_type, "result": result},
        )

    except Exception as e:
        logger.exception(
            f"Job failed: {e}",
            extra={"job_type": job_type},
        )
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
