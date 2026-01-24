"""
Pub/Sub message producer for issue ingestion.

Replaces GCS JSONL + Cloud Run Jobs API triggering with
direct Pub/Sub publishing for event-driven processing.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import AsyncIterator
from functools import partial
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

    MAX_INFLIGHT: int = 50  # Max concurrent publish requests (Memory safety)
    PUBLISH_TIMEOUT: float = 60.0  # Seconds to wait for publish (Deadlock prevention)

    def __init__(self, project_id: str, topic_id: str):
        self._publisher = pubsub_v1.PublisherClient()
        self._topic_path = self._publisher.topic_path(project_id, topic_id)
        # Bounded semaphore prevents arbitrary memory growth from unbounded concurrency
        self._semaphore = asyncio.Semaphore(self.MAX_INFLIGHT)
        self._active_futures: set[asyncio.Future] = set()

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
        """Deprecated single-publish method. Use publish_stream for safety."""
        # For backward compatibility if needed, but risky without semaphore
        logger.warning("Using deprecated publish_issue; use publish_stream for memory safety")
        content_hash = compute_content_hash(issue)
        message_data = self._serialize_issue(issue, content_hash)
        self._publisher.publish(self._topic_path, message_data, content_hash=content_hash)

    async def publish_stream(
        self,
        issues: AsyncIterator[IssueData],
        log_every: int = 500,
    ) -> int:
        """
        Publish issue stream to Pub/Sub with backpressure and memory bounds.

        Uses a semaphore to limit in-flight requests and waits for completion
        incrementally to ensure memory usage remains O(1) relative to stream size.
        """
        submitted_count = 0
        failed_initiation_count = 0
        failed_completion_count = 0
        loop = asyncio.get_running_loop()

        try:
            async for issue in issues:
                # 1. Acquire semaphore BEFORE creating heavy payloads (Hole #1)
                # This applies backpressure to the Gatherer if we are saturated
                await self._semaphore.acquire()

                try:
                    # 2. Serialize only after acquiring semaphore
                    content_hash = compute_content_hash(issue)
                    message_data = self._serialize_issue(issue, content_hash)

                    # 3. Publish
                    pubsub_future = self._publisher.publish(
                        self._topic_path,
                        message_data,
                        content_hash=content_hash,
                    )

                    # Create a cleanup callback that releases semaphore
                    # Fix: Use partial to pass keyword argument 'timeout' to result()
                    future = loop.run_in_executor(
                        None,
                        partial(pubsub_future.result, timeout=self.PUBLISH_TIMEOUT)
                    )

                    # We track the future to await it later
                    future.add_done_callback(lambda _: self._semaphore.release())

                    self._active_futures.add(future)
                    future.add_done_callback(self._active_futures.discard)

                    submitted_count += 1
                    if submitted_count % log_every == 0:
                        logger.info(
                            f"Published {submitted_count} issues to Pub/Sub",
                            extra={"issues_published": submitted_count, "active_futures": len(self._active_futures)},
                        )

                except Exception as e:
                    # If serialization or initial publish fails, we must release immediately
                    self._semaphore.release()
                    failed_initiation_count += 1
                    logger.error(f"Failed to initiate publish: {e}")

                # 4. Periodically prune/check active futures to bubble up errors early
                if len(self._active_futures) >= self.MAX_INFLIGHT:
                    done, _ = await asyncio.wait(self._active_futures, return_when=asyncio.FIRST_COMPLETED)
                    for f in done:
                        try:
                            await f
                        except Exception as e:
                            failed_completion_count += 1
                            logger.error(f"Publish failed: {e}")

            # Wait for all remaining futures
            if self._active_futures:
                done, _ = await asyncio.wait(self._active_futures, return_when=asyncio.ALL_COMPLETED)
                for f in done:
                    try:
                        await f
                    except Exception as e:
                        failed_completion_count += 1
                        logger.error(f"Publish failed during flush: {e}")

        except Exception as e:
            logger.exception(f"Stream publishing failed: {e}")
            raise e

        total_failures = failed_initiation_count + failed_completion_count

        # Summary logging
        if total_failures > 0:
            logger.warning(
                f"Publishing complete with {total_failures} failures: {submitted_count - failed_completion_count} successfully published",
                extra={
                    "total_submitted": submitted_count,
                    "failed_initiation": failed_initiation_count,
                    "failed_completion": failed_completion_count
                },
            )
        else:
            logger.info(
                f"Publishing complete: {submitted_count} issues published to Pub/Sub",
                extra={"issues_published": submitted_count, "topic": self._topic_path},
            )

        return submitted_count - failed_completion_count

    def close(self) -> None:
        """Close the publisher client."""
        self._publisher.close()
