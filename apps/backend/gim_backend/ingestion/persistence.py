

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from .content_hash import compute_content_hash
from .embeddings import EMBEDDING_DIM
from .survival_score import calculate_survival_score, days_since

if TYPE_CHECKING:
    from .embeddings import EmbeddedIssue
    from .scout import RepositoryData

logger = logging.getLogger(__name__)


def _assert_embedding_dim(embedding: list[float], expected_dim: int, *, issue_id: str | None = None) -> None:
    if len(embedding) != expected_dim:
        issue_part = f" for {issue_id}" if issue_id else ""
        raise ValueError(
            f"Issue embedding dimension mismatch{issue_part}: "
            f"expected {expected_dim}, got {len(embedding)}"
        )


class StreamingPersistence:

    BATCH_SIZE: int = 50

    def __init__(self, session: AsyncSession):
        self._session = session

    async def upsert_repositories(self, repos: list[RepositoryData]) -> int:
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

    async def upsert_staged_issue(self, issue: dict[str, Any], embedding: list[float]) -> None:
        _assert_embedding_dim(embedding, EMBEDDING_DIM, issue_id=str(issue.get("node_id")))

        github_created_at = issue.get("github_created_at")
        if isinstance(github_created_at, str):
            dt = datetime.fromisoformat(github_created_at.replace("Z", "+00:00"))
            github_created_at = dt.astimezone(UTC).replace(tzinfo=None)
        elif isinstance(github_created_at, datetime):
            github_created_at = github_created_at.replace(tzinfo=None)

        q_score = float(issue.get("q_score") or 0.0)
        days_old = days_since(github_created_at)
        survival = calculate_survival_score(q_score, days_old)

        await self._session.exec(
            text("""
                INSERT INTO ingestion.issue (
                    node_id, repo_id, has_code, has_template_headers,
                    tech_stack_weight, q_score, survival_score, title,
                    body_text, labels, embedding, content_hash, state,
                    github_created_at
                )
                VALUES (
                    :node_id, :repo_id, :has_code, :has_template_headers,
                    :tech_stack_weight, :q_score, :survival_score, :title,
                    :body_text, :labels, CAST(:embedding AS vector), :content_hash,
                    :state, :github_created_at
                )
                ON CONFLICT (node_id) DO UPDATE SET
                    repo_id = EXCLUDED.repo_id,
                    has_code = EXCLUDED.has_code,
                    has_template_headers = EXCLUDED.has_template_headers,
                    tech_stack_weight = EXCLUDED.tech_stack_weight,
                    q_score = EXCLUDED.q_score,
                    survival_score = EXCLUDED.survival_score,
                    title = EXCLUDED.title,
                    body_text = EXCLUDED.body_text,
                    labels = EXCLUDED.labels,
                    embedding = EXCLUDED.embedding,
                    content_hash = EXCLUDED.content_hash,
                    state = EXCLUDED.state,
                    github_created_at = EXCLUDED.github_created_at
            """),
            params={
                "node_id": issue["node_id"],
                "repo_id": issue["repo_id"],
                "has_code": bool(issue.get("has_code", False)),
                "has_template_headers": bool(issue.get("has_template_headers", False)),
                "tech_stack_weight": float(issue.get("tech_stack_weight") or 0.0),
                "q_score": q_score,
                "survival_score": survival,
                "title": issue["title"],
                "body_text": issue["body_text"],
                "labels": issue.get("labels") or [],
                "embedding": str(embedding),
                "content_hash": issue["content_hash"],
                "state": issue.get("state") or "open",
                "github_created_at": github_created_at,
            },
        )

    async def _upsert_batch(self, batch: list[EmbeddedIssue]) -> None:
        if not batch:
            return

        values_list = []
        params = {}

        for i, item in enumerate(batch):
            issue = item.issue
            _assert_embedding_dim(item.embedding, EMBEDDING_DIM, issue_id=issue.node_id)
            days_old = days_since(issue.github_created_at)
            survival = calculate_survival_score(issue.q_score, days_old)
            content_hash = compute_content_hash(issue.node_id, issue.title, issue.body_text)

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
