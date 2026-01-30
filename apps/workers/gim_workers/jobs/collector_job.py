"""
Collector job: Scout repositories and gather issues to Pub/Sub.

This is the entry point for the event-driven pipeline:
1. Discover top repositories
2. Filter for workload sharding
3. Stream issues with Q-Score filtering
4. Publish: Send issues to Pub/Sub for async embedding

The embedding worker consumes messages from Pub/Sub and generates embeddings.
Runs fast (1-2 minutes) with concurrent repo processing.
"""

import logging
import time

from gim_backend.core.config import get_settings
from gim_backend.ingestion.gatherer import Gatherer
from gim_backend.ingestion.github_client import GitHubGraphQLClient
from gim_backend.ingestion.persistence import StreamingPersistence
from gim_backend.ingestion.pubsub_producer import IssuePubSubProducer
from gim_backend.ingestion.scout import Scout
from gim_database.session import async_session_factory

logger = logging.getLogger(__name__)


async def run_collector_job() -> dict:
    """
    Executes the collection pipeline:
    1. Discover top repositories
    2. Filter via dynamic sharding
    3. Stream issues with Q-Score filtering
    4. Publish issues to Pub/Sub for async embedding
    
    Returns stats dict with repos_discovered and issues_published.
    """
    job_start = time.monotonic()
    settings = get_settings()
    
    if not settings.git_token:
        raise ValueError("GIT_TOKEN environment variable is required")
    
    if not settings.pubsub_project:
        raise ValueError("PUBSUB_PROJECT environment variable is required")

    logger.info(
        "Collector config",
        extra={
            "gatherer_concurrency": settings.gatherer_concurrency,
            "max_issues_per_repo": settings.max_issues_per_repo,
            "pubsub_project": settings.pubsub_project,
            "pubsub_topic": settings.pubsub_issues_topic,
        },
    )

    async with GitHubGraphQLClient(settings.git_token) as client:
        # Discover repositories via GitHub GraphQL
        scout_start = time.monotonic()
        logger.info("Starting Scout - discovering repositories")
        scout = Scout(client)
        all_repos = await scout.discover_repositories()
        
        # Filter repositories to process only ~1/24th based on current hour
        # This implements Dynamic Workload Sharding to respect API rate limits
        from binascii import crc32
        from datetime import UTC, datetime
        
        current_shard = datetime.now(UTC).hour
        repos = []
        
        for repo in all_repos:
            # Stable shard ID based on node_id (0-23)
            shard_id = crc32(repo.node_id.encode("utf-8")) % 24
            if shard_id == current_shard:
                repos.append(repo)
                
        scout_elapsed = time.monotonic() - scout_start
        
        logger.info(
            f"Scout complete in {scout_elapsed:.1f}s - "
            f"Selected {len(repos)}/{len(all_repos)} repositories for shard {current_shard}",
            extra={
                "repos_discovered": len(all_repos),
                "repos_selected": len(repos),
                "shard_id": current_shard,
                "scout_duration_s": round(scout_elapsed, 1)
            },
        )

        if not repos:
            logger.warning(f"No repositories selected for shard {current_shard}; skipping collection")
            return {"repos_discovered": len(all_repos), "issues_published": 0}

        # Persist repositories (FK constraint for issues)
        persist_start = time.monotonic()
        async with async_session_factory() as session:
            persistence = StreamingPersistence(session)
            repos_upserted = await persistence.upsert_repositories(repos)
        persist_elapsed = time.monotonic() - persist_start
            
        logger.info(
            f"Repositories upserted in {persist_elapsed:.1f}s: {repos_upserted}",
            extra={"repos_upserted": repos_upserted, "persist_duration_s": round(persist_elapsed, 1)},
        )

        # Gather issues (fetch from GitHub)
        gather_start = time.monotonic()
        
        logger.info(
            f"Starting Gather with concurrency={settings.gatherer_concurrency}",
            extra={"concurrency": settings.gatherer_concurrency},
        )
        
        gatherer = Gatherer(
            client,
            max_issues_per_repo=settings.max_issues_per_repo,
            concurrency=settings.gatherer_concurrency,
        )
        issue_stream = gatherer.harvest_issues(repos)
        
        # Publish messages to Pub/Sub
        logger.info(
            f"Publishing issues to Pub/Sub topic {settings.pubsub_issues_topic}",
            extra={"topic": settings.pubsub_issues_topic},
        )
        
        producer = IssuePubSubProducer(
            project_id=settings.pubsub_project,
            topic_id=settings.pubsub_issues_topic,
        )
        
        total = await producer.publish_stream(
            issues=issue_stream,
            log_every=500,
        )
        
        gather_elapsed = time.monotonic() - gather_start
        
        logger.info(
            f"Gather + Publish complete in {gather_elapsed:.1f}s - {total} issues published",
            extra={
                "issues_published": total,
                "gather_publish_duration_s": round(gather_elapsed, 1),
            },
        )

        job_elapsed = time.monotonic() - job_start
        logger.info(
            f"Collector job complete in {job_elapsed:.1f}s",
            extra={
                "total_duration_s": round(job_elapsed, 1),
                "scout_duration_s": round(scout_elapsed, 1),
                "gather_publish_duration_s": round(gather_elapsed, 1),
                "repos_discovered": len(repos),
                "issues_published": total,
            },
        )

        return {
            "repos_discovered": len(repos),
            "issues_published": total,
            "duration_s": round(job_elapsed, 1),
        }
