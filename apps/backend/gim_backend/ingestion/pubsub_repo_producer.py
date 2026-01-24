"""
Pub/Sub message producer for repository task fan-out.

Publishes repository discovery tasks to Pub/Sub for parallel processing
by gatherer workers. Each repo becomes a message that triggers independent
issue gathering and publishing.
"""

from __future__ import annotations

import json
import logging
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
    from .scout import RepositoryData

logger = logging.getLogger(__name__)


class RepoPubSubProducer:
    """
    Publishes repository tasks to Pub/Sub for fan-out processing.

    Each repository discovered by Scout becomes a Pub/Sub message.
    Gatherer workers consume these messages and process repos independently,
    enabling horizontal scaling and per-repo failure isolation.
    """

    def __init__(self, project_id: str, topic_id: str):
        self._publisher = pubsub_v1.PublisherClient()
        self._topic_path = self._publisher.topic_path(project_id, topic_id)
        self._futures: list = []

    def _serialize_repo(self, repo: RepositoryData) -> bytes:
        """Serialize repository data to JSON bytes for Pub/Sub message."""
        message_data = {
            "node_id": repo.node_id,
            "full_name": repo.full_name,
            "primary_language": repo.primary_language,
            "stargazer_count": repo.stargazer_count,
            "topics": repo.topics,
        }
        return json.dumps(message_data).encode("utf-8")

    def publish_repo(self, repo: RepositoryData) -> None:
        """
        Publish single repository task to Pub/Sub topic.

        The node_id is included as a message attribute for filtering and deduplication.
        """
        message_data = self._serialize_repo(repo)

        future = self._publisher.publish(
            self._topic_path,
            message_data,
            node_id=repo.node_id,
            full_name=repo.full_name,
        )
        self._futures.append(future)

    async def publish_repos(
        self,
        repos: list[RepositoryData],
        log_every: int = 50,
    ) -> int:
        """
        Publish repository list to Pub/Sub; returns count published.

        Repositories are published asynchronously and this method waits for
        all publish operations to complete before returning.
        """
        count = 0

        for repo in repos:
            self.publish_repo(repo)
            count += 1

            if count % log_every == 0:
                logger.info(
                    f"Published {count} repo tasks to Pub/Sub",
                    extra={"repos_published": count, "topic": self._topic_path},
                )

        # Wait for all publishes to complete
        failed_count = 0
        for future in self._futures:
            try:
                future.result()
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to publish repo task: {e}")

        if failed_count > 0:
            logger.warning(
                f"Repo publishing complete with {failed_count} failures: {count - failed_count} tasks published",
                extra={"total": count, "failed": failed_count},
            )
        else:
            logger.info(
                f"Repo publishing complete: {count} tasks published to Pub/Sub",
                extra={"repos_published": count, "topic": self._topic_path},
            )

        # Clear futures for potential reuse
        self._futures.clear()

        return count - failed_count

    def close(self) -> None:
        """Close the publisher client."""
        self._publisher.close()
