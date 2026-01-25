"""
Embedding worker: Consumes issues from Pub/Sub and generates embeddings.

Runs as a Cloud Run service with Pub/Sub pull subscription.
Autoscales based on queue depth via Cloud Run or KEDA.

This is a long-running worker that:
1. Pulls messages from issueindex-issues-embed subscription
2. Processes each message via IssueEmbeddingConsumer with retry policy
3. Acknowledges successful messages
4. Lets failed messages retry (up to 5 times via Pub/Sub) then go to DLQ
5. Handles graceful shutdown on SIGTERM
"""

import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING


from google.pubsub_v1.services.subscriber import SubscriberAsyncClient

from gim_backend.core.config import get_settings
from gim_backend.ingestion.nomic_moe_embedder import NomicMoEEmbedder
from gim_backend.ingestion.pubsub_consumer import IssueEmbeddingConsumer
from gim_database.session import async_session_factory

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# Retry configuration for message processing
# Separate from Pub/Sub's delivery retries; handles transient failures within a single delivery
RETRY_CONFIG = {
    "max_attempts": 3,
    "initial_backoff_seconds": 2,
    "max_backoff_seconds": 60,
    "backoff_multiplier": 2,
}


async def process_with_retry(
    message_data: bytes,
    consumer: IssueEmbeddingConsumer,
) -> bool:
    """
    Process message with exponential backoff retry.
    
    Retries on transient failures (network, database) within a single Pub/Sub delivery.
    If all retries fail, returns False so the message is nack'd and Pub/Sub will redeliver.
    """
    for attempt in range(RETRY_CONFIG["max_attempts"]):
        try:
            return await consumer.process_message(message_data)
        except Exception as e:
            if attempt == RETRY_CONFIG["max_attempts"] - 1:
                logger.error(
                    f"Final attempt {attempt + 1} failed: {e}",
                    extra={"attempt": attempt + 1, "error": str(e)},
                )
                return False
            
            backoff = min(
                RETRY_CONFIG["initial_backoff_seconds"] * (RETRY_CONFIG["backoff_multiplier"] ** attempt),
                RETRY_CONFIG["max_backoff_seconds"],
            )
            logger.warning(
                f"Attempt {attempt + 1} failed, retrying in {backoff}s: {e}",
                extra={"attempt": attempt + 1, "backoff_seconds": backoff, "error": str(e)},
            )
            await asyncio.sleep(backoff)
    
    return False


class GracefulShutdown:
    """Handles SIGTERM for graceful shutdown during message processing."""
    
    def __init__(self):
        self._shutdown_requested = False
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self._shutdown_requested = True
    
    @property
    def should_stop(self) -> bool:
        return self._shutdown_requested


@asynccontextmanager
async def create_session():
    """Context manager for database session."""
    async with async_session_factory() as session:
        yield session


async def run_embedding_worker(embedder: NomicMoEEmbedder) -> None:
    """
    Long-running worker that processes Pub/Sub messages.
    
    Pulls messages in batches using AsyncSubscriberClient, processes them,
    and acknowledges/nacks based on success. Handles graceful shutdown.
    """
    settings = get_settings()
    shutdown = GracefulShutdown()
    
    if not settings.pubsub_project:
        raise ValueError("PUBSUB_PROJECT environment variable is required")
    
    project_id = settings.pubsub_project
    subscription_id = "issueindex-issues-embed"
    
    logger.info(
        "Starting embedding worker",
        extra={
            "project_id": project_id,
            "subscription_id": subscription_id,
            "embedding_model": settings.embedding_model,
            "embedding_dim": settings.embedding_dim,
        },
    )
    
    # Create consumer with injected embedder
    consumer = IssueEmbeddingConsumer(
        embedder=embedder,
        session_factory=create_session,
    )
    
    # Create Async subscriber client
    subscriber = SubscriberAsyncClient()
    subscription_path = subscriber.subscription_path(project_id, subscription_id)
    
    # Track statistics
    processed_count = 0
    success_count = 0
    failure_count = 0
    
    try:
        logger.info(f"Listening for messages on {subscription_path}")
        
        while not shutdown.should_stop:
            # Pull messages in batches using Async Client
            try:
                response = await subscriber.pull(
                    request={
                        "subscription": subscription_path,
                        "max_messages": settings.embedding_batch_size,
                    },
                    timeout=30.0,  # Long poll timeout
                )
            except Exception as e:
                # Handle timeout errors
                err_str = str(e)
                if "504 Deadline Exceeded" in err_str or "DEADLINE_EXCEEDED" in err_str:
                    logger.debug("No messages available via async pull")
                    continue
                    
                logger.error(f"Failed to pull messages: {e}")
                await asyncio.sleep(5)  # Backoff on error
                continue
            
            if not response.received_messages:
                continue
            
            ack_ids = []
            nack_ids = []
            
            # Loop through batch with atomic shutdown checks
            try:
                for received_message in response.received_messages:
                    # 1. Check shutdown BEFORE starting work
                    if shutdown.should_stop:
                        logger.info("Shutdown signaled mid-batch; yielding remaining messages")
                        nack_ids.append(received_message.ack_id)
                        continue

                    message = received_message.message
                    ack_id = received_message.ack_id
                    processed_count += 1
                    
                    # Process with retry policy for transient failures
                    success = await process_with_retry(message.data, consumer)
                    
                    if success:
                        ack_ids.append(ack_id)
                        success_count += 1
                    else:
                        nack_ids.append(ack_id)
                        failure_count += 1

            finally:
                # 2. Atomic Commit/Rollback for the batch
                if ack_ids:
                    await subscriber.acknowledge(
                        request={
                            "subscription": subscription_path,
                            "ack_ids": ack_ids,
                        }
                    )
                
                if nack_ids:
                    # Don't use ack_deadline=0 during shutdown to prevent thundering
                    delay = 0 if not shutdown.should_stop else 30
                    
                    await subscriber.modify_ack_deadline(
                        request={
                            "subscription": subscription_path,
                            "ack_ids": nack_ids,
                            "ack_deadline_seconds": delay,
                        }
                    )
            
            # Log progress periodically
            if processed_count % 100 == 0:
                logger.info(
                    "Embedding worker progress",
                    extra={
                        "processed": processed_count,
                        "success": success_count,
                        "failure": failure_count,
                    },
                )
    
    except Exception as e:
        logger.exception(f"Embedding worker error: {e}")
        raise
    
    finally:
        # Cleanup does NOT close the embedder here as it is owned by __main__
        await subscriber.close()
        
        logger.info(
            "Embedding worker shutdown complete",
            extra={
                "total_processed": processed_count,
                "total_success": success_count,
                "total_failure": failure_count,
            },
        )
