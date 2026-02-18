"""Streaming issue harvester; yields AsyncIterator for constant memory"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .quality_gate import (
    QScoreComponents,
    compute_q_score,
    extract_components,
    passes_quality_gate,
)

if TYPE_CHECKING:
    from .github_client import GitHubGraphQLClient
    from .scout import RepositoryData

logger = logging.getLogger(__name__)

GATHERER_QUERY_PATH = Path(__file__).parent / "queries" / "gatherer.graphql"

BODY_TRUNCATE_LENGTH: int = 4000


@dataclass
class IssueData:
    node_id: str
    repo_id: str
    title: str
    body_text: str
    labels: list[str]
    github_created_at: datetime
    q_score: float
    q_components: QScoreComponents
    state: str
    issue_number: int | None = None
    github_url: str | None = None


class Gatherer:
    """Streams issues via AsyncIterator; filters by Q score >= 0,6"""

    PAGE_SIZE: int = 100
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: float = 2.0
    Q_SCORE_THRESHOLD: float = 0.3

    def __init__(
        self,
        client: GitHubGraphQLClient,
        max_issues_per_repo: int = 0,
        concurrency: int = 10,
    ):
        self._client = client
        self._max_issues_per_repo = max_issues_per_repo
        self._concurrency = concurrency
        self._query = self._load_query()

    def _load_query(self) -> str:
        if GATHERER_QUERY_PATH.exists():
            return GATHERER_QUERY_PATH.read_text()
        return self._inline_query()

    def _inline_query(self) -> str:
        return """
        query GathererIssues($owner: String!, $name: String!, $first: Int!, $after: String) {
          repository(owner: $owner, name: $name) {
            issues(first: $first, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
              pageInfo { hasNextPage endCursor }
              nodes {
                id number url title bodyText createdAt state
                labels(first: 10) { nodes { name } }
              }
            }
          }
          rateLimit { cost remaining resetAt nodeCount }
        }
        """

    async def harvest_issues(
        self,
        repos: list[RepositoryData],
    ) -> AsyncIterator[IssueData]:
        """Process repos concurrently with bounded concurrency, yield issues as they arrive.

        Uses asyncio.Semaphore to limit concurrent API requests and asyncio.Queue
        to stream issues back to the caller while workers process repos in parallel.
        """
        if not repos:
            return

        total_repos = len(repos)
        semaphore = asyncio.Semaphore(self._concurrency)
        # Bounded queue prevents unbounded memory growth if producer is slow
        # (Couples fetch rate to publish rate via backpressure)
        issue_queue: asyncio.Queue[IssueData | None] = asyncio.Queue(maxsize=100)
        start_time = time.monotonic()

        logger.info(
            f"Gatherer starting: {total_repos} repos with concurrency={self._concurrency}",
            extra={"total_repos": total_repos, "concurrency": self._concurrency},
        )

        # Start all worker tasks
        tasks = [
            asyncio.create_task(
                self._repo_worker(repo, issue_queue, semaphore, idx, total_repos, start_time)
            )
            for idx, repo in enumerate(repos)
        ]

        # Track completed workers via sentinel None values
        completed_workers = 0
        total_issues = 0

        # Yield issues from queue until all workers complete
        while completed_workers < total_repos:
            item = await issue_queue.get()
            if item is None:
                # Sentinel indicates a worker finished
                completed_workers += 1
                # Log progress every 10 repos for better visibility
                if completed_workers % 10 == 0 or completed_workers == total_repos:
                    elapsed = time.monotonic() - start_time
                    rate = completed_workers / elapsed if elapsed > 0 else 0
                    logger.info(
                        f"Gatherer progress: {completed_workers}/{total_repos} repos in {elapsed:.1f}s ({rate:.1f} repos/s), {total_issues} issues",
                        extra={
                            "repos_processed": completed_workers,
                            "total_repos": total_repos,
                            "issues_yielded": total_issues,
                            "elapsed_s": round(elapsed, 1),
                            "repos_per_second": round(rate, 1),
                        },
                    )
            else:
                total_issues += 1
                yield item

        # Ensure all tasks are complete and collect any exceptions for logging
        await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.monotonic() - start_time
        logger.info(
            f"Gatherer complete: {completed_workers} repos, {total_issues} issues in {elapsed:.1f}s",
            extra={
                "repos_processed": completed_workers,
                "total_issues": total_issues,
                "total_duration_s": round(elapsed, 1),
            },
        )

    async def _repo_worker(
        self,
        repo: RepositoryData,
        issue_queue: asyncio.Queue[IssueData | None],
        semaphore: asyncio.Semaphore,
        repo_idx: int,
        total_repos: int,
        job_start_time: float,
    ) -> int:
        """Process a single repo under semaphore control, push issues to queue.

        Returns the number of issues yielded from this repo.
        Sends None sentinel to queue when complete regardless of success or failure.
        """
        issue_count = 0
        acquire_start = time.monotonic()

        try:
            async with semaphore:
                wait_time = time.monotonic() - acquire_start
                # Log if worker waited more than 1 second for semaphore
                if wait_time > 1.0:
                    logger.debug(
                        f"Gatherer: Worker {repo_idx} waited {wait_time:.1f}s for semaphore",
                        extra={"repo": repo.full_name, "wait_time_s": round(wait_time, 1)},
                    )

                fetch_start = time.monotonic()
                async for issue in self._fetch_repo_issues_with_retry(repo):
                    await issue_queue.put(issue)
                    issue_count += 1
                fetch_elapsed = time.monotonic() - fetch_start

                if issue_count > 0:
                    logger.debug(
                        f"Gatherer: {repo.full_name} yielded {issue_count} issues in {fetch_elapsed:.1f}s",
                        extra={
                            "repo": repo.full_name,
                            "issue_count": issue_count,
                            "fetch_duration_s": round(fetch_elapsed, 1),
                        },
                    )
        except Exception as e:
            logger.warning(
                f"Gatherer: Skipping {repo.full_name} (repo {repo_idx + 1}/{total_repos}) after retries: {e}",
                extra={
                    "repo": repo.full_name,
                    "repos_processed": repo_idx + 1,
                    "error": str(e),
                },
            )
        finally:
            # Always send sentinel to signal this worker is done
            await issue_queue.put(None)

        return issue_count

    async def _fetch_repo_issues_with_retry(
        self,
        repo: RepositoryData,
    ) -> AsyncIterator[IssueData]:
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                async for issue in self._fetch_repo_issues(repo):
                    yield issue
                return  # Success? exit retry loop
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY_SECONDS * (attempt + 1)
                    logger.debug(
                        f"Gatherer: Retry {attempt + 1}/{self.MAX_RETRIES} "
                        f"for {repo.full_name} after {delay}s"
                    )
                    await asyncio.sleep(delay)

        if last_error:
            raise last_error

    async def _fetch_repo_issues(
        self,
        repo: RepositoryData,
    ) -> AsyncIterator[IssueData]:
        owner, name = repo.full_name.split("/", 1)
        cursor: str | None = None
        yielded_count = 0  # Track issues that pass Q-Score filter

        while True:
            data = await self._client.execute_query(
                self._query,
                variables={
                    "owner": owner,
                    "name": name,
                    "first": self.PAGE_SIZE,
                    "after": cursor,
                },
                estimated_cost=1,
            )

            repository = data.get("repository")
            if not repository:
                logger.warning(f"Gatherer: Repository not found: {repo.full_name}")
                break

            issues_data = repository.get("issues", {})
            nodes = issues_data.get("nodes", [])
            page_info = issues_data.get("pageInfo", {})

            for node in nodes:
                issue = self._parse_issue(node, repo)
                if issue and passes_quality_gate(issue.q_score, self.Q_SCORE_THRESHOLD):
                    yield issue
                    yielded_count += 1

                    # Check cap after yield to limit large repos
                    if self._max_issues_per_repo > 0 and yielded_count >= self._max_issues_per_repo:
                        logger.info(
                            f"Gatherer: Reached cap of {self._max_issues_per_repo} issues for {repo.full_name}",
                            extra={"repo": repo.full_name, "cap": self._max_issues_per_repo},
                        )
                        return  # Exit pagination early

            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

    def _parse_issue(self, node: dict, repo: RepositoryData) -> IssueData | None:
        if not node:
            return None

        node_id = node.get("id")
        issue_number_raw = node.get("number")
        github_url_raw = node.get("url")
        title = node.get("title", "")
        created_at_str = node.get("createdAt")

        if not node_id or not created_at_str:
            return None

        body = (node.get("bodyText") or "")[:BODY_TRUNCATE_LENGTH]
        issue_number = issue_number_raw if isinstance(issue_number_raw, int) and issue_number_raw > 0 else None
        github_url = github_url_raw.strip() if isinstance(github_url_raw, str) and github_url_raw.strip() else None

        labels_data = node.get("labels", {}).get("nodes", [])
        labels = [
            label.get("name")
            for label in labels_data
            if label and label.get("name")
        ]

        # GitHub returns state as OPEN or CLOSED; normalize to lowercase
        raw_state = node.get("state", "OPEN")
        state = raw_state.lower() if raw_state else "open"

        try:
            github_created_at = datetime.fromisoformat(
                created_at_str.replace("Z", "+00:00")
            )
        except (ValueError, AttributeError):
            logger.warning(f"Gatherer: Invalid createdAt for issue {node_id}")
            return None

        components = extract_components(title, body, repo.primary_language)
        q_score = compute_q_score(components)

        return IssueData(
            node_id=node_id,
            repo_id=repo.node_id,
            title=title,
            body_text=body,
            issue_number=issue_number,
            github_url=github_url,
            labels=labels,
            github_created_at=github_created_at,
            q_score=q_score,
            q_components=components,
            state=state,
        )
