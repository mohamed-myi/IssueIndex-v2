"""Google Cloud Storage utilities for JSONL issue data"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Iterator
from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING

from google.cloud import storage

if TYPE_CHECKING:
    from .gatherer import IssueData

logger = logging.getLogger(__name__)


def generate_batch_path(bucket_name: str, prefix: str = "issues") -> str:
    """Generate a unique GCS path for a batch of issues"""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
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
    Writes IssueData objects to GCS as JSONL.
    Buffers in memory and uploads on close.
    """

    def __init__(self, gcs_path: str):
        self._gcs_path = gcs_path
        self._bucket_name, self._blob_path = parse_gcs_path(gcs_path)
        self._buffer: list[str] = []
        self._count = 0

    def write_issue(self, issue: IssueData) -> None:
        """Add an issue to the buffer"""
        # Convert dataclass to dict, handling nested dataclasses
        issue_dict = asdict(issue)
        
        # Convert datetime to ISO string for JSON serialization
        if isinstance(issue_dict.get("github_created_at"), datetime):
            issue_dict["github_created_at"] = issue_dict["github_created_at"].isoformat()
        
        # Add content field for embedding (title + body)
        issue_dict["content"] = f"{issue.title}\n{issue.body_text}"
        
        self._buffer.append(json.dumps(issue_dict))
        self._count += 1

    def upload(self) -> int:
        """Upload buffered data to GCS and return count"""
        if not self._buffer:
            logger.warning("No issues to upload to GCS")
            return 0

        client = storage.Client()
        bucket = client.bucket(self._bucket_name)
        blob = bucket.blob(self._blob_path)

        # Join all lines with newlines
        content = "\n".join(self._buffer)
        
        blob.upload_from_string(content, content_type="application/jsonl")
        
        logger.info(
            f"Uploaded {self._count} issues to {self._gcs_path}",
            extra={"issues_uploaded": self._count, "gcs_path": self._gcs_path},
        )
        
        return self._count

    @property
    def gcs_path(self) -> str:
        return self._gcs_path

    @property
    def count(self) -> int:
        return self._count


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
) -> tuple[str, int]:
    """
    Consume issue stream and write to GCS as JSONL.
    Returns (gcs_path, count).
    """
    writer = GCSWriter(gcs_path)
    
    async for issue in issues:
        writer.write_issue(issue)
        
        if writer.count % log_every == 0:
            logger.info(
                f"Collector progress: {writer.count} issues buffered",
                extra={"issues_buffered": writer.count},
            )
    
    count = writer.upload()
    return writer.gcs_path, count
