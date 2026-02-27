"""Schema compatibility probes for search-related tables."""

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession


async def _issue_has_github_url_column(db: AsyncSession) -> bool:
    result = await db.exec(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'ingestion'
                  AND table_name = 'issue'
                  AND column_name = 'github_url'
            ) AS has_column
            """
        )
    )
    row = result.one()
    return bool(row[0])


__all__ = ["_issue_has_github_url_column"]
