"""
Embedder job: Process pending issues from staging table.

Reads from staging.pending_issue, generates embeddings, writes to ingestion.issue.
Designed to run as a Cloud Run Job, scheduled after the Collector.
"""

import logging
import time
from datetime import datetime

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from gim_backend.core.config import get_settings
from gim_backend.ingestion.nomic_moe_embedder import NomicMoEEmbedder
from gim_backend.ingestion.staging_persistence import StagingPersistence
from gim_backend.ingestion.survival_score import calculate_survival_score, days_since
from gim_database.session import async_session_factory

logger = logging.getLogger(__name__)


async def run_embedder_job(embedder: NomicMoEEmbedder | None = None) -> dict:
    """
    Process pending issues from staging table.
    
    1. Claim batch of pending issues (atomic lock)
    2. Generate embeddings in batches
    3. Persist to ingestion.issue with survival score
    4. Mark staging records as completed
    
    Returns stats dict with issues_processed and issues_failed.
    """
    job_start = time.monotonic()
    settings = get_settings()
    batch_size = settings.embedder_batch_size
    
    logger.info(
        f"Embedder job starting with batch_size={batch_size}",
        extra={"batch_size": batch_size},
    )
    
    # Initialize embedder if not provided (for standalone testing)
    close_embedder = False
    if embedder is None:
        logger.info("Initializing NomicMoEEmbedder")
        embedder = NomicMoEEmbedder(max_workers=2)
        embedder.warmup()
        close_embedder = True
    
    total_processed = 0
    total_failed = 0
    
    try:
        # Process multiple batches until no pending issues remain
        while True:
            # Claim batch
            async with async_session_factory() as session:
                staging = StagingPersistence(session)
                pending_issues = await staging.claim_pending_batch(batch_size)
            
            if not pending_issues:
                logger.info("No pending issues to process")
                break
            
            logger.info(
                f"Processing batch of {len(pending_issues)} issues",
                extra={"batch_size": len(pending_issues)},
            )
            
            # Generate embeddings
            texts = [
                f"{issue['title']}\n{issue['body_text']}"
                for issue in pending_issues
            ]
            
            try:
                embeddings = await embedder.embed_documents(texts)
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")
                # Mark all as failed (will retry)
                async with async_session_factory() as session:
                    staging = StagingPersistence(session)
                    await staging.mark_failed([i["node_id"] for i in pending_issues])
                total_failed += len(pending_issues)
                continue
            
            if len(embeddings) != len(pending_issues):
                logger.error(
                    f"Embedding count mismatch: got {len(embeddings)}, expected {len(pending_issues)}"
                )
                async with async_session_factory() as session:
                    staging = StagingPersistence(session)
                    await staging.mark_failed([i["node_id"] for i in pending_issues])
                total_failed += len(pending_issues)
                continue
            
            # Persist to ingestion.issue
            succeeded_ids = []
            failed_ids = []
            
            async with async_session_factory() as session:
                for issue, embedding in zip(pending_issues, embeddings):
                    try:
                        await _persist_issue(session, issue, embedding)
                        succeeded_ids.append(issue["node_id"])
                    except Exception as e:
                        logger.warning(f"Failed to persist issue {issue['node_id']}: {e}")
                        failed_ids.append(issue["node_id"])
                
                await session.commit()
            
            # Update staging status
            async with async_session_factory() as session:
                staging = StagingPersistence(session)
                if succeeded_ids:
                    await staging.mark_completed(succeeded_ids)
                if failed_ids:
                    await staging.mark_failed(failed_ids)
            
            total_processed += len(succeeded_ids)
            total_failed += len(failed_ids)
            
            logger.info(
                f"Batch complete: {len(succeeded_ids)} succeeded, {len(failed_ids)} failed",
                extra={
                    "batch_succeeded": len(succeeded_ids),
                    "batch_failed": len(failed_ids),
                    "total_processed": total_processed,
                },
            )
    
    finally:
        if close_embedder:
            embedder.close()
    
    elapsed = time.monotonic() - job_start
    
    logger.info(
        f"Embedder job complete in {elapsed:.1f}s - {total_processed} processed, {total_failed} failed",
        extra={
            "total_processed": total_processed,
            "total_failed": total_failed,
            "duration_s": round(elapsed, 1),
        },
    )
    
    return {
        "issues_processed": total_processed,
        "issues_failed": total_failed,
        "duration_s": round(elapsed, 1),
    }


async def _persist_issue(
    session: AsyncSession,
    issue: dict,
    embedding: list[float],
) -> None:
    """Persist single issue with embedding to ingestion.issue table."""
    # Parse github_created_at
    github_created_at = issue.get("github_created_at")
    if isinstance(github_created_at, str):
        from datetime import UTC
        dt = datetime.fromisoformat(github_created_at.replace("Z", "+00:00"))
        github_created_at = dt.astimezone(UTC).replace(tzinfo=None)
    elif hasattr(github_created_at, 'replace'):
        # Already a datetime, ensure naive UTC
        github_created_at = github_created_at.replace(tzinfo=None)
    
    # Calculate survival score
    days_old = days_since(github_created_at)
    q_score = issue.get("q_score", 0.0)
    survival = calculate_survival_score(q_score, days_old)
    
    await session.execute(
        text("""
            INSERT INTO ingestion.issue (
                node_id, repo_id, has_code, has_template_headers,
                tech_stack_weight, q_score, survival_score, title,
                body_text, labels, embedding, content_hash, state,
                github_created_at
            )
            VALUES (
                :node_id, :repo_id, :has_code, :has_template_headers,
                :tech_stack_weight, :q_score, :survival_score, :title,
                :body_text, :labels, CAST(:embedding AS vector), :content_hash,
                :state, :github_created_at
            )
            ON CONFLICT (node_id) DO UPDATE SET
                repo_id = EXCLUDED.repo_id,
                has_code = EXCLUDED.has_code,
                has_template_headers = EXCLUDED.has_template_headers,
                tech_stack_weight = EXCLUDED.tech_stack_weight,
                q_score = EXCLUDED.q_score,
                survival_score = EXCLUDED.survival_score,
                title = EXCLUDED.title,
                body_text = EXCLUDED.body_text,
                labels = EXCLUDED.labels,
                embedding = EXCLUDED.embedding,
                content_hash = EXCLUDED.content_hash,
                state = EXCLUDED.state,
                github_created_at = EXCLUDED.github_created_at
        """),
        {
            "node_id": issue["node_id"],
            "repo_id": issue["repo_id"],
            "has_code": issue.get("has_code", False),
            "has_template_headers": issue.get("has_template_headers", False),
            "tech_stack_weight": issue.get("tech_stack_weight", 0.0),
            "q_score": q_score,
            "survival_score": survival,
            "title": issue["title"],
            "body_text": issue["body_text"],
            "labels": issue.get("labels", []),
            "embedding": str(embedding),
            "content_hash": issue["content_hash"],
            "state": issue.get("state", "open"),
            "github_created_at": github_created_at,
        },
    )
