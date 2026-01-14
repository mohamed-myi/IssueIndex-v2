"""Google Cloud Storage utilities for JSONL issue data"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from google.cloud import storage

if TYPE_CHECKING:
    from .gatherer import IssueData

logger = logging.getLogger(__name__)


def generate_batch_path(bucket_name: str, prefix: str = "issues") -> str:
    """Generate a unique GCS path for a batch of issues"""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"gs://{bucket_name}/{prefix}/batch_{timestamp}.jsonl"


def parse_gcs_path(gcs_path: str) -> tuple[str, str]:
    """Parse gs://bucket/path into (bucket, blob_path)"""
    if not gcs_path.startswith("gs://"):
        raise ValueError(f"Invalid GCS path: {gcs_path}")
    path = gcs_path[5:]  # Remove gs://
    parts = path.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid GCS path format: {gcs_path}")
    return parts[0], parts[1]


class GCSWriter:
    """
    Writes IssueData objects to GCS as JSONL with chunked buffering.

    Uses chunked uploads to prevent OOM on large batches by flushing to
    intermediate GCS blobs when buffer reaches threshold, then composing
    them into the final JSONL file.
    """

    DEFAULT_FLUSH_THRESHOLD: int = 5000

    def __init__(self, gcs_path: str, flush_threshold: int = 0):
        """Initialize GCSWriter with optional flush threshold.

        Args:
            gcs_path: Target GCS path for final JSONL file
            flush_threshold: Number of issues before flushing to intermediate blob.
                             0 means use DEFAULT_FLUSH_THRESHOLD.
        """
        self._gcs_path = gcs_path
        self._bucket_name, self._blob_path = parse_gcs_path(gcs_path)
        self._flush_threshold = flush_threshold if flush_threshold > 0 else self.DEFAULT_FLUSH_THRESHOLD
        self._buffer: list[str] = []
        self._count = 0
        self._chunk_paths: list[str] = []  # Track intermediate blob paths

    def write_issue(self, issue: IssueData) -> None:
        """Add an issue to the buffer, auto-flushing when threshold reached"""
        # Convert dataclass to dict, handling nested dataclasses
        issue_dict = asdict(issue)

        # Convert datetime to ISO string for JSON serialization
        if isinstance(issue_dict.get("github_created_at"), datetime):
            issue_dict["github_created_at"] = issue_dict["github_created_at"].isoformat()

        # Add content field for embedding (title + body)
        issue_dict["content"] = f"{issue.title}\n{issue.body_text}"

        self._buffer.append(json.dumps(issue_dict))
        self._count += 1

        # Auto-flush when threshold reached to bound memory usage
        if len(self._buffer) >= self._flush_threshold:
            self._flush_chunk()

    def _flush_chunk(self) -> None:
        """Upload current buffer as intermediate chunk blob"""
        if not self._buffer:
            return

        chunk_idx = len(self._chunk_paths)
        chunk_path = f"{self._blob_path}.chunk_{chunk_idx}"

        client = storage.Client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(chunk_path)

        content = "\n".join(self._buffer)
        blob.upload_from_string(content, content_type="application/jsonl")

        self._chunk_paths.append(chunk_path)
        buffer_size = len(self._buffer)
        self._buffer.clear()

        logger.info(
            f"GCS: Flushed chunk {chunk_idx} with {buffer_size} issues ({self._count} total)",
            extra={"chunk_idx": chunk_idx, "issues_in_chunk": buffer_size, "total_issues": self._count},
        )

    def upload(self) -> int:
        """Finalize upload - flush remaining buffer and compose chunks into final file"""
        if not self._buffer and not self._chunk_paths:
            logger.warning("No issues to upload to GCS")
            return 0

        # Flush any remaining buffered issues
        if self._buffer:
            self._flush_chunk()

        client = storage.Client()
        bucket = client.bucket(self._bucket_name)

        if len(self._chunk_paths) == 1:
            # Single chunk - just rename it to final path
            source_blob = bucket.blob(self._chunk_paths[0])
            bucket.rename_blob(source_blob, self._blob_path)
        else:
            # Multiple chunks - compose them into final blob
            final_blob = bucket.blob(self._blob_path)
            source_blobs = [bucket.blob(p) for p in self._chunk_paths]
            final_blob.compose(source_blobs)

            # Clean up intermediate chunks after successful compose
            for chunk_path in self._chunk_paths:
                bucket.blob(chunk_path).delete()

            logger.info(
                f"GCS: Composed {len(self._chunk_paths)} chunks into final file",
                extra={"chunk_count": len(self._chunk_paths)},
            )

        logger.info(
            f"Uploaded {self._count} issues to {self._gcs_path}",
            extra={
                "issues_uploaded": self._count,
                "gcs_path": self._gcs_path,
                "chunks_used": len(self._chunk_paths),
            },
        )

        return self._count

    @property
    def gcs_path(self) -> str:
        return self._gcs_path

    @property
    def count(self) -> int:
        return self._count

    @property
    def flush_threshold(self) -> int:
        return self._flush_threshold


class GCSReader:
    """Reads JSONL issue data from GCS"""

    def __init__(self, gcs_path: str):
        self._gcs_path = gcs_path
        self._bucket_name, self._blob_path = parse_gcs_path(gcs_path)

    def read_lines(self) -> Iterator[dict]:
        """Read and yield each line as a parsed dict"""
        client = storage.Client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._blob_path)

        content = blob.download_as_text()

        for line in content.strip().split("\n"):
            if line:
                yield json.loads(line)

    def count_lines(self) -> int:
        """Count total lines without loading all into memory"""
        return sum(1 for _ in self.read_lines())


async def write_issues_to_gcs(
    issues: AsyncIterator[IssueData],
    gcs_path: str,
    log_every: int = 500,
    flush_threshold: int = 0,
) -> tuple[str, int]:
    """
    Consume issue stream and write to GCS as JSONL.

    Args:
        issues: Async iterator of IssueData objects
        gcs_path: Target GCS path for final JSONL file
        log_every: Log progress every N issues
        flush_threshold: Issues before flushing to intermediate blob (0 = default)

    Returns:
        Tuple of (gcs_path, count)
    """
    writer = GCSWriter(gcs_path, flush_threshold=flush_threshold)

    async for issue in issues:
        writer.write_issue(issue)

        if writer.count % log_every == 0:
            logger.info(
                f"Collector progress: {writer.count} issues buffered",
                extra={"issues_buffered": writer.count},
            )

    count = writer.upload()
    return writer.gcs_path, count
