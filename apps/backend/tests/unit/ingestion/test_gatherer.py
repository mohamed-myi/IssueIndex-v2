"""Unit tests for Gatherer streaming issue harvester"""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.ingestion.gatherer import (
    BODY_TRUNCATE_LENGTH,
    Gatherer,
    IssueData,
)
from src.ingestion.quality_gate import QScoreComponents
from src.ingestion.scout import RepositoryData


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.execute_query = AsyncMock()
    return client


@pytest.fixture
def gatherer(mock_client):
    return Gatherer(client=mock_client)


@pytest.fixture
def sample_repo():
    return RepositoryData(
        node_id="R_kgDOHDq123",
        full_name="facebook/react",
        primary_language="TypeScript",
        stargazer_count=200000,
        issue_count_open=500,
        topics=["react", "javascript"],
    )


def make_issue_node(
    node_id: str = "I_kwDOHDq123",
    title: str = "Bug report",
    body: str = "## Description\n```typescript\nthrow new TypeError()\n```",
    created_at: str = "2024-01-15T12:00:00Z",
    labels: list[str] | None = None,
    state: str = "OPEN",
):
    return {
        "id": node_id,
        "title": title,
        "bodyText": body,
        "createdAt": created_at,
        "state": state,
        "labels": {
            "nodes": [{"name": lbl} for lbl in (labels or [])]
        },
    }


class TestParseIssue:

    def test_parses_complete_node(self, gatherer, sample_repo):
        node = make_issue_node(
            node_id="I_123",
            title="TypeError in component",
            body="## Description\n```typescript\ncode\n```",
            labels=["bug", "high-priority"],
        )

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert issue.node_id == "I_123"
        assert issue.repo_id == sample_repo.node_id
        assert issue.title == "TypeError in component"
        assert "bug" in issue.labels
        assert issue.q_score >= 0.0

    def test_truncates_body_at_limit(self, gatherer, sample_repo):
        long_body = "x" * 10000
        node = make_issue_node(body=long_body)

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert len(issue.body_text) == BODY_TRUNCATE_LENGTH

    def test_handles_empty_body(self, gatherer, sample_repo):
        node = make_issue_node(body="")

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert issue.body_text == ""

    def test_handles_none_body(self, gatherer, sample_repo):
        node = make_issue_node()
        node["bodyText"] = None

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert issue.body_text == ""

    def test_parses_created_at_with_z_suffix(self, gatherer, sample_repo):
        node = make_issue_node(created_at="2024-01-15T12:00:00Z")

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert issue.github_created_at.year == 2024
        assert issue.github_created_at.month == 1
        assert issue.github_created_at.day == 15

    def test_parses_labels(self, gatherer, sample_repo):
        node = make_issue_node(labels=["bug", "help wanted", "good first issue"])

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert len(issue.labels) == 3
        assert "bug" in issue.labels

    def test_handles_empty_labels(self, gatherer, sample_repo):
        node = make_issue_node(labels=[])

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert issue.labels == []

    def test_handles_missing_labels(self, gatherer, sample_repo):
        node = make_issue_node()
        del node["labels"]

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert issue.labels == []

    def test_returns_none_for_missing_id(self, gatherer, sample_repo):
        node = make_issue_node()
        del node["id"]

        issue = gatherer._parse_issue(node, sample_repo)
        assert issue is None

    def test_returns_none_for_missing_created_at(self, gatherer, sample_repo):
        node = make_issue_node()
        del node["createdAt"]

        issue = gatherer._parse_issue(node, sample_repo)
        assert issue is None

    def test_returns_none_for_invalid_created_at(self, gatherer, sample_repo):
        node = make_issue_node(created_at="not-a-date")

        issue = gatherer._parse_issue(node, sample_repo)
        assert issue is None

    def test_returns_none_for_empty_node(self, gatherer, sample_repo):
        issue = gatherer._parse_issue({}, sample_repo)
        assert issue is None

    def test_returns_none_for_none_node(self, gatherer, sample_repo):
        issue = gatherer._parse_issue(None, sample_repo)
        assert issue is None

    def test_calculates_q_score(self, gatherer, sample_repo):
        node = make_issue_node(
            title="TypeError in async function",
            body="## Description\n```typescript\nawait Promise.resolve()\n```",
        )

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert issue.q_score > 0.6
        assert isinstance(issue.q_components, QScoreComponents)

    def test_parses_open_state(self, gatherer, sample_repo):
        node = make_issue_node(state="OPEN")

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert issue.state == "open"

    def test_parses_closed_state(self, gatherer, sample_repo):
        node = make_issue_node(state="CLOSED")

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert issue.state == "closed"

    def test_defaults_to_open_when_state_missing(self, gatherer, sample_repo):
        node = make_issue_node()
        del node["state"]

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert issue.state == "open"

    def test_defaults_to_open_when_state_none(self, gatherer, sample_repo):
        node = make_issue_node()
        node["state"] = None

        issue = gatherer._parse_issue(node, sample_repo)

        assert issue is not None
        assert issue.state == "open"


class TestFetchRepoIssues:
    async def test_fetches_single_page(self, mock_client, gatherer, sample_repo):
        mock_client.execute_query.return_value = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        make_issue_node(f"I_{i}", body="## Description\n```code\n```")
                        for i in range(5)
                    ],
                }
            }
        }

        issues = [i async for i in gatherer._fetch_repo_issues(sample_repo)]

        assert len(issues) >= 1
        mock_client.execute_query.assert_called_once()

    async def test_paginates_multiple_pages(self, mock_client, gatherer, sample_repo):
        page1 = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor_1"},
                    "nodes": [
                        make_issue_node(f"I_{i}", body="## Description\n```code\n```")
                        for i in range(3)
                    ],
                }
            }
        }
        page2 = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        make_issue_node(f"I_{i+10}", body="## Description\n```code\n```")
                        for i in range(2)
                    ],
                }
            }
        }

        mock_client.execute_query.side_effect = [page1, page2]

        _ = [i async for i in gatherer._fetch_repo_issues(sample_repo)]

        assert mock_client.execute_query.call_count == 2

    async def test_handles_missing_repository(self, mock_client, gatherer, sample_repo):
        mock_client.execute_query.return_value = {"repository": None}

        issues = [i async for i in gatherer._fetch_repo_issues(sample_repo)]

        assert len(issues) == 0

    async def test_filters_low_q_score_issues(self, mock_client, gatherer, sample_repo):
        mock_client.execute_query.return_value = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        make_issue_node("I_high", body="## Description\n```code\n```"),
                        make_issue_node("I_low", title="bug", body="just a bug"),
                    ],
                }
            }
        }

        issues = [i async for i in gatherer._fetch_repo_issues(sample_repo)]

        high_quality = [i for i in issues if i.node_id == "I_high"]
        low_quality = [i for i in issues if i.node_id == "I_low"]

        assert len(high_quality) == 1
        assert len(low_quality) == 0


class TestRetryLogic:

    async def test_retries_on_failure(self, mock_client, gatherer, sample_repo):
        call_count = [0]

        async def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("API Error")
            return {
                "repository": {
                    "issues": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [make_issue_node("I_1", body="## Description\n```code\n```")],
                    }
                }
            }

        mock_client.execute_query.side_effect = mock_execute

        with patch("asyncio.sleep", new_callable=AsyncMock):
            issues = [i async for i in gatherer._fetch_repo_issues_with_retry(sample_repo)]

        assert call_count[0] == 3
        assert len(issues) >= 1

    async def test_raises_after_max_retries(self, mock_client, gatherer, sample_repo):
        mock_client.execute_query.side_effect = Exception("Persistent failure")

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(Exception, match="Persistent failure"):
                _ = [i async for i in gatherer._fetch_repo_issues_with_retry(sample_repo)]

    async def test_exponential_backoff(self, mock_client, gatherer, sample_repo):
        mock_client.execute_query.side_effect = Exception("API Error")
        sleep_calls = []

        async def capture_sleep(seconds):
            sleep_calls.append(seconds)

        with patch("asyncio.sleep", side_effect=capture_sleep):
            try:
                _ = [i async for i in gatherer._fetch_repo_issues_with_retry(sample_repo)]
            except Exception:
                pass

        assert sleep_calls == [2.0, 4.0]


class TestHarvestIssues:

    async def test_harvests_from_multiple_repos(self, mock_client, gatherer):
        repos = [
            RepositoryData(
                node_id=f"R_{i}",
                full_name=f"owner/repo{i}",
                primary_language="Python",
                stargazer_count=1000,
                issue_count_open=50,
                topics=[],
            )
            for i in range(3)
        ]

        mock_client.execute_query.return_value = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [make_issue_node("I_1", body="## Description\n```code\n```")],
                }
            }
        }

        _ = [i async for i in gatherer.harvest_issues(repos)]

        assert mock_client.execute_query.call_count == 3

    async def test_continues_on_repo_failure(self, mock_client, gatherer):
        repos = [
            RepositoryData(
                node_id=f"R_{i}",
                full_name=f"owner/repo{i}",
                primary_language="Python",
                stargazer_count=1000,
                issue_count_open=50,
                topics=[],
            )
            for i in range(3)
        ]

        call_count = [0]

        async def mock_execute(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 3:  # First repo fails all retries
                raise Exception("API Error")
            return {
                "repository": {
                    "issues": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [make_issue_node("I_1", body="## Description\n```code\n```")],
                    }
                }
            }

        mock_client.execute_query.side_effect = mock_execute

        with patch("asyncio.sleep", new_callable=AsyncMock):
            issues = [i async for i in gatherer.harvest_issues(repos)]

        assert len(issues) >= 1


class TestIssueData:

    def test_dataclass_fields(self):
        components = QScoreComponents(
            has_code=True,
            has_headers=True,
            tech_weight=0.5,
            is_junk=False,
        )

        issue = IssueData(
            node_id="I_123",
            repo_id="R_456",
            title="Bug report",
            body_text="Description",
            labels=["bug"],
            github_created_at=datetime.now(UTC),
            q_score=0.75,
            q_components=components,
            state="open",
        )

        assert issue.node_id == "I_123"
        assert issue.repo_id == "R_456"
        assert issue.q_score == 0.75
        assert issue.q_components.has_code is True
        assert issue.state == "open"


class TestBodyTruncation:
    def test_truncate_length_is_4000(self):
        assert BODY_TRUNCATE_LENGTH == 4000


class TestIssueCapping:
    """Tests for PERF-002: max_issues_per_repo capping functionality"""

    async def test_stops_pagination_at_cap(self, mock_client, sample_repo):
        # Arrange - create gatherer with cap of 3 issues
        gatherer = Gatherer(client=mock_client, max_issues_per_repo=3)

        # Two pages of high quality issues that would all pass Q-Score
        page1 = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor_1"},
                    "nodes": [
                        make_issue_node(f"I_{i}", body="## Description\n```code\n```")
                        for i in range(2)
                    ],
                }
            }
        }
        page2 = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor_2"},
                    "nodes": [
                        make_issue_node(f"I_{i+10}", body="## Description\n```code\n```")
                        for i in range(2)
                    ],
                }
            }
        }
        page3 = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        make_issue_node(f"I_{i+20}", body="## Description\n```code\n```")
                        for i in range(2)
                    ],
                }
            }
        }

        mock_client.execute_query.side_effect = [page1, page2, page3]

        # Act
        issues = [i async for i in gatherer._fetch_repo_issues(sample_repo)]

        # Assert - should stop after cap of 3, not fetch all 6
        assert len(issues) == 3
        # Should have stopped after 2 pages since cap reached during page 2
        assert mock_client.execute_query.call_count == 2

    async def test_cap_counts_only_yielded_issues(self, mock_client, sample_repo):
        # Arrange - cap of 2, but include low Q-Score issues that wont count
        gatherer = Gatherer(client=mock_client, max_issues_per_repo=2)

        # High quality body with code blocks and headers passes Q-Score threshold of 0.6
        high_quality_body = "## Description\n```typescript\nthrow new TypeError()\n```"
        # Low quality body without code or headers fails Q-Score threshold
        low_quality_body = "this is broken please fix"

        # Mix of high and low quality issues
        mock_client.execute_query.return_value = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        # High quality - will pass Q-Score and count toward cap
                        make_issue_node("I_high_1", body=high_quality_body),
                        # Low quality - will NOT pass Q-Score threshold
                        make_issue_node("I_low_1", title="bug", body=low_quality_body),
                        make_issue_node("I_low_2", title="help", body=low_quality_body),
                        # High quality - will pass and count toward cap
                        make_issue_node("I_high_2", body=high_quality_body),
                        # This would pass but cap should already be reached
                        make_issue_node("I_high_3", body=high_quality_body),
                    ],
                }
            }
        }

        # Act
        issues = [i async for i in gatherer._fetch_repo_issues(sample_repo)]

        # Assert - should only get 2 high quality issues due to cap
        assert len(issues) == 2
        assert all(i.node_id.startswith("I_high") for i in issues)

    async def test_zero_cap_disables_capping(self, mock_client, sample_repo):
        # Arrange - cap of 0 means no limit
        gatherer = Gatherer(client=mock_client, max_issues_per_repo=0)

        # Multiple pages of issues
        page1 = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor_1"},
                    "nodes": [
                        make_issue_node(f"I_{i}", body="## Description\n```code\n```")
                        for i in range(3)
                    ],
                }
            }
        }
        page2 = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        make_issue_node(f"I_{i+10}", body="## Description\n```code\n```")
                        for i in range(3)
                    ],
                }
            }
        }

        mock_client.execute_query.side_effect = [page1, page2]

        # Act
        issues = [i async for i in gatherer._fetch_repo_issues(sample_repo)]

        # Assert - should fetch all issues from both pages
        assert len(issues) == 6
        assert mock_client.execute_query.call_count == 2

    async def test_repos_with_fewer_issues_fully_processed(self, mock_client, sample_repo):
        # Arrange - cap of 100, but repo only has 5 issues
        gatherer = Gatherer(client=mock_client, max_issues_per_repo=100)

        mock_client.execute_query.return_value = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        make_issue_node(f"I_{i}", body="## Description\n```code\n```")
                        for i in range(5)
                    ],
                }
            }
        }

        # Act
        issues = [i async for i in gatherer._fetch_repo_issues(sample_repo)]

        # Assert - all 5 issues should be returned since under cap
        assert len(issues) == 5

    async def test_logs_when_cap_reached(self, mock_client, sample_repo, caplog):
        # Arrange
        gatherer = Gatherer(client=mock_client, max_issues_per_repo=2)

        mock_client.execute_query.return_value = {
            "repository": {
                "issues": {
                    "pageInfo": {"hasNextPage": True, "endCursor": "cursor_1"},
                    "nodes": [
                        make_issue_node(f"I_{i}", body="## Description\n```code\n```")
                        for i in range(5)
                    ],
                }
            }
        }

        # Act
        import logging
        with caplog.at_level(logging.INFO):
            _ = [i async for i in gatherer._fetch_repo_issues(sample_repo)]

        # Assert - should log info message about reaching cap
        assert any("Reached cap of 2 issues" in record.message for record in caplog.records)
        assert any("facebook/react" in record.message for record in caplog.records)


class TestConcurrentHarvesting:
    """Tests for PERF-001: concurrent repository processing with bounded concurrency"""

    async def test_processes_repos_concurrently(self, mock_client):
        # Arrange - 5 repos with concurrency=3, each API call has 50ms delay
        # If sequential: 5 * 50ms = 250ms minimum
        # If concurrent (3): ~100ms (2 batches)
        repos = [
            RepositoryData(
                node_id=f"R_{i}",
                full_name=f"owner/repo{i}",
                primary_language="Python",
                stargazer_count=1000,
                issue_count_open=50,
                topics=[],
            )
            for i in range(5)
        ]

        call_times = []

        async def mock_execute_with_delay(*args, **kwargs):
            import time
            start = time.monotonic()
            await asyncio.sleep(0.05)  # 50ms delay per API call
            call_times.append(time.monotonic() - start)
            return {
                "repository": {
                    "issues": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [make_issue_node("I_1", body="## Description\n```code\n```")],
                    }
                }
            }

        mock_client.execute_query.side_effect = mock_execute_with_delay
        gatherer = Gatherer(client=mock_client, concurrency=3)

        # Act
        import time
        start_time = time.monotonic()
        issues = [i async for i in gatherer.harvest_issues(repos)]
        elapsed = time.monotonic() - start_time

        # Assert - concurrent execution should be faster than sequential
        # 5 repos at 50ms each sequential = 250ms
        # With concurrency=3: batch1 (3 repos) + batch2 (2 repos) = ~100ms
        assert elapsed < 0.2  # Should complete in under 200ms, not 250ms+
        assert len(issues) == 5  # All 5 repos should yield 1 issue each

    async def test_semaphore_limits_concurrent_requests(self, mock_client):
        # Arrange - 10 repos with concurrency=2
        # Track max simultaneous active fetches to verify semaphore works
        repos = [
            RepositoryData(
                node_id=f"R_{i}",
                full_name=f"owner/repo{i}",
                primary_language="Python",
                stargazer_count=1000,
                issue_count_open=50,
                topics=[],
            )
            for i in range(10)
        ]

        active_count = [0]
        max_concurrent = [0]

        async def mock_execute_tracking(*args, **kwargs):
            active_count[0] += 1
            max_concurrent[0] = max(max_concurrent[0], active_count[0])
            await asyncio.sleep(0.02)  # Small delay to allow overlap detection
            active_count[0] -= 1
            return {
                "repository": {
                    "issues": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [make_issue_node("I_1", body="## Description\n```code\n```")],
                    }
                }
            }

        mock_client.execute_query.side_effect = mock_execute_tracking
        gatherer = Gatherer(client=mock_client, concurrency=2)

        # Act
        _ = [i async for i in gatherer.harvest_issues(repos)]

        # Assert - max concurrent should never exceed semaphore limit of 2
        assert max_concurrent[0] <= 2
        assert max_concurrent[0] >= 1  # Should have had at least some concurrency

    async def test_single_repo_failure_does_not_stop_others(self, mock_client):
        # Arrange - 5 repos, repo at index 1 raises exception after all retries
        repos = [
            RepositoryData(
                node_id=f"R_{i}",
                full_name=f"owner/repo{i}",
                primary_language="Python",
                stargazer_count=1000,
                issue_count_open=50,
                topics=[],
            )
            for i in range(5)
        ]

        call_counts_by_repo = {}

        async def mock_execute_with_failure(*args, **kwargs):
            variables = kwargs.get("variables", args[1] if len(args) > 1 else {})
            repo_name = f"{variables.get('owner')}/{variables.get('name')}"
            call_counts_by_repo[repo_name] = call_counts_by_repo.get(repo_name, 0) + 1

            # Repo1 always fails
            if "repo1" in repo_name:
                raise Exception("Simulated failure for repo1")

            return {
                "repository": {
                    "issues": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [make_issue_node(f"I_{repo_name}", body="## Description\n```code\n```")],
                    }
                }
            }

        mock_client.execute_query.side_effect = mock_execute_with_failure
        gatherer = Gatherer(client=mock_client, concurrency=3)

        # Act
        with patch("asyncio.sleep", new_callable=AsyncMock):
            issues = [i async for i in gatherer.harvest_issues(repos)]

        # Assert - should get issues from 4 successful repos (0, 2, 3, 4)
        # repo1 failed but others should succeed
        assert len(issues) == 4
        issue_ids = [i.node_id for i in issues]
        assert not any("repo1" in id for id in issue_ids)

    async def test_all_issues_from_all_repos_yielded(self, mock_client):
        # Arrange - 5 repos, each yields 3 issues = 15 total
        repos = [
            RepositoryData(
                node_id=f"R_{i}",
                full_name=f"owner/repo{i}",
                primary_language="Python",
                stargazer_count=1000,
                issue_count_open=50,
                topics=[],
            )
            for i in range(5)
        ]

        def make_response_for_repo(repo_idx):
            return {
                "repository": {
                    "issues": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            make_issue_node(f"I_repo{repo_idx}_issue{j}", body="## Description\n```code\n```")
                            for j in range(3)
                        ],
                    }
                }
            }

        repo_call_idx = [0]

        async def mock_execute_multi_issues(*args, **kwargs):
            variables = kwargs.get("variables", args[1] if len(args) > 1 else {})
            repo_name = variables.get("name", "")
            # Extract repo index from name like "repo0", "repo1", etc.
            repo_idx = int(repo_name.replace("repo", ""))
            return make_response_for_repo(repo_idx)

        mock_client.execute_query.side_effect = mock_execute_multi_issues
        gatherer = Gatherer(client=mock_client, concurrency=3)

        # Act
        issues = [i async for i in gatherer.harvest_issues(repos)]

        # Assert - all 15 issues should be yielded
        assert len(issues) == 15
        # Verify we got issues from all 5 repos
        repo_ids_in_issues = set(i.node_id.split("_")[1] for i in issues)
        assert repo_ids_in_issues == {"repo0", "repo1", "repo2", "repo3", "repo4"}

    async def test_uses_configurable_concurrency(self, mock_client):
        # Arrange - verify concurrency parameter is accepted and stored
        gatherer_low = Gatherer(client=mock_client, concurrency=2)
        gatherer_high = Gatherer(client=mock_client, concurrency=20)

        # Assert - concurrency should be stored correctly
        assert gatherer_low._concurrency == 2
        assert gatherer_high._concurrency == 20

    async def test_defaults_to_concurrency_of_10(self, mock_client):
        # Arrange & Act - create gatherer without specifying concurrency
        gatherer = Gatherer(client=mock_client)

        # Assert - should default to 10 as specified in PERF-005
        assert gatherer._concurrency == 10

