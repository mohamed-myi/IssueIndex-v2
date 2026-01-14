"""
Embedder job: Generate embeddings via Vertex AI Batch Prediction and persist.

This is Job 2 of the split pipeline:
1. Read: Get JSONL file path from INPUT_GCS_PATH env var
2. Submit: Send to Vertex AI Batch Prediction API
3. Poll: Wait for completion
4. Persist: Load embeddings and write to database

Uses Vertex AI Batch Prediction for massive parallelization.
Can process thousands of issues in minutes vs hours with real-time API.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add backend src to path
backend_src = Path(__file__).parent.parent.parent.parent / "backend" / "src"
if str(backend_src) not in sys.path:
    sys.path.insert(0, str(backend_src))

# Add packages to path
packages_db = Path(__file__).parent.parent.parent.parent.parent / "packages" / "database" / "src"
if str(packages_db) not in sys.path:
    sys.path.insert(0, str(packages_db))

from google.cloud import storage
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config import get_settings
from ingestion.gcs_storage import GCSReader, parse_gcs_path
from ingestion.survival_score import calculate_survival_score, days_since
from ingestion.vertex_batch import VertexBatchEmbedder
from session import async_session_factory

logger = logging.getLogger(__name__)


def read_batch_output(output_gcs_dir: str) -> dict[str, list[float]]:
    """
    Read Vertex AI batch prediction output and return node_id -> embedding mapping.
    
    Vertex AI writes output as JSONL files in the output directory.
    Each line contains the original input plus 'predictions' field with embeddings.
    """
    client = storage.Client()
    
    # Parse the output directory path
    bucket_name, prefix = parse_gcs_path(output_gcs_dir)
    bucket = client.bucket(bucket_name)
    
    embeddings_map: dict[str, list[float]] = {}
    files_processed = 0
    
    # List all output files in the directory
    blobs = bucket.list_blobs(prefix=prefix)
    
    for blob in blobs:
        if not blob.name.endswith(".jsonl"):
            continue
            
        files_processed += 1
        content = blob.download_as_text()
        
        for line in content.strip().split("\n"):
            if not line:
                continue
                
            try:
                record = json.loads(line)
                node_id = record.get("node_id")
                
                # Vertex AI returns embeddings in 'predictions' or 'embedding' field
                predictions = record.get("predictions", {})
                embedding = (
                    predictions.get("embeddings", {}).get("values")
                    or predictions.get("values")
                    or record.get("embedding")
                )
                
                if node_id and embedding:
                    embeddings_map[node_id] = embedding
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse output line: {e}")
                continue
    
    logger.info(
        f"Read {len(embeddings_map)} embeddings from {files_processed} output files",
        extra={"embeddings_count": len(embeddings_map), "files_count": files_processed},
    )
    
    return embeddings_map


async def persist_embeddings(
    input_gcs_path: str,
    embeddings_map: dict[str, list[float]],
    session: AsyncSession,
    batch_size: int = 50,
) -> int:
    """
    Read original issue data from input file and persist with embeddings.
    Returns count of issues persisted.
    """
    reader = GCSReader(input_gcs_path)
    
    batch: list[dict] = []
    total = 0
    skipped = 0
    
    for issue_data in reader.read_lines():
        node_id = issue_data.get("node_id")
        
        if node_id not in embeddings_map:
            skipped += 1
            continue
        
        issue_data["embedding"] = embeddings_map[node_id]
        batch.append(issue_data)
        
        if len(batch) >= batch_size:
            await _upsert_batch(batch, session)
            total += len(batch)
            
            if total % 500 == 0:
                logger.info(
                    f"Persistence progress: {total} issues persisted",
                    extra={"issues_persisted": total},
                )
            
            batch.clear()
    
    # Final batch
    if batch:
        await _upsert_batch(batch, session)
        total += len(batch)
    
    if skipped > 0:
        logger.warning(
            f"Skipped {skipped} issues without embeddings",
            extra={"skipped_count": skipped},
        )
    
    logger.info(
        f"Persisted {total} issues to database",
        extra={"issues_persisted": total},
    )
    
    return total


async def _upsert_batch(batch: list[dict], session: AsyncSession) -> None:
    """UPSERT a batch of issues with embeddings"""
    if not batch:
        return

    values_list = []
    params = {}

    for i, issue_data in enumerate(batch):
        # Parse github_created_at if it's a string
        github_created_at = issue_data.get("github_created_at")
        if isinstance(github_created_at, str):
            github_created_at = datetime.fromisoformat(github_created_at.replace("Z", "+00:00"))
        
        # Calculate survival score
        q_score = issue_data.get("q_score", 0.0)
        days_old = days_since(github_created_at) if github_created_at else 0
        survival = calculate_survival_score(q_score, days_old)
        
        # Get q_components fields
        q_components = issue_data.get("q_components", {})

        values_list.append(
            f"(:node_id_{i}, :repo_id_{i}, :has_code_{i}, :has_template_headers_{i}, "
            f":tech_stack_weight_{i}, :q_score_{i}, :survival_score_{i}, :title_{i}, "
            f":body_text_{i}, :labels_{i}, CAST(:embedding_{i} AS vector), :github_created_at_{i}, :state_{i})"
        )

        params[f"node_id_{i}"] = issue_data.get("node_id")
        params[f"repo_id_{i}"] = issue_data.get("repo_id")
        params[f"has_code_{i}"] = q_components.get("has_code", False)
        params[f"has_template_headers_{i}"] = q_components.get("has_headers", False)
        params[f"tech_stack_weight_{i}"] = q_components.get("tech_weight", 0.0)
        params[f"q_score_{i}"] = q_score
        params[f"survival_score_{i}"] = survival
        params[f"title_{i}"] = issue_data.get("title", "")
        params[f"body_text_{i}"] = issue_data.get("body_text", "")
        params[f"labels_{i}"] = issue_data.get("labels", [])
        params[f"embedding_{i}"] = str(issue_data.get("embedding", []))
        params[f"github_created_at_{i}"] = github_created_at
        params[f"state_{i}"] = issue_data.get("state", "open")

    values_sql = ", ".join(values_list)

    query = text(f"""
        INSERT INTO ingestion.issue
            (node_id, repo_id, has_code, has_template_headers, tech_stack_weight,
             q_score, survival_score, title, body_text, labels, embedding, github_created_at, state)
        VALUES {values_sql}
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
            github_created_at = EXCLUDED.github_created_at,
            state = EXCLUDED.state
    """)

    await session.execute(query, params)
    await session.commit()


async def run_embedder_job() -> dict:
    """
    Executes the embedding pipeline:
    1. Read input GCS path from environment
    2. Submit to Vertex AI Batch Prediction
    3. Wait for completion
    4. Persist embeddings to database
    
    Returns stats dict with issues_embedded and any errors.
    """
    job_start = time.monotonic()
    settings = get_settings()
    
    input_gcs_path = os.environ.get("INPUT_GCS_PATH")
    if not input_gcs_path:
        raise ValueError("INPUT_GCS_PATH environment variable is required")
    
    if not settings.gcs_bucket:
        raise ValueError("GCS_BUCKET environment variable is required")

    logger.info(
        "Phase 1/3: Starting embedder job",
        extra={"input_path": input_gcs_path},
    )

    # Phase 1: Submit batch prediction job
    submit_start = time.monotonic()
    embedder = VertexBatchEmbedder(
        project=settings.gcp_project,
        region=settings.gcp_region,
    )
    
    output_bucket = f"gs://{settings.gcs_bucket}/embeddings"
    
    logger.info(
        "Phase 1/3: Submitting to Vertex AI Batch Prediction",
        extra={"output_bucket": output_bucket},
    )
    
    result = embedder.submit_and_wait(
        input_gcs_path=input_gcs_path,
        output_gcs_bucket=output_bucket,
        poll_interval_seconds=30,
        timeout_seconds=7200,  # 2 hours
    )
    submit_elapsed = time.monotonic() - submit_start
    
    if result.state != "SUCCEEDED":
        logger.error(
            f"Phase 1/3: Batch prediction failed after {submit_elapsed:.1f}s: {result.state}",
            extra={
                "state": result.state,
                "error": result.error_message,
                "duration_s": round(submit_elapsed, 1),
            },
        )
        return {
            "state": result.state,
            "error": result.error_message,
            "issues_embedded": 0,
            "duration_s": round(time.monotonic() - job_start, 1),
        }
    
    logger.info(
        f"Phase 1/3: Batch prediction complete in {submit_elapsed:.1f}s",
        extra={
            "output_path": result.output_gcs_path,
            "batch_duration_s": round(submit_elapsed, 1),
        },
    )
    
    # Phase 2: Read embeddings from output
    read_start = time.monotonic()
    logger.info(f"Phase 2/3: Reading embeddings from {result.output_gcs_path}")
    embeddings_map = read_batch_output(result.output_gcs_path)
    read_elapsed = time.monotonic() - read_start
    
    if not embeddings_map:
        logger.error("Phase 2/3: No embeddings found in batch output")
        return {
            "state": "NO_EMBEDDINGS",
            "error": "Batch output contained no embeddings",
            "issues_embedded": 0,
            "duration_s": round(time.monotonic() - job_start, 1),
        }
    
    logger.info(
        f"Phase 2/3: Read {len(embeddings_map)} embeddings in {read_elapsed:.1f}s",
        extra={
            "embeddings_count": len(embeddings_map),
            "read_duration_s": round(read_elapsed, 1),
        },
    )
    
    # Phase 3: Persist to database
    persist_start = time.monotonic()
    logger.info(f"Phase 3/3: Persisting {len(embeddings_map)} issues to database")
    
    async with async_session_factory() as session:
        total = await persist_embeddings(
            input_gcs_path=input_gcs_path,
            embeddings_map=embeddings_map,
            session=session,
        )
    persist_elapsed = time.monotonic() - persist_start
    
    job_elapsed = time.monotonic() - job_start
    logger.info(
        f"Embedder job complete in {job_elapsed:.1f}s: {total} issues persisted",
        extra={
            "issues_embedded": total,
            "total_duration_s": round(job_elapsed, 1),
            "batch_duration_s": round(submit_elapsed, 1),
            "read_duration_s": round(read_elapsed, 1),
            "persist_duration_s": round(persist_elapsed, 1),
        },
    )
    
    return {
        "state": "SUCCEEDED",
        "issues_embedded": total,
        "input_path": input_gcs_path,
        "output_path": result.output_gcs_path,
        "duration_s": round(job_elapsed, 1),
    }
