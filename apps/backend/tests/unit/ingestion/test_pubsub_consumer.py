"""Unit tests for Pub/Sub consumer with idempotency and embedding generation"""

import json
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from gim_backend.ingestion.pubsub_consumer import IssueEmbeddingConsumer


@pytest.fixture
def sample_message_data():
    """Sample Pub/Sub message data"""
    return {
        "node_id": "I_123",
        "repo_id": "R_456",
        "title": "Bug report",
        "body_text": "Description of the bug",
        "labels": ["bug"],
        "github_created_at": "2026-01-14T12:00:00+00:00",
        "state": "open",
        "q_score": 0.75,
        "q_components": {
            "has_code": True,
            "has_headers": False,
            "tech_weight": 0.3,
        },
        "content_hash": "abc123def456",
    }


@pytest.fixture
def mock_embedder():
    """Mock NomicMoEEmbedder"""
    embedder = AsyncMock()
    embedder.embed_documents = AsyncMock(return_value=[[0.1] * 256])
    return embedder


@pytest.fixture
def mock_session_factory():
    """Mock async session factory"""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def factory():
        yield mock_session

    return factory, mock_session


class TestProcessMessage:
    """Tests for message processing"""

    @pytest.mark.asyncio
    async def test_process_message_generates_256_dim_embedding(
        self, sample_message_data, mock_embedder, mock_session_factory
    ):
        """Should generate 256-dim embedding for message"""
        factory, mock_session = mock_session_factory

        # Not a duplicate
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        message_bytes = json.dumps(sample_message_data).encode("utf-8")
        success = await consumer.process_message(message_bytes)

        assert success is True
        mock_embedder.embed_documents.assert_called_once()

        # Verify text sent to embedder
        call_args = mock_embedder.embed_documents.call_args[0][0]
        assert call_args == ["Bug report\nDescription of the bug"]

    @pytest.mark.asyncio
    async def test_idempotency_skips_duplicate(
        self, sample_message_data, mock_embedder, mock_session_factory
    ):
        """Should skip processing if content_hash already exists"""
        factory, mock_session = mock_session_factory

        # Simulate existing record with same content_hash
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1  # Record exists
        mock_session.execute.return_value = mock_result

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        message_bytes = json.dumps(sample_message_data).encode("utf-8")
        success = await consumer.process_message(message_bytes)

        assert success is True  # Returns True to ACK the message
        mock_embedder.embed_documents.assert_not_called()  # No embedding generated

    @pytest.mark.asyncio
    async def test_failed_embedding_returns_false(
        self, sample_message_data, mock_embedder, mock_session_factory
    ):
        """Should return False if embedding generation fails"""
        factory, mock_session = mock_session_factory

        # Not a duplicate
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        # Embedding returns empty
        mock_embedder.embed_documents.return_value = []

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        message_bytes = json.dumps(sample_message_data).encode("utf-8")
        success = await consumer.process_message(message_bytes)

        assert success is False

    @pytest.mark.asyncio
    async def test_invalid_json_returns_false(
        self, mock_embedder, mock_session_factory
    ):
        """Should return False for invalid JSON"""
        factory, mock_session = mock_session_factory

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        message_bytes = b"not valid json"
        success = await consumer.process_message(message_bytes)

        assert success is False

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_false(
        self, mock_embedder, mock_session_factory
    ):
        """Should return False if node_id or content_hash missing"""
        factory, mock_session = mock_session_factory

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        # Missing content_hash
        message_data = {"node_id": "I_123", "title": "Bug"}
        message_bytes = json.dumps(message_data).encode("utf-8")
        success = await consumer.process_message(message_bytes)

        assert success is False


class TestPersistIssue:
    """Tests for database persistence"""

    @pytest.mark.asyncio
    async def test_process_message_persists_to_db(
        self, sample_message_data, mock_embedder, mock_session_factory
    ):
        """Should execute INSERT query on successful processing"""
        factory, mock_session = mock_session_factory

        # First call for idempotency check (no duplicate)
        mock_check_result = MagicMock()
        mock_check_result.scalar.return_value = None

        # Second call for insert (no return value needed)
        mock_insert_result = MagicMock()

        mock_session.execute.side_effect = [mock_check_result, mock_insert_result]

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        message_bytes = json.dumps(sample_message_data).encode("utf-8")
        await consumer.process_message(message_bytes)

        # Should have called execute twice: once for check, once for insert
        assert mock_session.execute.call_count == 2
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_persists_q_components(
        self, sample_message_data, mock_embedder, mock_session_factory
    ):
        """Should persist Q-score components correctly"""
        factory, mock_session = mock_session_factory

        mock_check_result = MagicMock()
        mock_check_result.scalar.return_value = None
        mock_insert_result = MagicMock()
        mock_session.execute.side_effect = [mock_check_result, mock_insert_result]

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        message_bytes = json.dumps(sample_message_data).encode("utf-8")
        await consumer.process_message(message_bytes)

        # Get the INSERT call arguments
        insert_call = mock_session.execute.call_args_list[1]
        params = insert_call[0][1]

        assert params["has_code"] is True
        assert params["has_template_headers"] is False
        assert params["tech_stack_weight"] == 0.3

    @pytest.mark.asyncio
    async def test_calculates_survival_score(
        self, sample_message_data, mock_embedder, mock_session_factory
    ):
        """Should calculate and persist survival_score"""
        factory, mock_session = mock_session_factory

        mock_check_result = MagicMock()
        mock_check_result.scalar.return_value = None
        mock_insert_result = MagicMock()
        mock_session.execute.side_effect = [mock_check_result, mock_insert_result]

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        message_bytes = json.dumps(sample_message_data).encode("utf-8")
        await consumer.process_message(message_bytes)

        # Get the INSERT call arguments
        insert_call = mock_session.execute.call_args_list[1]
        params = insert_call[0][1]

        # survival_score should be calculated and positive
        assert "survival_score" in params
        assert params["survival_score"] > 0


class TestAlreadyProcessed:
    """Tests for idempotency check"""

    @pytest.mark.asyncio
    async def test_returns_true_when_exists(
        self, mock_embedder, mock_session_factory
    ):
        """Should return True if record with same hash exists"""
        factory, mock_session = mock_session_factory

        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        result = await consumer._already_processed("I_123", "abc123")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_exists(
        self, mock_embedder, mock_session_factory
    ):
        """Should return False if no record with hash exists"""
        factory, mock_session = mock_session_factory

        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_session.execute.return_value = mock_result

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        result = await consumer._already_processed("I_123", "abc123")

        assert result is False


class TestDatetimeParsing:
    """Tests for datetime handling"""

    @pytest.mark.asyncio
    async def test_parses_iso_datetime(
        self, sample_message_data, mock_embedder, mock_session_factory
    ):
        """Should correctly parse ISO datetime strings"""
        factory, mock_session = mock_session_factory

        mock_check_result = MagicMock()
        mock_check_result.scalar.return_value = None
        mock_insert_result = MagicMock()
        mock_session.execute.side_effect = [mock_check_result, mock_insert_result]

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        message_bytes = json.dumps(sample_message_data).encode("utf-8")
        await consumer.process_message(message_bytes)

        # Get the INSERT call arguments
        insert_call = mock_session.execute.call_args_list[1]
        params = insert_call[0][1]

        assert params["github_created_at"] is not None
        assert isinstance(params["github_created_at"], datetime)

    @pytest.mark.asyncio
    async def test_parses_z_suffix_datetime(
        self, sample_message_data, mock_embedder, mock_session_factory
    ):
        """Should handle Z suffix in datetime strings"""
        factory, mock_session = mock_session_factory

        mock_check_result = MagicMock()
        mock_check_result.scalar.return_value = None
        mock_insert_result = MagicMock()
        mock_session.execute.side_effect = [mock_check_result, mock_insert_result]

        consumer = IssueEmbeddingConsumer(
            embedder=mock_embedder,
            session_factory=factory,
        )

        sample_message_data["github_created_at"] = "2026-01-14T12:00:00Z"
        message_bytes = json.dumps(sample_message_data).encode("utf-8")
        await consumer.process_message(message_bytes)

        # Should not raise an error
        assert mock_session.execute.call_count == 2
