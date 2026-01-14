"""
Single entrypoint for IssueIndex worker jobs.

Usage:
    JOB_TYPE=gatherer python -m src     # Legacy: full pipeline (slow)
    JOB_TYPE=collector python -m src    # Job 1: Scout + Gather -> GCS
    JOB_TYPE=embedder python -m src     # Job 2: GCS -> Vertex AI Batch -> DB
    JOB_TYPE=janitor python -m src
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
    
    job_type = os.getenv("JOB_TYPE", "gatherer").lower()
    
    logger.info(
        f"Starting job",
        extra={"job_type": job_type, "job_id": job_id},
    )

    try:
        match job_type:
            case "gatherer":
                # Legacy full pipeline - kept for backwards compatibility
                from jobs.gatherer_job import run_gatherer_job
                result = await run_gatherer_job()
            
            case "collector":
                # Job 1: Scout + Gather issues -> Write to GCS -> Trigger embedder
                from jobs.collector_job import run_collector_job
                result = await run_collector_job()
            
            case "embedder":
                # Job 2: Read GCS -> Vertex AI Batch Prediction -> Persist to DB
                from jobs.embedder_job import run_embedder_job
                result = await run_embedder_job()
            
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

