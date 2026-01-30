"""Set-based pruning of lowest survival score issues"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text

from gim_backend.core.config import get_settings

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class Janitor:
    """
    Prunes the bottom 20% of issues by survival_score using a single
    indexed DELETE query. The survival_score is pre-calculated during
    ingestion (Phase 5), so no refresh step is needed.

    The DELETE leverages the ix_issue_survival_vacuum(survival_score, ingested_at)
    composite index for efficient execution.
    """

    PRUNE_PERCENTILE: float = 0.2

    def __init__(self, session: AsyncSession):
        self._session = session
        self._min_count = get_settings().janitor_min_issues

    async def execute_pruning(self) -> dict:
        """
        Deletes the bottom 20% of issues by survival_score.

        Returns dict with deleted_count and remaining_count for logging.
        """
        stats_before = await self._get_table_stats()

        if stats_before["row_count"] == 0 or stats_before["row_count"] < self._min_count:
            logger.info(
                f"Janitor: Skipping prune (row count {stats_before['row_count']} < {self._min_count})"
            )
            return {
                "deleted_count": 0,
                "remaining_count": stats_before["row_count"],
            }

        deleted_count = await self._delete_bottom_percentile()

        stats_after = await self._get_table_stats()

        logger.info(
            f"Janitor: Pruned {deleted_count} issues "
            f"({stats_before['row_count']} -> {stats_after['row_count']})"
        )

        return {
            "deleted_count": deleted_count,
            "remaining_count": stats_after["row_count"],
        }

    async def _delete_bottom_percentile(self) -> int:
        """
        Single indexed DELETE using PERCENTILE_CONT.

        The subquery calculates the 20th percentile threshold;
        all issues with survival_score below this threshold are deleted.
        """
        query = text("""
            DELETE FROM ingestion.issue
            WHERE survival_score < (
                SELECT PERCENTILE_CONT(:percentile) WITHIN GROUP (ORDER BY survival_score)
                FROM ingestion.issue
            )
        """)

        result = await self._session.execute(
            query,
            {"percentile": self.PRUNE_PERCENTILE},
        )
        await self._session.commit()

        return result.rowcount

    async def _get_table_stats(self) -> dict:
        """
        Returns row count for logging and verification.
        Uses COUNT(*) which is optimized in AlloyDB.
        """
        query = text("SELECT COUNT(*) as cnt FROM ingestion.issue")
        result = await self._session.execute(query)
        row = result.fetchone()

        return {
            "row_count": row.cnt if row else 0,
        }

