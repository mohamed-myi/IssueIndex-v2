"""Staging persistence layer for pending issue processing.

Provides atomic batch operations for the Collector → Embedder pipeline.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

if TYPE_CHECKING:
    from .gatherer import IssueData

logger = logging.getLogger(__name__)


def compute_content_hash(node_id: str, title: str, body_text: str) -> str:
    """Compute SHA256 hash of issue content for idempotency."""
    content = f"{node_id}:{title}:{body_text}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class StagingPersistence:
    """Persistence layer for staging.pending_issue table.

    Used by:
    - Collector: batch insert pending issues
    - Embedder: claim → process → complete/fail batch
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def insert_pending_issues(self, issues: list[IssueData]) -> int:
        """Insert issues into staging table, skipping duplicates.

        Uses ON CONFLICT DO NOTHING for idempotency.
        Returns count of inserted rows.
        """
        if not issues:
            return 0

        inserted = 0
        for issue in issues:
            content_hash = compute_content_hash(
                issue.node_id, issue.title, issue.body_text
            )

            result = await self._session.execute(
                text("""
                    INSERT INTO staging.pending_issue (
                        node_id, repo_id, title, body_text, labels,
                        github_created_at, has_code, has_template_headers,
                        tech_stack_weight, q_score, state, content_hash,
                        status, attempts
                    )
                    VALUES (
                        :node_id, :repo_id, :title, :body_text, :labels,
                        :github_created_at, :has_code, :has_template_headers,
                        :tech_stack_weight, :q_score, :state, :content_hash,
                        'pending', 0
                    )
                    ON CONFLICT (node_id) DO NOTHING
                """),
                {
                    "node_id": issue.node_id,
                    "repo_id": issue.repo_id,
                    "title": issue.title,
                    "body_text": issue.body_text,
                    "labels": issue.labels,
                    "github_created_at": issue.github_created_at,
                    "has_code": issue.q_components.has_code,
                    "has_template_headers": issue.q_components.has_headers,
                    "tech_stack_weight": issue.q_components.tech_weight,
                    "q_score": issue.q_score,
                    "state": issue.state,
                    "content_hash": content_hash,
                },
            )
            if result.rowcount > 0:
                inserted += 1

        await self._session.commit()

        logger.info(
            f"Inserted {inserted}/{len(issues)} pending issues (skipped duplicates)",
            extra={"inserted": inserted, "total": len(issues)},
        )
        return inserted

    async def claim_pending_batch(self, batch_size: int = 100) -> list[dict]:
        """Atomically claim a batch of pending issues for processing.

        Uses FOR UPDATE SKIP LOCKED to prevent race conditions.
        Updates status to 'processing' and increments attempts.
        Returns list of issue dicts with all columns.
        """
        result = await self._session.execute(
            text("""
                WITH claimed AS (
                    SELECT node_id
                    FROM staging.pending_issue
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT :batch_size
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE staging.pending_issue p
                SET status = 'processing', attempts = attempts + 1
                FROM claimed c
                WHERE p.node_id = c.node_id
                RETURNING p.node_id, p.repo_id, p.title, p.body_text, p.labels,
                          p.github_created_at, p.has_code, p.has_template_headers,
                          p.tech_stack_weight, p.q_score, p.state, p.content_hash,
                          p.attempts
            """),
            {"batch_size": batch_size},
        )

        await self._session.commit()

        rows = result.fetchall()
        issues = [
            {
                "node_id": row.node_id,
                "repo_id": row.repo_id,
                "title": row.title,
                "body_text": row.body_text,
                "labels": row.labels or [],
                "github_created_at": row.github_created_at,
                "has_code": row.has_code,
                "has_template_headers": row.has_template_headers,
                "tech_stack_weight": row.tech_stack_weight,
                "q_score": row.q_score,
                "state": row.state,
                "content_hash": row.content_hash,
                "attempts": row.attempts,
            }
            for row in rows
        ]

        logger.info(
            f"Claimed {len(issues)} pending issues for processing",
            extra={"claimed_count": len(issues)},
        )
        return issues

    async def mark_completed(self, node_ids: list[str]) -> int:
        """Mark issues as completed (will be cleaned up separately).

        Returns count of updated rows.
        """
        if not node_ids:
            return 0

        result = await self._session.execute(
            text("""
                UPDATE staging.pending_issue
                SET status = 'completed'
                WHERE node_id = ANY(:node_ids)
            """),
            {"node_ids": node_ids},
        )
        await self._session.commit()

        return result.rowcount

    async def mark_failed(self, node_ids: list[str], max_attempts: int = 3) -> int:
        """Mark issues as failed or reset to pending if retries remain.

        Issues with attempts < max_attempts are reset to 'pending'.
        Issues with attempts >= max_attempts are marked 'failed'.
        Returns count of issues marked as permanently failed.
        """
        if not node_ids:
            return 0

        # Reset retryable issues to pending
        await self._session.execute(
            text("""
                UPDATE staging.pending_issue
                SET status = 'pending'
                WHERE node_id = ANY(:node_ids)
                AND attempts < :max_attempts
            """),
            {"node_ids": node_ids, "max_attempts": max_attempts},
        )

        # Mark exhausted issues as failed
        result = await self._session.execute(
            text("""
                UPDATE staging.pending_issue
                SET status = 'failed'
                WHERE node_id = ANY(:node_ids)
                AND attempts >= :max_attempts
            """),
            {"node_ids": node_ids, "max_attempts": max_attempts},
        )
        await self._session.commit()

        return result.rowcount

    async def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """Delete completed issues older than specified hours.

        Returns count of deleted rows.
        """
        result = await self._session.execute(
            text("""
                DELETE FROM staging.pending_issue
                WHERE status = 'completed'
                AND created_at < NOW() - INTERVAL ':hours hours'
            """),
            {"hours": older_than_hours},
        )
        await self._session.commit()

        return result.rowcount

    async def get_pending_count(self) -> int:
        """Get count of pending issues."""
        result = await self._session.execute(
            text("SELECT COUNT(*) FROM staging.pending_issue WHERE status = 'pending'")
        )
        return result.scalar() or 0
