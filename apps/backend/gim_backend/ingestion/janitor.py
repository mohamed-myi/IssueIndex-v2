

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text

from gim_backend.core.config import get_settings

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class Janitor:

    PRUNE_PERCENTILE: float = 0.2

    def __init__(self, session: AsyncSession):
        self._session = session
        self._min_count = get_settings().janitor_min_issues

    async def execute_pruning(self) -> dict:
        stats_before = await self._get_table_stats()

        if stats_before["row_count"] == 0 or stats_before["row_count"] < self._min_count:
            logger.info(f"Janitor: Skipping prune (row count {stats_before['row_count']} < {self._min_count})")
            return {
                "deleted_count": 0,
                "remaining_count": stats_before["row_count"],
            }

        deleted_count = await self._delete_bottom_percentile()

        stats_after = await self._get_table_stats()

        logger.info(
            f"Janitor: Pruned {deleted_count} issues ({stats_before['row_count']} -> {stats_after['row_count']})"
        )

        return {
            "deleted_count": deleted_count,
            "remaining_count": stats_after["row_count"],
        }

    async def _delete_bottom_percentile(self) -> int:
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
        query = text("SELECT COUNT(*) as cnt FROM ingestion.issue")
        result = await self._session.execute(query)
        row = result.fetchone()

        return {
            "row_count": row.cnt if row else 0,
        }
