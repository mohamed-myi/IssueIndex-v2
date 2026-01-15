"""Unit tests for Pub/Sub producer with content hash computation"""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.gatherer import IssueData
from src.ingestion.pubsub_producer import (
    IssuePubSubProducer,
    compute_content_hash,
)
from src.ingestion.quality_gate import QScoreComponents


@pytest.fixture
def sample_q_components():
    return QScoreComponents(
        has_code=True,
        has_headers=True,
        tech_weight=0.5,
        is_junk=False,
    )


@pytest.fixture
def make_issue(sample_q_components):
    def _make(
        node_id: str = "I_123",
        title: str = "Bug report",
        body_text: str = "Description of the bug",
    ):
        return IssueData(
            node_id=node_id,
            repo_id="R_456",
            title=title,
            body_text=body_text,
            labels=["bug"],
            github_created_at=datetime.now(UTC),
            q_score=0.75,
            q_components=sample_q_components,
            state="open",
        )
    return _make


class TestComputeContentHash:
    """Tests for content hash computation"""

    def test_content_hash_deterministic(self, make_issue):
        """Same content produces same hash"""
        issue1 = make_issue(node_id="I_1", title="Bug", body_text="Description")
        issue2 = make_issue(node_id="I_1", title="Bug", body_text="Description")

        hash1 = compute_content_hash(issue1)
        hash2 = compute_content_hash(issue2)

        assert hash1 == hash2

    def test_content_hash_changes_with_title(self, make_issue):
        """Different title produces different hash"""
        issue1 = make_issue(title="Bug report")
        issue2 = make_issue(title="Feature request")

        hash1 = compute_content_hash(issue1)
        hash2 = compute_content_hash(issue2)

        assert hash1 != hash2

    def test_content_hash_changes_with_body(self, make_issue):
        """Different body produces different hash"""
        issue1 = make_issue(body_text="Original description")
        issue2 = make_issue(body_text="Updated description")

        hash1 = compute_content_hash(issue1)
        hash2 = compute_content_hash(issue2)

        assert hash1 != hash2

    def test_content_hash_changes_with_node_id(self, make_issue):
        """Different node_id produces different hash"""
        issue1 = make_issue(node_id="I_1")
        issue2 = make_issue(node_id="I_2")

        hash1 = compute_content_hash(issue1)
        hash2 = compute_content_hash(issue2)

        assert hash1 != hash2

    def test_content_hash_is_64_chars(self, make_issue):
        """SHA256 hash should be 64 hex characters"""
        issue = make_issue()
        content_hash = compute_content_hash(issue)

        assert len(content_hash) == 64
        assert all(c in "0123456789abcdef" for c in content_hash)


class TestIssuePubSubProducer:
    """Tests for Pub/Sub producer"""

    @pytest.fixture
    def mock_publisher(self):
        with patch("src.ingestion.pubsub_producer.pubsub_v1.PublisherClient") as mock:
            mock_client = MagicMock()
            mock_client.topic_path.return_value = "projects/test/topics/test-topic"
            mock.return_value = mock_client
            yield mock_client

    def test_creates_topic_path(self, mock_publisher):
        """Should create correct topic path"""
        producer = IssuePubSubProducer(
            project_id="test-project",
            topic_id="test-topic",
        )

        mock_publisher.topic_path.assert_called_once_with("test-project", "test-topic")

    def test_publish_issue_includes_content_hash(self, mock_publisher, make_issue):
        """Published message should include content_hash attribute"""
        mock_future = MagicMock()
        mock_publisher.publish.return_value = mock_future

        producer = IssuePubSubProducer(
            project_id="test-project",
            topic_id="test-topic",
        )
        issue = make_issue()
        producer.publish_issue(issue)

        # Verify publish was called with content_hash attribute
        call_args = mock_publisher.publish.call_args
        assert "content_hash" in call_args.kwargs

    def test_publish_issue_serializes_correctly(self, mock_publisher, make_issue):
        """Published message should contain correct JSON data"""
        mock_future = MagicMock()
        mock_publisher.publish.return_value = mock_future

        producer = IssuePubSubProducer(
            project_id="test-project",
            topic_id="test-topic",
        )
        issue = make_issue(node_id="I_test", title="Test Bug", body_text="Test body")
        producer.publish_issue(issue)

        # Get the message data from publish call
        call_args = mock_publisher.publish.call_args
        message_bytes = call_args.args[1]
        message_data = json.loads(message_bytes.decode("utf-8"))

        assert message_data["node_id"] == "I_test"
        assert message_data["title"] == "Test Bug"
        assert message_data["body_text"] == "Test body"
        assert message_data["repo_id"] == "R_456"
        assert message_data["state"] == "open"
        assert message_data["q_score"] == 0.75
        assert "content_hash" in message_data
        assert "q_components" in message_data
        assert message_data["q_components"]["has_code"] is True

    def test_publish_issue_includes_q_components(self, mock_publisher, make_issue):
        """Q-score components should be serialized correctly"""
        mock_future = MagicMock()
        mock_publisher.publish.return_value = mock_future

        producer = IssuePubSubProducer(
            project_id="test-project",
            topic_id="test-topic",
        )
        issue = make_issue()
        producer.publish_issue(issue)

        call_args = mock_publisher.publish.call_args
        message_bytes = call_args.args[1]
        message_data = json.loads(message_bytes.decode("utf-8"))

        assert message_data["q_components"]["has_code"] is True
        assert message_data["q_components"]["has_headers"] is True
        assert message_data["q_components"]["tech_weight"] == 0.5


class TestPublishStream:
    """Tests for streaming publish"""

    @pytest.fixture
    def mock_publisher(self):
        with patch("src.ingestion.pubsub_producer.pubsub_v1.PublisherClient") as mock:
            mock_client = MagicMock()
            mock_client.topic_path.return_value = "projects/test/topics/test-topic"
            mock.return_value = mock_client
            yield mock_client

    @pytest.mark.asyncio
    async def test_publish_stream_returns_count(self, mock_publisher, make_issue):
        """publish_stream should return count of published messages"""
        mock_future = MagicMock()
        mock_future.result.return_value = "message_id"
        mock_publisher.publish.return_value = mock_future

        producer = IssuePubSubProducer(
            project_id="test-project",
            topic_id="test-topic",
        )

        async def issue_stream():
            for i in range(5):
                yield make_issue(node_id=f"I_{i}")

        count = await producer.publish_stream(issue_stream())

        assert count == 5
        assert mock_publisher.publish.call_count == 5

    @pytest.mark.asyncio
    async def test_publish_stream_awaits_futures(self, mock_publisher, make_issue):
        """publish_stream should wait for all publishes to complete"""
        mock_future = MagicMock()
        mock_publisher.publish.return_value = mock_future

        producer = IssuePubSubProducer(
            project_id="test-project",
            topic_id="test-topic",
        )

        async def issue_stream():
            yield make_issue()

        await producer.publish_stream(issue_stream())

        # Future.result() should be called to wait for completion
        mock_future.result.assert_called()

    @pytest.mark.asyncio
    async def test_publish_stream_handles_empty_stream(self, mock_publisher):
        """Empty stream should return 0 without errors"""
        producer = IssuePubSubProducer(
            project_id="test-project",
            topic_id="test-topic",
        )

        async def empty_stream():
            return
            yield  # Makes this an async generator

        count = await producer.publish_stream(empty_stream())

        assert count == 0
        mock_publisher.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_stream_counts_failures(self, mock_publisher, make_issue):
        """Failed publishes should be subtracted from count"""
        mock_future_success = MagicMock()
        mock_future_success.result.return_value = "message_id"

        mock_future_failure = MagicMock()
        mock_future_failure.result.side_effect = Exception("Publish failed")

        # First succeeds, second fails
        mock_publisher.publish.side_effect = [mock_future_success, mock_future_failure]

        producer = IssuePubSubProducer(
            project_id="test-project",
            topic_id="test-topic",
        )

        async def issue_stream():
            yield make_issue(node_id="I_1")
            yield make_issue(node_id="I_2")

        count = await producer.publish_stream(issue_stream())

        assert count == 1  # Only successful publish counted
