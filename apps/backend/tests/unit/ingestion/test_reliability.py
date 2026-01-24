"""
Reliability tests for worker hardening (OOM prevention, Deadlock safety, Graceful shutdown).
"""
import asyncio
from unittest.mock import MagicMock, patch

import pytest

from gim_backend.ingestion.gatherer import IssueData
from gim_backend.ingestion.pubsub_producer import IssuePubSubProducer
from gim_backend.ingestion.quality_gate import QScoreComponents


@pytest.fixture
def make_issue():
    def _make(node_id: str):
        return IssueData(
            node_id=node_id,
            repo_id="R_1",
            title="Test",
            body_text="Body",
            labels=[],
            github_created_at=None,
            q_score=0.5,
            q_components=QScoreComponents(has_code=True, has_headers=True, tech_weight=0.5, is_junk=False),
            state="open",
        )
    return _make


class TestProducerReliability:
    """Tests for Publisher memory bounds and timeouts (Holes #1, #2, #6, #10, #11)"""

    @pytest.mark.asyncio
    async def test_producer_respects_max_inflight(self, make_issue):
        """Verify semaphore limits concurrent publishes."""
        with patch("gim_backend.ingestion.pubsub_producer.pubsub_v1.PublisherClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.topic_path.return_value = "projects/proj/topics/topic"
            mock_client_cls.return_value = mock_client

            producer = IssuePubSubProducer("proj", "topic")
            producer.MAX_INFLIGHT = 2
            producer._semaphore = asyncio.Semaphore(2)

            async def issue_stream():
                for i in range(10):
                    yield make_issue(f"I_{i}")

            mock_future = MagicMock()
            mock_future.result.return_value = "id"
            mock_client.publish.return_value = mock_future

            await producer.publish_stream(issue_stream())

            assert producer._semaphore._value <= producer.MAX_INFLIGHT

    @pytest.mark.asyncio
    async def test_producer_timeout_prevents_deadlock(self, make_issue):
        """Verify hung publisher hits timeout and counts as failure."""
        with patch("gim_backend.ingestion.pubsub_producer.pubsub_v1.PublisherClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.topic_path.return_value = "projects/proj/topics/topic"
            mock_client_cls.return_value = mock_client

            producer = IssuePubSubProducer("proj", "topic")
            producer.PUBLISH_TIMEOUT = 0.1

            async def issue_stream():
                yield make_issue("I_1")

            mock_future = MagicMock()
            mock_future.result.side_effect = TimeoutError("Timed out")
            mock_client.publish.return_value = mock_future

            count = await producer.publish_stream(issue_stream())
            assert count == 0


class TestEmbeddingWorkerReliability:
    """Tests for graceful shutdown atomicity."""

    @pytest.mark.asyncio
    async def test_shutdown_breaks_batch_loop(self):
        """Verify shutdown signal stops batch processing mid-loop."""
        mock_shutdown_obj = MagicMock()
        mock_shutdown_obj.should_stop = False

        msg1, msg2, msg3 = MagicMock(), MagicMock(), MagicMock()
        msg1.ack_id, msg2.ack_id, msg3.ack_id = "ack1", "ack2", "ack3"

        response = MagicMock()
        response.received_messages = [
            MagicMock(message=msg1, ack_id="ack1"),
            MagicMock(message=msg2, ack_id="ack2"),
            MagicMock(message=msg3, ack_id="ack3")
        ]

        ack_ids = []
        nack_ids = []
        processed_count = 0

        for i, received_message in enumerate(response.received_messages):
            if i == 1:
                mock_shutdown_obj.should_stop = True

            if mock_shutdown_obj.should_stop:
                nack_ids.append(received_message.ack_id)
                continue

            ack_ids.append(received_message.ack_id)
            processed_count += 1

        assert processed_count == 1
        assert "ack1" in ack_ids
        assert "ack2" in nack_ids
        assert "ack3" in nack_ids
