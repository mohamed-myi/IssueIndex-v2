"""Unit tests for GathererWorker that consumes repo tasks and publishes issues"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.gatherer_worker import (
    GathererWorker,
    GracefulShutdown,
    RepoTaskMessage,
    deserialize_repo_message,
    process_with_retry,
)


@pytest.fixture
def sample_repo_message_data():
    """Create sample repo task message bytes."""
    data = {
        "node_id": "R_123abc",
        "full_name": "owner/repo",
        "primary_language": "Python",
        "stargazer_count": 1500,
        "topics": ["machine-learning", "python"],
    }
    return json.dumps(data).encode("utf-8")


@pytest.fixture
def make_repo_message():
    """Factory fixture for creating repo message bytes."""
    def _make(
        node_id: str = "R_123abc",
        full_name: str = "owner/repo",
        primary_language: str = "Python",
        stargazer_count: int = 1500,
        topics: list[str] | None = None,
    ):
        data = {
            "node_id": node_id,
            "full_name": full_name,
            "primary_language": primary_language,
            "stargazer_count": stargazer_count,
            "topics": topics or [],
        }
        return json.dumps(data).encode("utf-8")
    return _make


class TestDeserializeRepoMessage:
    """Tests for repo message deserialization"""

    def test_deserializes_valid_message(self, sample_repo_message_data):
        """Should deserialize valid JSON message to RepoTaskMessage"""
        # Act
        result = deserialize_repo_message(sample_repo_message_data)

        # Assert
        assert result.node_id == "R_123abc"
        assert result.full_name == "owner/repo"
        assert result.primary_language == "Python"
        assert result.stargazer_count == 1500
        assert result.topics == ["machine-learning", "python"]

    def test_handles_missing_topics(self, make_repo_message):
        """Should default to empty list if topics not present"""
        # Arrange
        data = {"node_id": "R_1", "full_name": "a/b", "primary_language": "Go", "stargazer_count": 100}
        message_bytes = json.dumps(data).encode("utf-8")

        # Act
        result = deserialize_repo_message(message_bytes)

        # Assert
        assert result.topics == []

    def test_raises_on_invalid_json(self):
        """Should raise JSONDecodeError on invalid JSON"""
        # Arrange
        invalid_bytes = b"not valid json"

        # Act & Assert
        with pytest.raises(json.JSONDecodeError):
            deserialize_repo_message(invalid_bytes)

    def test_raises_on_missing_required_field(self):
        """Should raise KeyError on missing required field"""
        # Arrange
        data = {"node_id": "R_1"}  # Missing full_name, primary_language, stargazer_count
        message_bytes = json.dumps(data).encode("utf-8")

        # Act & Assert
        with pytest.raises(KeyError):
            deserialize_repo_message(message_bytes)


class TestRepoTaskMessage:
    """Tests for RepoTaskMessage dataclass"""

    def test_to_repository_data_conversion(self):
        """Should convert to RepositoryData correctly"""
        task = RepoTaskMessage(
            node_id="R_abc",
            full_name="org/project",
            primary_language="TypeScript",
            stargazer_count=5000,
            topics=["web", "frontend"],
        )

        repo_data = task.to_repository_data()

        assert repo_data.node_id == "R_abc"
        assert repo_data.full_name == "org/project"
        assert repo_data.primary_language == "TypeScript"
        assert repo_data.stargazer_count == 5000
        assert repo_data.issue_count_open == 0  # Default since it's not in Pub/Sub
        assert repo_data.topics == ["web", "frontend"]

    def test_is_frozen(self):
        """RepoTaskMessage should be immutable"""
        # Arrange
        task = RepoTaskMessage(
            node_id="R_1",
            full_name="a/b",
            primary_language="Rust",
            stargazer_count=100,
            topics=[],
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            task.node_id = "R_2"


class TestGracefulShutdown:
    """Tests for graceful shutdown handler"""

    def test_initial_state_is_not_shutdown(self):
        """should_stop should be False initially"""
        # Arrange & Act
        shutdown = GracefulShutdown()

        # Assert
        assert shutdown.should_stop is False

    def test_signal_handler_sets_shutdown(self):
        """Signal handler should set should_stop to True"""
        # Arrange
        shutdown = GracefulShutdown()

        # Act
        shutdown._signal_handler(15, None)  # SIGTERM

        # Assert
        assert shutdown.should_stop is True


class TestGathererWorker:
    """Tests for GathererWorker message processing"""

    @pytest.fixture
    def mock_github_client(self):
        return MagicMock()

    @pytest.fixture
    def mock_issue_producer(self):
        producer = MagicMock()
        producer.publish_issue = MagicMock()
        return producer

    @pytest.fixture
    def mock_gatherer(self):
        """Create mock gatherer that yields test issues."""
        with patch("jobs.gatherer_worker.Gatherer") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            yield mock_instance

    @pytest.mark.asyncio
    async def test_process_repo_message_success(
        self, mock_github_client, mock_issue_producer, mock_gatherer, sample_repo_message_data
    ):
        """Should process valid message and publish issues"""
        # Arrange
        from ingestion.gatherer import IssueData

        mock_issue = MagicMock(spec=IssueData)
        mock_issue.node_id = "I_1"

        async def mock_fetch_issues(*args, **kwargs):
            yield mock_issue

        mock_gatherer._fetch_repo_issues_with_retry = mock_fetch_issues

        worker = GathererWorker(
            github_client=mock_github_client,
            issue_producer=mock_issue_producer,
            max_issues_per_repo=100,
        )
        # Replace the internal gatherer with our mock
        worker._gatherer = mock_gatherer

        # Act
        result = await worker.process_repo_message(sample_repo_message_data)

        # Assert
        assert result is True
        mock_issue_producer.publish_issue.assert_called_once_with(mock_issue)

    @pytest.mark.asyncio
    async def test_process_repo_message_invalid_json(
        self, mock_github_client, mock_issue_producer, mock_gatherer
    ):
        """Should return False on invalid JSON"""
        # Arrange
        worker = GathererWorker(
            github_client=mock_github_client,
            issue_producer=mock_issue_producer,
        )
        worker._gatherer = mock_gatherer
        invalid_data = b"not json"

        # Act
        result = await worker.process_repo_message(invalid_data)

        # Assert
        assert result is False
        mock_issue_producer.publish_issue.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_repo_message_handles_exception(
        self, mock_github_client, mock_issue_producer, mock_gatherer, sample_repo_message_data
    ):
        """Should return False and not crash on exception"""
        # Arrange
        async def mock_fetch_issues_error(*args, **kwargs):
            raise Exception("GitHub API error")
            yield  # Make it an async generator

        mock_gatherer._fetch_repo_issues_with_retry = mock_fetch_issues_error

        worker = GathererWorker(
            github_client=mock_github_client,
            issue_producer=mock_issue_producer,
        )
        worker._gatherer = mock_gatherer

        # Act
        result = await worker.process_repo_message(sample_repo_message_data)

        # Assert
        assert result is False


class TestProcessWithRetry:
    """Tests for retry logic"""

    @pytest.mark.asyncio
    async def test_returns_true_on_first_success(self):
        """Should return True immediately on success"""
        # Arrange
        mock_worker = MagicMock()
        mock_worker.process_repo_message = AsyncMock(return_value=True)
        message_data = b'{"test": "data"}'

        # Act
        result = await process_with_retry(message_data, mock_worker)

        # Assert
        assert result is True
        assert mock_worker.process_repo_message.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        """Should retry on transient failures"""
        # Arrange
        mock_worker = MagicMock()
        # Fail twice, then succeed
        mock_worker.process_repo_message = AsyncMock(
            side_effect=[Exception("Error 1"), Exception("Error 2"), True]
        )
        message_data = b'{"test": "data"}'

        # Act
        with patch("jobs.gatherer_worker.asyncio.sleep", new_callable=AsyncMock):
            result = await process_with_retry(message_data, mock_worker)

        # Assert
        assert result is True
        assert mock_worker.process_repo_message.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_false_after_max_retries(self):
        """Should return False after exhausting retries"""
        # Arrange
        mock_worker = MagicMock()
        mock_worker.process_repo_message = AsyncMock(side_effect=Exception("Persistent error"))
        message_data = b'{"test": "data"}'

        # Act
        with patch("jobs.gatherer_worker.asyncio.sleep", new_callable=AsyncMock):
            result = await process_with_retry(message_data, mock_worker)

        # Assert
        assert result is False
        assert mock_worker.process_repo_message.call_count == 3  # RETRY_CONFIG max_attempts
