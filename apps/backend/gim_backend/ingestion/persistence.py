"""Streaming persistence layer for ingested issues"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from .survival_score import calculate_survival_score, days_since

if TYPE_CHECKING:
    from .embeddings import EmbeddedIssue
    from .gatherer import IssueData
    from .scout import RepositoryData

logger = logging.getLogger(__name__)


def compute_content_hash(issue: IssueData) -> str:
    """
    Compute SHA256 hash of issue content for idempotency.

    Hash includes node_id, title, and body_text to detect content changes.
    Same content produces same hash; updated content produces new hash.
    """
    content = f"{issue.node_id}:{issue.title}:{issue.body_text}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class StreamingPersistence:
    """Consumes embedded issue stream and writes in batches via UPSERT"""

    BATCH_SIZE: int = 50

    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_repositories(self, repos: list[RepositoryData]) -> int:
        """
        Batch UPSERT repositories before issue ingestion.
        Returns count of upserted rows.
        """
        if not repos:
            return 0

        now = datetime.now(UTC)
        insert_or_update_by_node_id = text("""
            INSERT INTO ingestion.repository
                (node_id, full_name, primary_language, issue_velocity_week,
                 stargazer_count, topics, last_scraped_at)
            VALUES
                (:node_id, :full_name, :primary_language, :issue_velocity_week,
                 :stargazer_count, :topics, :last_scraped_at)
            ON CONFLICT (node_id) DO UPDATE SET
                full_name = EXCLUDED.full_name,
                primary_language = EXCLUDED.primary_language,
                issue_velocity_week = EXCLUDED.issue_velocity_week,
                stargazer_count = EXCLUDED.stargazer_count,
                topics = EXCLUDED.topics,
                last_scraped_at = EXCLUDED.last_scraped_at
        """)

        update_by_full_name = text("""
            UPDATE ingestion.repository SET
                node_id = :node_id,
                primary_language = :primary_language,
                issue_velocity_week = :issue_velocity_week,
                stargazer_count = :stargazer_count,
                topics = :topics,
                last_scraped_at = :last_scraped_at
            WHERE full_name = :full_name
        """)

        # Commit per repo so a single constraint violation does not leave the
        # entire session transaction aborted.
        for repo in repos:
            params = {
                "node_id": repo.node_id,
                "full_name": repo.full_name,
                "primary_language": repo.primary_language,
                "issue_velocity_week": repo.issue_count_open,
                "stargazer_count": repo.stargazer_count,
                "topics": repo.topics,
                "last_scraped_at": now,
            }

            try:
                await self._session.exec(insert_or_update_by_node_id, params=params)
                await self._session.commit()
            except IntegrityError:
                await self._session.rollback()
                result = await self._session.exec(update_by_full_name, params=params)
                await self._session.commit()
                if (result.rowcount or 0) == 0:
                    raise

        logger.debug(f"Upserted {len(repos)} repositories")
        return len(repos)

    async def persist_stream(
        self,
        embedded_issues: AsyncIterator[EmbeddedIssue],
    ) -> int:
        """
        Consumes stream, calculates survival_score, UPSERTs in batches.
        Returns total issues persisted.
        """
        batch: list[EmbeddedIssue] = []
        total = 0
        batch_number = 0

        async for item in embedded_issues:
            batch.append(item)

            if len(batch) >= self.BATCH_SIZE:
                batch_number += 1
                try:
                    await self._upsert_batch(batch)
                    total += len(batch)
                    # Log progress every 5 batches (250 issues) to avoid log spam
                    if batch_number % 5 == 0:
                        logger.info(
                            f"Persistence progress: {total} issues persisted (batch {batch_number})",
                            extra={"issues_persisted": total, "batch_number": batch_number},
                        )
                except Exception as e:
                    logger.error(
                        f"Database upsert failed at batch {batch_number} (total {total} issues so far): {e}",
                        extra={"batch_number": batch_number, "issues_so_far": total, "error": str(e)},
                    )
                    raise
                batch.clear()

        if batch:
            batch_number += 1
            try:
                await self._upsert_batch(batch)
                total += len(batch)
            except Exception as e:
                logger.error(
                    f"Database upsert failed at final batch {batch_number} (total {total} issues so far): {e}",
                    extra={"batch_number": batch_number, "issues_so_far": total, "error": str(e)},
                )
                raise

        logger.info(
            f"Persisted {total} issues to database in {batch_number} batches",
            extra={"issues_persisted": total, "total_batches": batch_number},
        )
        return total

    async def _upsert_batch(self, batch: list[EmbeddedIssue]) -> None:
        """UPSERT batch with survival_score calculation and content_hash for idempotency"""
        if not batch:
            return

        values_list = []
        params = {}

        for i, item in enumerate(batch):
            issue = item.issue
            days_old = days_since(issue.github_created_at)
            survival = calculate_survival_score(issue.q_score, days_old)
            content_hash = compute_content_hash(issue)

            values_list.append(
                f"(:node_id_{i}, :repo_id_{i}, :has_code_{i}, :has_template_headers_{i}, "
                f":tech_stack_weight_{i}, :q_score_{i}, :survival_score_{i}, :title_{i}, "
                f":body_text_{i}, :issue_number_{i}, :github_url_{i}, :labels_{i}, "
                f"CAST(:embedding_{i} AS vector), :content_hash_{i}, "
                f":github_created_at_{i}, :state_{i})"
            )

            params[f"node_id_{i}"] = issue.node_id
            params[f"repo_id_{i}"] = issue.repo_id
            params[f"has_code_{i}"] = issue.q_components.has_code
            params[f"has_template_headers_{i}"] = issue.q_components.has_headers
            params[f"tech_stack_weight_{i}"] = issue.q_components.tech_weight
            params[f"q_score_{i}"] = issue.q_score
            params[f"survival_score_{i}"] = survival
            params[f"title_{i}"] = issue.title
            params[f"body_text_{i}"] = issue.body_text
            params[f"issue_number_{i}"] = issue.issue_number
            params[f"github_url_{i}"] = issue.github_url
            params[f"labels_{i}"] = issue.labels
            params[f"embedding_{i}"] = str(item.embedding)
            params[f"content_hash_{i}"] = content_hash
            params[f"github_created_at_{i}"] = issue.github_created_at
            params[f"state_{i}"] = issue.state

        values_sql = ", ".join(values_list)

        query = text(f"""
            INSERT INTO ingestion.issue
                (node_id, repo_id, has_code, has_template_headers, tech_stack_weight,
                 q_score, survival_score, title, body_text, issue_number, github_url,
                 labels, embedding, content_hash,
                 github_created_at, state)
            VALUES {values_sql}
            ON CONFLICT (node_id) DO UPDATE SET
                repo_id = EXCLUDED.repo_id,
                has_code = EXCLUDED.has_code,
                has_template_headers = EXCLUDED.has_template_headers,
                tech_stack_weight = EXCLUDED.tech_stack_weight,
                q_score = EXCLUDED.q_score,
                survival_score = EXCLUDED.survival_score,
                title = EXCLUDED.title,
                body_text = EXCLUDED.body_text,
                issue_number = EXCLUDED.issue_number,
                github_url = EXCLUDED.github_url,
                labels = EXCLUDED.labels,
                embedding = EXCLUDED.embedding,
                content_hash = EXCLUDED.content_hash,
                github_created_at = EXCLUDED.github_created_at,
                state = EXCLUDED.state
        """)

        await self._session.exec(query, params=params)
        await self._session.commit()

        logger.debug(f"Upserted batch of {len(batch)} issues")
