"""
Prune bottom 20% of issues by survival score.

Uses set-based DELETE with PERCENTILE_CONT for efficient execution.
Leverages ix_issue_survival_vacuum index.
"""

import logging
import sys
from pathlib import Path

# Add backend src to path
backend_src = Path(__file__).parent.parent.parent.parent / "backend" / "src"
if str(backend_src) not in sys.path:
    sys.path.insert(0, str(backend_src))

# Add packages to path
packages_db = Path(__file__).parent.parent.parent.parent.parent / "packages" / "database" / "src"
if str(packages_db) not in sys.path:
    sys.path.insert(0, str(packages_db))

from ingestion.janitor import Janitor
from session import async_session_factory

logger = logging.getLogger(__name__)


async def run_janitor_job() -> dict:
    """
    Prunes the bottom 20% of issues by survival_score.
    
    The survival_score is pre-calculated during ingestion,
    so no refresh step is needed. The DELETE query uses
    PERCENTILE_CONT to find the threshold.
    
    Returns stats dict with deleted_count and remaining_count.
    """
    logger.info("Starting Janitor: pruning low-survival issues")

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

    return {
        "deleted_count": result["deleted_count"],
        "remaining_count": result["remaining_count"],
    }

