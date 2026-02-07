"""
Prune bottom 20% of issues by survival score and clean up staging table.

Uses set-based DELETE with PERCENTILE_CONT for efficient execution.
Leverages ix_issue_survival_vacuum index.
"""

import logging

from gim_backend.ingestion.janitor import Janitor
from gim_backend.ingestion.staging_persistence import StagingPersistence
from gim_database.session import async_session_factory

logger = logging.getLogger(__name__)


async def run_janitor_job() -> dict:
    """
    Two-phase cleanup:
    1. Prune bottom 20% of ingestion.issue by survival_score
    2. Delete completed staging rows older than 24 hours

    Returns stats dict with deleted_count, remaining_count, and staging_cleaned.
    """
    logger.info("Starting Janitor: pruning low-survival issues")

    # Prune ingestion.issue table
    async with async_session_factory() as session:
        janitor = Janitor(session)
        result = await janitor.execute_pruning()

    logger.info(
        f"Janitor complete: deleted {result['deleted_count']} issues, "
        f"{result['remaining_count']} remaining",
        extra={
            "deleted_count": result["deleted_count"],
            "remaining_count": result["remaining_count"],
        },
    )

    # Clean up completed staging rows
    staging_cleaned = 0
    try:
        async with async_session_factory() as session:
            staging = StagingPersistence(session)
            staging_cleaned = await staging.cleanup_completed(older_than_hours=24)
        if staging_cleaned > 0:
            logger.info(
                f"Staging cleanup: removed {staging_cleaned} completed rows",
                extra={"staging_cleaned": staging_cleaned},
            )
    except Exception as e:
        logger.warning(f"Staging cleanup failed (non-fatal): {e}")

    return {
        "deleted_count": result["deleted_count"],
        "remaining_count": result["remaining_count"],
        "staging_cleaned": staging_cleaned,
    }
