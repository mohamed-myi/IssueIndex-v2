"""
Collector job: Scout repositories and gather issues to GCS.

This is Job 1 of the split pipeline:
1. Scout: Discover top repositories
2. Gather: Stream issues with Q-Score filtering
3. Store: Write to GCS as JSONL
4. Trigger: Start embedder job with the GCS path

Runs fast (10-15 minutes) because it skips embedding.
"""

import logging
import os
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
from ingestion.gatherer import Gatherer
from ingestion.gcs_storage import generate_batch_path, write_issues_to_gcs
from ingestion.github_client import GitHubGraphQLClient
from ingestion.persistence import StreamingPersistence
from ingestion.scout import Scout
from session import async_session_factory

logger = logging.getLogger(__name__)


def trigger_embedder_job(gcs_path: str, project: str, region: str) -> str | None:
    """
    Trigger the embedder job with the GCS path as input.
    Returns the execution name or None if trigger fails.
    """
    try:
        from google.cloud import run_v2

        client = run_v2.JobsClient()
        
        job_name = f"projects/{project}/locations/{region}/jobs/issueindex-embedder"
        
        request = run_v2.RunJobRequest(
            name=job_name,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(
                        env=[
                            run_v2.EnvVar(name="INPUT_GCS_PATH", value=gcs_path),
                        ]
                    )
                ]
            ),
        )
        
        operation = client.run_job(request=request)
        
        # Get execution name from operation metadata
        execution_name = operation.metadata.name if operation.metadata else "unknown"
        
        logger.info(
            f"Triggered embedder job: {execution_name}",
            extra={"execution_name": execution_name, "input_path": gcs_path},
        )
        
        return execution_name
        
    except Exception as e:
        logger.error(
            f"Failed to trigger embedder job: {e}",
            extra={"error": str(e), "gcs_path": gcs_path},
        )
        return None


async def run_collector_job() -> dict:
    """
    Executes the collection pipeline:
    1. Scout: Discover top repositories
    2. Gather: Stream issues with Q-Score filtering
    3. Store: Write to GCS as JSONL
    4. Trigger: Start embedder job
    
    Returns stats dict with repos_discovered, issues_collected, and gcs_path.
    """
    settings = get_settings()
    
    if not settings.git_token:
        raise ValueError("GIT_TOKEN environment variable is required")
    
    if not settings.gcs_bucket:
        raise ValueError("GCS_BUCKET environment variable is required")

    async with GitHubGraphQLClient(settings.git_token) as client:
        logger.info("Starting Scout: discovering repositories")
        scout = Scout(client)
        repos = await scout.discover_repositories()
        
        logger.info(
            f"Scout complete: discovered {len(repos)} repositories",
            extra={"repos_discovered": len(repos)},
        )

        if not repos:
            logger.warning("No repositories discovered; skipping collection")
            return {"repos_discovered": 0, "issues_collected": 0, "gcs_path": None}

        # Persist repositories first (FK constraint for issues)
        async with async_session_factory() as session:
            persistence = StreamingPersistence(session)
            repos_upserted = await persistence.upsert_repositories(repos)
            
            logger.info(
                f"Repositories upserted: {repos_upserted}",
                extra={"repos_upserted": repos_upserted},
            )

        # Generate GCS path for this batch
        gcs_path = generate_batch_path(settings.gcs_bucket)
        
        logger.info(
            f"Starting collection pipeline: Gather -> GCS",
            extra={"gcs_path": gcs_path},
        )
        
        # Gather issues and write to GCS
        gatherer = Gatherer(client, max_issues_per_repo=settings.max_issues_per_repo)
        issue_stream = gatherer.harvest_issues(repos)
        
        gcs_path, total = await write_issues_to_gcs(
            issues=issue_stream,
            gcs_path=gcs_path,
            log_every=500,
        )
        
        logger.info(
            f"Collection complete: {total} issues written to {gcs_path}",
            extra={"issues_collected": total, "gcs_path": gcs_path},
        )

        # Trigger embedder job
        if total > 0:
            execution_name = trigger_embedder_job(
                gcs_path=gcs_path,
                project=settings.gcp_project,
                region=settings.gcp_region,
            )
            
            if execution_name:
                logger.info(
                    f"Embedder job triggered successfully",
                    extra={"embedder_execution": execution_name},
                )
            else:
                logger.warning("Failed to trigger embedder job; manual trigger required")
        else:
            logger.warning("No issues collected; skipping embedder trigger")

        return {
            "repos_discovered": len(repos),
            "issues_collected": total,
            "gcs_path": gcs_path,
        }
