"""
Gatherer job: Full streaming pipeline
Scout -> Gather -> Embed -> Persist

Memory ceiling: less than 1GB during execution via AsyncIterator streaming.
"""

import logging
import sys
from pathlib import Path

# Add backend src to path
backend_src = Path(__file__).parent.parent.parent.parent / "backend" / "src"
if str(backend_src) not in sys.path:
    sys.path.insert(0, str(backend_src))

# Add packages to path
packages_db = Path(__file__).parent.parent.parent.parent.parent / "packages" / "database" / "src"
if str(packages_db) not in sys.path:
    sys.path.insert(0, str(packages_db))

from core.config import get_settings
from ingestion.embeddings import NomicEmbedder, VertexEmbedder, embed_issue_stream
from ingestion.gatherer import Gatherer
from ingestion.github_client import GitHubGraphQLClient
from ingestion.persistence import StreamingPersistence
from ingestion.scout import Scout
from session import async_session_factory

logger = logging.getLogger(__name__)


async def run_gatherer_job() -> dict:
    """
    Executes the full ingestion pipeline:
    1. Scout: Discover top repositories (returns list of ~500 repos)
    2. Gather: Stream issues with Q-Score filtering (AsyncIterator)
    3. Embed: Generate 768-dim vectors (AsyncIterator)
    4. Persistence: UPSERT in batches of 50
    
    Returns stats dict with repos_discovered and issues_persisted.
    """
    settings = get_settings()
    
    if not settings.git_token:
        raise ValueError("GIT_TOKEN environment variable is required")

    async with GitHubGraphQLClient(settings.git_token) as client:
        logger.info("Starting Scout: discovering repositories")
        scout = Scout(client)
        repos = await scout.discover_repositories()
        
        logger.info(
            f"Scout complete: discovered {len(repos)} repositories",
            extra={"repos_discovered": len(repos)},
        )

        if not repos:
            logger.warning("No repositories discovered; skipping ingestion")
            return {"repos_discovered": 0, "issues_persisted": 0}

        # Persist repositories first (FK constraint for issues)
        async with async_session_factory() as session:
            persistence = StreamingPersistence(session)
            repos_upserted = await persistence.upsert_repositories(repos)
            
            logger.info(
                f"Repositories upserted: {repos_upserted}",
                extra={"repos_upserted": repos_upserted},
            )

            logger.info("Starting streaming pipeline: Gather -> Embed -> Persist")
            
            gatherer = Gatherer(client)
            
            if settings.embedding_mode == "vertex":
                embedder = VertexEmbedder(project=settings.gcp_project, region=settings.gcp_region)
            else:
                embedder = NomicEmbedder()

            try:
                issue_stream = gatherer.harvest_issues(repos)
                embedded_stream = embed_issue_stream(issue_stream, embedder)
                total = await persistence.persist_stream(embedded_stream)
            finally:
                embedder.close()

            logger.info(
                f"Pipeline complete: persisted {total} issues",
                extra={"issues_persisted": total},
            )

        return {
            "repos_discovered": len(repos),
            "issues_persisted": total,
        }

