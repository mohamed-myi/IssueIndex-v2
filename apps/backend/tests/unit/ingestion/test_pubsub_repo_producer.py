"""Unit tests for Pub/Sub repo producer for fan-out architecture"""

import json
from unittest.mock import MagicMock, patch

import pytest

from gim_backend.ingestion.pubsub_repo_producer import RepoPubSubProducer
from gim_backend.ingestion.scout import RepositoryData


@pytest.fixture
def sample_repo():
    """Create a sample RepositoryData for testing."""
    return RepositoryData(
        node_id="R_123abc",
        full_name="owner/repo",
        primary_language="Python",
        stargazer_count=1500,
        issue_count_open=50,
        topics=["machine-learning", "python"],
    )


@pytest.fixture
def make_repo():
    """Factory fixture for creating RepositoryData with custom values."""
    def _make(
        node_id: str = "R_123abc",
        full_name: str = "owner/repo",
        primary_language: str = "Python",
        stargazer_count: int = 1500,
        topics: list[str] | None = None,
    ):
        return RepositoryData(
            node_id=node_id,
            full_name=full_name,
            primary_language=primary_language,
            stargazer_count=stargazer_count,
            issue_count_open=50,
            topics=topics if topics is not None else ["topic1"],
        )
    return _make


class TestRepoPubSubProducer:
    """Tests for Pub/Sub repo producer"""

    @pytest.fixture
    def mock_publisher(self):
        with patch("gim_backend.ingestion.pubsub_repo_producer.pubsub_v1.PublisherClient") as mock:
            mock_client = MagicMock()
            mock_client.topic_path.return_value = "projects/test/topics/repo-tasks"
            mock.return_value = mock_client
            yield mock_client

    def test_creates_topic_path(self, mock_publisher):
        """Should create correct topic path from project and topic IDs"""
        # Arrange & Act
        RepoPubSubProducer(
            project_id="test-project",
            topic_id="repo-tasks",
        )

        # Assert
        mock_publisher.topic_path.assert_called_once_with("test-project", "repo-tasks")

    def test_publish_repo_includes_node_id_attribute(self, mock_publisher, sample_repo):
        """Published message should include node_id as message attribute"""
        # Arrange
        mock_future = MagicMock()
        mock_publisher.publish.return_value = mock_future
        producer = RepoPubSubProducer(
            project_id="test-project",
            topic_id="repo-tasks",
        )

        # Act
        producer.publish_repo(sample_repo)

        # Assert
        call_args = mock_publisher.publish.call_args
        assert call_args.kwargs["node_id"] == "R_123abc"
        assert call_args.kwargs["full_name"] == "owner/repo"

    def test_publish_repo_serializes_correctly(self, mock_publisher, sample_repo):
        """Published message should contain correct JSON data"""
        # Arrange
        mock_future = MagicMock()
        mock_publisher.publish.return_value = mock_future
        producer = RepoPubSubProducer(
            project_id="test-project",
            topic_id="repo-tasks",
        )

        # Act
        producer.publish_repo(sample_repo)

        # Assert
        call_args = mock_publisher.publish.call_args
        message_bytes = call_args.args[1]
        message_data = json.loads(message_bytes.decode("utf-8"))

        assert message_data["node_id"] == "R_123abc"
        assert message_data["full_name"] == "owner/repo"
        assert message_data["primary_language"] == "Python"
        assert message_data["stargazer_count"] == 1500
        assert message_data["topics"] == ["machine-learning", "python"]

    def test_publish_repo_handles_empty_topics(self, mock_publisher, make_repo):
        """Should handle repos with empty topics list"""
        # Arrange
        mock_future = MagicMock()
        mock_publisher.publish.return_value = mock_future
        producer = RepoPubSubProducer(
            project_id="test-project",
            topic_id="repo-tasks",
        )
        repo = make_repo(topics=[])

        # Act
        producer.publish_repo(repo)

        # Assert
        call_args = mock_publisher.publish.call_args
        message_bytes = call_args.args[1]
        message_data = json.loads(message_bytes.decode("utf-8"))
        assert message_data["topics"] == []

    def test_close_closes_publisher(self, mock_publisher):
        """close() should close the underlying publisher client"""
        # Arrange
        producer = RepoPubSubProducer(
            project_id="test-project",
            topic_id="repo-tasks",
        )

        # Act
        producer.close()

        # Assert
        mock_publisher.close.assert_called_once()


class TestPublishRepos:
    """Tests for batch repo publishing"""

    @pytest.fixture
    def mock_publisher(self):
        with patch("gim_backend.ingestion.pubsub_repo_producer.pubsub_v1.PublisherClient") as mock:
            mock_client = MagicMock()
            mock_client.topic_path.return_value = "projects/test/topics/repo-tasks"
            mock.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_publish_repos_returns_count(self, mock_publisher, make_repo):
        """publish_repos should return count of published messages"""
        # Arrange
        mock_future = MagicMock()
        mock_future.result.return_value = "message_id"
        mock_publisher.publish.return_value = mock_future
        producer = RepoPubSubProducer(
            project_id="test-project",
            topic_id="repo-tasks",
        )
        repos = [make_repo(node_id=f"R_{i}") for i in range(5)]

        # Act
        count = await producer.publish_repos(repos)

        # Assert
        assert count == 5
        assert mock_publisher.publish.call_count == 5

    @pytest.mark.asyncio
    async def test_publish_repos_awaits_futures(self, mock_publisher, make_repo):
        """publish_repos should wait for all publishes to complete"""
        # Arrange
        mock_future = MagicMock()
        mock_publisher.publish.return_value = mock_future
        producer = RepoPubSubProducer(
            project_id="test-project",
            topic_id="repo-tasks",
        )
        repos = [make_repo()]

        # Act
        await producer.publish_repos(repos)

        # Assert
        mock_future.result.assert_called()

    @pytest.mark.asyncio
    async def test_publish_repos_handles_empty_list(self, mock_publisher):
        """Empty list should return 0 without errors"""
        # Arrange
        producer = RepoPubSubProducer(
            project_id="test-project",
            topic_id="repo-tasks",
        )

        # Act
        count = await producer.publish_repos([])

        # Assert
        assert count == 0
        mock_publisher.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_repos_counts_failures(self, mock_publisher, make_repo):
        """Failed publishes should be subtracted from count"""
        # Arrange
        mock_future_success = MagicMock()
        mock_future_success.result.return_value = "message_id"

        mock_future_failure = MagicMock()
        mock_future_failure.result.side_effect = Exception("Publish failed")

        # First succeeds, second fails, third succeeds
        mock_publisher.publish.side_effect = [
            mock_future_success,
            mock_future_failure,
            mock_future_success,
        ]
        producer = RepoPubSubProducer(
            project_id="test-project",
            topic_id="repo-tasks",
        )
        repos = [make_repo(node_id=f"R_{i}") for i in range(3)]

        # Act
        count = await producer.publish_repos(repos)

        # Assert
        assert count == 2  # Only successful publishes counted

    @pytest.mark.asyncio
    async def test_publish_repos_clears_futures_after_completion(self, mock_publisher, make_repo):
        """Futures list should be cleared after publish_repos completes"""
        # Arrange
        mock_future = MagicMock()
        mock_future.result.return_value = "message_id"
        mock_publisher.publish.return_value = mock_future
        producer = RepoPubSubProducer(
            project_id="test-project",
            topic_id="repo-tasks",
        )
        repos = [make_repo()]

        # Act
        await producer.publish_repos(repos)

        # Assert - internal futures list should be cleared
        assert len(producer._futures) == 0
