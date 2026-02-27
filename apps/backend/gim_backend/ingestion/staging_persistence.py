

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from .content_hash import compute_content_hash

if TYPE_CHECKING:
    from .gatherer import IssueData

logger = logging.getLogger(__name__)
class StagingPersistence:

    def __init__(self, session: AsyncSession):
        self._session = session

    async def insert_pending_issues(self, issues: list[IssueData]) -> int:
        if not issues:
            return 0

        inserted = 0
        for issue in issues:
            content_hash = compute_content_hash(issue.node_id, issue.title, issue.body_text)

            result = await self._session.execute(
                text("""
                    INSERT INTO staging.pending_issue (
                        node_id, repo_id, title, body_text, labels,
                        issue_number, github_url, github_created_at, has_code, has_template_headers,
                        tech_stack_weight, q_score, state, content_hash,
                        status, attempts
                    )
                    VALUES (
                        :node_id, :repo_id, :title, :body_text, :labels,
                        :issue_number, :github_url, :github_created_at, :has_code, :has_template_headers,
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
                    "issue_number": issue.issue_number,
                    "github_url": issue.github_url,
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
                          p.issue_number, p.github_url, p.github_created_at,
                          p.has_code, p.has_template_headers,
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
                "issue_number": row.issue_number,
                "github_url": row.github_url,
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
        if not node_ids:
            return 0


        await self._session.execute(
            text("""
                UPDATE staging.pending_issue
                SET status = 'pending'
                WHERE node_id = ANY(:node_ids)
                AND attempts < :max_attempts
            """),
            {"node_ids": node_ids, "max_attempts": max_attempts},
        )


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
        result = await self._session.execute(
            text("""
                DELETE FROM staging.pending_issue
                WHERE status = 'completed'
                AND created_at < NOW() - make_interval(hours => :hours)
            """),
            {"hours": older_than_hours},
        )
        await self._session.commit()

        return result.rowcount

    async def get_pending_count(self) -> int:
        result = await self._session.execute(
            text("SELECT COUNT(*) FROM staging.pending_issue WHERE status = 'pending'")
        )
        return result.scalar() or 0
