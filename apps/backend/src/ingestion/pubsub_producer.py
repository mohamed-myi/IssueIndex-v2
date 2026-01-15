"""
Pub/Sub message producer for issue ingestion.

Replaces GCS JSONL + Cloud Run Jobs API triggering with
direct Pub/Sub publishing for event-driven processing.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

try:
    from google.cloud import pubsub_v1
except ModuleNotFoundError:  # pragma: no cover
    # This module is patched in unit tests. At runtime, Pub/Sub publishing
    # requires the google-cloud-pubsub dependency.
    class _PubSubV1Stub:
        class PublisherClient:  # noqa: D106
            def __init__(self, *_: object, **__: object) -> None:
                raise ModuleNotFoundError(
                    "Missing dependency 'google-cloud-pubsub'. Install it to enable Pub/Sub publishing."
                )

    pubsub_v1 = _PubSubV1Stub()

if TYPE_CHECKING:
    from .gatherer import IssueData

logger = logging.getLogger(__name__)


def compute_content_hash(issue: IssueData) -> str:
    """
    Compute SHA256 hash of issue content for idempotency.

    Hash includes node_id, title, and body_text to detect content changes.
    Same content produces same hash; updated content produces new hash.
    """
    content = f"{issue.node_id}:{issue.title}:{issue.body_text}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class IssuePubSubProducer:
    """
    Publishes issues to Pub/Sub topic for async embedding.

    Replaces the GCS write + Cloud Run Jobs trigger pattern with
    direct message publishing. Each issue becomes a Pub/Sub message
    that the embedding worker will consume and process.
    """

    def __init__(self, project_id: str, topic_id: str):
        self._publisher = pubsub_v1.PublisherClient()
        self._topic_path = self._publisher.topic_path(project_id, topic_id)
        self._futures: list = []

    def _serialize_issue(self, issue: IssueData, content_hash: str) -> bytes:
        """Serialize issue data to JSON bytes for Pub/Sub message."""
        message_data = {
            "node_id": issue.node_id,
            "repo_id": issue.repo_id,
            "title": issue.title,
            "body_text": issue.body_text,
            "labels": issue.labels,
            "github_created_at": (
                issue.github_created_at.isoformat() if issue.github_created_at else None
            ),
            "state": issue.state,
            "q_score": issue.q_score,
            "q_components": {
                "has_code": issue.q_components.has_code,
                "has_headers": issue.q_components.has_headers,
                "tech_weight": issue.q_components.tech_weight,
            },
            "content_hash": content_hash,
        }
        return json.dumps(message_data).encode("utf-8")

    def publish_issue(self, issue: IssueData) -> None:
        """
        Publish single issue to Pub/Sub topic.

        The content_hash is included as both a message attribute (for filtering)
        and in the message body (for idempotency checks during processing).
        """
        content_hash = compute_content_hash(issue)
        message_data = self._serialize_issue(issue, content_hash)

        future = self._publisher.publish(
            self._topic_path,
            message_data,
            content_hash=content_hash,  # Attribute for potential deduplication
        )
        self._futures.append(future)

    async def publish_stream(
        self,
        issues: AsyncIterator[IssueData],
        log_every: int = 500,
    ) -> int:
        """
        Publish issue stream to Pub/Sub; returns count published.

        Issues are published asynchronously and this method waits for
        all publish operations to complete before returning.
        """
        count = 0

        async for issue in issues:
            self.publish_issue(issue)
            count += 1

            if count % log_every == 0:
                logger.info(
                    f"Published {count} issues to Pub/Sub",
                    extra={"issues_published": count, "topic": self._topic_path},
                )

        # Wait for all publishes to complete
        failed_count = 0
        for future in self._futures:
            try:
                future.result()
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to publish message: {e}")

        if failed_count > 0:
            logger.warning(
                f"Publishing complete with {failed_count} failures: {count - failed_count} issues published",
                extra={"total": count, "failed": failed_count},
            )
        else:
            logger.info(
                f"Publishing complete: {count} issues published to Pub/Sub",
                extra={"issues_published": count, "topic": self._topic_path},
            )

        # Clear futures for potential reuse
        self._futures.clear()

        return count - failed_count

    def close(self) -> None:
        """Close the publisher client."""
        self._publisher.close()
