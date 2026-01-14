"""Unit tests for GCS storage utilities"""

import json
import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

# Mock google.cloud.storage before importing the module
mock_storage = MagicMock()
sys.modules["google.cloud.storage"] = mock_storage
sys.modules["google.cloud"] = MagicMock()

from src.ingestion.gcs_storage import (
    GCSReader,
    GCSWriter,
    generate_batch_path,
    parse_gcs_path,
)


class TestGenerateBatchPath:
    def test_returns_gs_prefix(self):
        path = generate_batch_path("my-bucket")
        
        assert path.startswith("gs://my-bucket/")

    def test_includes_issues_prefix_by_default(self):
        path = generate_batch_path("my-bucket")
        
        assert "/issues/batch_" in path

    def test_uses_custom_prefix(self):
        path = generate_batch_path("my-bucket", prefix="custom")
        
        assert "/custom/batch_" in path

    def test_includes_timestamp(self):
        path = generate_batch_path("my-bucket")
        
        # Format: batch_YYYYMMDD_HHMMSS.jsonl
        assert path.endswith(".jsonl")
        parts = path.split("batch_")[1].replace(".jsonl", "")
        assert len(parts) == 15  # YYYYMMDD_HHMMSS

    def test_successive_calls_produce_unique_paths(self):
        # Timestamps within same second might collide but paths should still be generated
        path1 = generate_batch_path("bucket")
        path2 = generate_batch_path("bucket")
        
        assert path1.startswith("gs://bucket/")
        assert path2.startswith("gs://bucket/")


class TestParseGcsPath:
    def test_parses_simple_path(self):
        bucket, blob = parse_gcs_path("gs://my-bucket/path/to/file.jsonl")
        
        assert bucket == "my-bucket"
        assert blob == "path/to/file.jsonl"

    def test_parses_single_level_path(self):
        bucket, blob = parse_gcs_path("gs://bucket/file.txt")
        
        assert bucket == "bucket"
        assert blob == "file.txt"

    def test_parses_deep_path(self):
        bucket, blob = parse_gcs_path("gs://bucket/a/b/c/d/e.jsonl")
        
        assert bucket == "bucket"
        assert blob == "a/b/c/d/e.jsonl"

    def test_raises_on_missing_gs_prefix(self):
        with pytest.raises(ValueError, match="Invalid GCS path"):
            parse_gcs_path("my-bucket/file.txt")

    def test_raises_on_http_prefix(self):
        with pytest.raises(ValueError, match="Invalid GCS path"):
            parse_gcs_path("https://storage.googleapis.com/bucket/file.txt")

    def test_raises_on_bucket_only(self):
        with pytest.raises(ValueError, match="Invalid GCS path format"):
            parse_gcs_path("gs://bucket-only")


class TestGCSWriter:
    @pytest.fixture
    def mock_storage_client(self):
        with patch("src.ingestion.gcs_storage.storage") as mock_storage:
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()

            mock_storage.Client.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob

            yield {
                "storage": mock_storage,
                "client": mock_client,
                "bucket": mock_bucket,
                "blob": mock_blob,
            }

    @pytest.fixture
    def sample_issue_data(self):
        """Create a real IssueData dataclass instance for testing"""
        from src.ingestion.gatherer import IssueData
        from src.ingestion.quality_gate import QScoreComponents

        return IssueData(
            node_id="I_123",
            repo_id="R_456",
            title="Test Issue",
            body_text="Test body content",
            labels=["bug"],
            github_created_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
            q_score=0.75,
            q_components=QScoreComponents(
                has_code=True,
                has_headers=True,
                tech_weight=0.5,
                is_junk=False,
            ),
            state="open",
        )

    def test_initializes_with_gcs_path(self):
        writer = GCSWriter("gs://bucket/path/file.jsonl")
        
        assert writer.gcs_path == "gs://bucket/path/file.jsonl"
        assert writer.count == 0

    def test_count_starts_at_zero(self):
        writer = GCSWriter("gs://bucket/file.jsonl")
        
        assert writer.count == 0

    def test_write_issue_increments_count(self, sample_issue_data):
        writer = GCSWriter("gs://bucket/file.jsonl")
        
        writer.write_issue(sample_issue_data)
        
        assert writer.count == 1

    def test_write_multiple_issues_increments_correctly(self, sample_issue_data):
        writer = GCSWriter("gs://bucket/file.jsonl")
        
        for _ in range(5):
            writer.write_issue(sample_issue_data)
        
        assert writer.count == 5

    def test_upload_returns_count(self, mock_storage_client, sample_issue_data):
        writer = GCSWriter("gs://bucket/file.jsonl")
        writer.write_issue(sample_issue_data)
        writer.write_issue(sample_issue_data)
        
        count = writer.upload()
        
        assert count == 2

    def test_upload_calls_storage_client(self, mock_storage_client, sample_issue_data):
        writer = GCSWriter("gs://my-bucket/path/file.jsonl")
        writer.write_issue(sample_issue_data)
        
        writer.upload()
        
        # With chunked buffering, storage client is called for chunk upload
        mock_storage_client["storage"].Client.assert_called()
        mock_storage_client["client"].bucket.assert_called_with("my-bucket")
        # First blob call is for the chunk, then rename_blob moves it to final path
        mock_storage_client["bucket"].blob.assert_called_with("path/file.jsonl.chunk_0")

    def test_upload_writes_jsonl_content(self, mock_storage_client, sample_issue_data):
        writer = GCSWriter("gs://bucket/file.jsonl")
        writer.write_issue(sample_issue_data)
        
        writer.upload()
        
        blob = mock_storage_client["blob"]
        blob.upload_from_string.assert_called_once()
        
        # Check content type
        call_args = blob.upload_from_string.call_args
        assert call_args[1]["content_type"] == "application/jsonl"

    def test_upload_empty_returns_zero(self, mock_storage_client):
        writer = GCSWriter("gs://bucket/file.jsonl")
        
        count = writer.upload()
        
        assert count == 0
        mock_storage_client["storage"].Client.assert_not_called()

    def test_write_issue_adds_content_field(self, sample_issue_data):
        """Verify content field is added for embedding"""
        writer = GCSWriter("gs://bucket/file.jsonl")
        writer.write_issue(sample_issue_data)
        
        # Check the buffer contains content field
        line = json.loads(writer._buffer[0])
        assert "content" in line
        assert sample_issue_data.title in line["content"]
        assert sample_issue_data.body_text in line["content"]

    def test_gcs_path_property(self):
        writer = GCSWriter("gs://bucket/path/file.jsonl")
        
        assert writer.gcs_path == "gs://bucket/path/file.jsonl"


class TestGCSReader:
    @pytest.fixture
    def mock_storage_client(self):
        with patch("src.ingestion.gcs_storage.storage") as mock_storage:
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            mock_blob = MagicMock()
            
            mock_storage.Client.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.return_value = mock_blob
            
            yield {
                "storage": mock_storage,
                "client": mock_client,
                "bucket": mock_bucket,
                "blob": mock_blob,
            }

    def test_initializes_with_gcs_path(self):
        reader = GCSReader("gs://bucket/file.jsonl")
        
        assert reader._gcs_path == "gs://bucket/file.jsonl"

    def test_read_lines_yields_dicts(self, mock_storage_client):
        mock_storage_client["blob"].download_as_text.return_value = (
            '{"node_id": "I_1", "title": "Issue 1"}\n'
            '{"node_id": "I_2", "title": "Issue 2"}'
        )
        
        reader = GCSReader("gs://bucket/file.jsonl")
        lines = list(reader.read_lines())
        
        assert len(lines) == 2
        assert lines[0]["node_id"] == "I_1"
        assert lines[1]["title"] == "Issue 2"

    def test_read_lines_skips_empty_lines(self, mock_storage_client):
        mock_storage_client["blob"].download_as_text.return_value = (
            '{"node_id": "I_1"}\n'
            '\n'
            '{"node_id": "I_2"}\n'
        )
        
        reader = GCSReader("gs://bucket/file.jsonl")
        lines = list(reader.read_lines())
        
        assert len(lines) == 2

    def test_read_lines_calls_storage_client(self, mock_storage_client):
        mock_storage_client["blob"].download_as_text.return_value = '{"node_id": "I_1"}'
        
        reader = GCSReader("gs://my-bucket/path/file.jsonl")
        list(reader.read_lines())
        
        mock_storage_client["storage"].Client.assert_called_once()
        mock_storage_client["client"].bucket.assert_called_with("my-bucket")
        mock_storage_client["bucket"].blob.assert_called_with("path/file.jsonl")

    def test_count_lines_returns_correct_count(self, mock_storage_client):
        mock_storage_client["blob"].download_as_text.return_value = (
            '{"id": 1}\n{"id": 2}\n{"id": 3}'
        )
        
        reader = GCSReader("gs://bucket/file.jsonl")
        count = reader.count_lines()
        
        assert count == 3

    def test_count_lines_returns_zero_for_empty(self, mock_storage_client):
        mock_storage_client["blob"].download_as_text.return_value = ""
        
        reader = GCSReader("gs://bucket/file.jsonl")
        count = reader.count_lines()
        
        assert count == 0


class TestWriteIssuesToGcs:
    @pytest.fixture
    def mock_gcs_writer(self):
        with patch("src.ingestion.gcs_storage.GCSWriter") as mock_writer_class:
            mock_writer = MagicMock()
            mock_writer.gcs_path = "gs://bucket/test.jsonl"
            mock_writer.count = 0
            mock_writer.upload.return_value = 3
            mock_writer_class.return_value = mock_writer
            
            yield {"class": mock_writer_class, "instance": mock_writer}

    @pytest.mark.asyncio
    async def test_writes_all_issues(self, mock_gcs_writer):
        from src.ingestion.gcs_storage import write_issues_to_gcs

        class MockIssue:
            title = "Test"
            body_text = "Body"

        async def issue_stream():
            for _ in range(3):
                yield MockIssue()

        mock_gcs_writer["instance"].upload.return_value = 3

        path, count = await write_issues_to_gcs(
            issue_stream(),
            "gs://bucket/test.jsonl",
        )

        assert count == 3
        assert path == "gs://bucket/test.jsonl"
        assert mock_gcs_writer["instance"].write_issue.call_count == 3

    @pytest.mark.asyncio
    async def test_returns_gcs_path(self, mock_gcs_writer):
        from src.ingestion.gcs_storage import write_issues_to_gcs

        async def empty_stream():
            return
            yield

        mock_gcs_writer["instance"].upload.return_value = 0

        path, _ = await write_issues_to_gcs(
            empty_stream(),
            "gs://bucket/output.jsonl",
        )

        assert path == "gs://bucket/test.jsonl"


class TestChunkedBuffering:
    """Tests for PERF-004: chunked buffering in GCSWriter to prevent OOM"""

    @pytest.fixture
    def mock_storage_client(self):
        with patch("src.ingestion.gcs_storage.storage") as mock_storage:
            mock_client = MagicMock()
            mock_bucket = MagicMock()

            # Track blobs created for each path
            blobs = {}

            def get_blob(path):
                if path not in blobs:
                    blob = MagicMock()
                    blob.path = path
                    blobs[path] = blob
                return blobs[path]

            mock_storage.Client.return_value = mock_client
            mock_client.bucket.return_value = mock_bucket
            mock_bucket.blob.side_effect = get_blob

            yield {
                "storage": mock_storage,
                "client": mock_client,
                "bucket": mock_bucket,
                "blobs": blobs,
            }

    @pytest.fixture
    def sample_issue_data(self):
        """Create a real IssueData dataclass instance for testing"""
        from src.ingestion.gatherer import IssueData
        from src.ingestion.quality_gate import QScoreComponents

        return IssueData(
            node_id="I_123",
            repo_id="R_456",
            title="Test Issue",
            body_text="Test body content",
            labels=["bug"],
            github_created_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
            q_score=0.75,
            q_components=QScoreComponents(
                has_code=True,
                has_headers=True,
                tech_weight=0.5,
                is_junk=False,
            ),
            state="open",
        )

    def test_flush_threshold_configurable(self):
        # Arrange & Act
        writer_default = GCSWriter("gs://bucket/file.jsonl")
        writer_custom = GCSWriter("gs://bucket/file.jsonl", flush_threshold=100)
        writer_zero = GCSWriter("gs://bucket/file.jsonl", flush_threshold=0)

        # Assert - default should be 5000, custom should be 100, zero should fallback to default
        assert writer_default.flush_threshold == 5000
        assert writer_custom.flush_threshold == 100
        assert writer_zero.flush_threshold == 5000

    def test_flushes_buffer_at_threshold(self, mock_storage_client, sample_issue_data):
        # Arrange - create writer with small threshold of 3
        writer = GCSWriter("gs://bucket/path/file.jsonl", flush_threshold=3)

        # Act - write 5 issues (should trigger 1 flush at 3, leaving 2 in buffer)
        for _ in range(5):
            writer.write_issue(sample_issue_data)

        # Assert - should have flushed once when hitting threshold
        assert len(writer._chunk_paths) == 1
        assert len(writer._buffer) == 2  # Remaining 2 issues still in buffer
        assert writer.count == 5

        # Verify chunk blob was created and uploaded
        chunk_path = "path/file.jsonl.chunk_0"
        chunk_blob = mock_storage_client["blobs"][chunk_path]
        chunk_blob.upload_from_string.assert_called_once()

    def test_composes_multiple_chunks_into_final(self, mock_storage_client, sample_issue_data):
        # Arrange - create writer with small threshold to trigger multiple chunks
        writer = GCSWriter("gs://bucket/path/file.jsonl", flush_threshold=2)

        # Act - write 5 issues (2 chunks of 2, plus 1 remaining)
        for _ in range(5):
            writer.write_issue(sample_issue_data)

        # Should have 2 chunks flushed, 1 issue remaining in buffer
        assert len(writer._chunk_paths) == 2
        assert len(writer._buffer) == 1

        # Upload should compose all chunks
        count = writer.upload()

        # Assert
        assert count == 5
        # After upload, should have 3 chunks total (2 + final flush of 1)
        assert len(writer._chunk_paths) == 3

        # Verify compose was called on the final blob
        final_blob = mock_storage_client["blobs"]["path/file.jsonl"]
        final_blob.compose.assert_called_once()

    def test_cleans_up_intermediate_chunks(self, mock_storage_client, sample_issue_data):
        # Arrange - create writer that will produce multiple chunks
        writer = GCSWriter("gs://bucket/path/file.jsonl", flush_threshold=2)

        # Act - write enough issues to create multiple chunks
        for _ in range(5):
            writer.write_issue(sample_issue_data)

        writer.upload()

        # Assert - verify delete was called on intermediate chunk blobs
        chunk_paths = [
            "path/file.jsonl.chunk_0",
            "path/file.jsonl.chunk_1",
            "path/file.jsonl.chunk_2",
        ]

        for chunk_path in chunk_paths:
            chunk_blob = mock_storage_client["blobs"][chunk_path]
            chunk_blob.delete.assert_called_once()

    def test_small_batches_under_threshold_use_rename(self, mock_storage_client, sample_issue_data):
        # Arrange - create writer with threshold larger than issue count
        writer = GCSWriter("gs://bucket/path/file.jsonl", flush_threshold=100)

        # Act - write fewer issues than threshold
        for _ in range(5):
            writer.write_issue(sample_issue_data)

        writer.upload()

        # Assert - should use rename since only one chunk
        mock_storage_client["bucket"].rename_blob.assert_called_once()

        # Compose should NOT be called since only one chunk
        final_blob = mock_storage_client["blobs"].get("path/file.jsonl")
        if final_blob:
            final_blob.compose.assert_not_called()

    def test_upload_with_no_issues_returns_zero(self, mock_storage_client):
        # Arrange
        writer = GCSWriter("gs://bucket/path/file.jsonl")

        # Act
        count = writer.upload()

        # Assert
        assert count == 0
        mock_storage_client["storage"].Client.assert_not_called()

    def test_buffer_cleared_after_flush(self, mock_storage_client, sample_issue_data):
        # Arrange
        writer = GCSWriter("gs://bucket/path/file.jsonl", flush_threshold=3)

        # Act - write exactly threshold issues to trigger flush
        for _ in range(3):
            writer.write_issue(sample_issue_data)

        # Assert - buffer should be empty after flush
        assert len(writer._buffer) == 0
        assert len(writer._chunk_paths) == 1
        assert writer.count == 3

    def test_multiple_flushes_increment_chunk_index(self, mock_storage_client, sample_issue_data):
        # Arrange
        writer = GCSWriter("gs://bucket/path/file.jsonl", flush_threshold=2)

        # Act - write 6 issues to trigger 3 flushes
        for _ in range(6):
            writer.write_issue(sample_issue_data)

        # Assert - should have 3 chunks
        assert len(writer._chunk_paths) == 3
        assert writer._chunk_paths[0] == "path/file.jsonl.chunk_0"
        assert writer._chunk_paths[1] == "path/file.jsonl.chunk_1"
        assert writer._chunk_paths[2] == "path/file.jsonl.chunk_2"

    def test_flush_threshold_property_exposed(self):
        # Arrange & Act
        writer = GCSWriter("gs://bucket/file.jsonl", flush_threshold=1000)

        # Assert
        assert writer.flush_threshold == 1000

    def test_content_preserved_across_chunks(self, mock_storage_client, sample_issue_data):
        # Arrange - track all uploaded content
        uploaded_contents = []

        def capture_upload(content, **kwargs):
            uploaded_contents.append(content)

        writer = GCSWriter("gs://bucket/path/file.jsonl", flush_threshold=2)

        # Make blobs capture their upload content
        for blob in mock_storage_client["blobs"].values():
            blob.upload_from_string.side_effect = capture_upload

        # Act - write 4 issues (should create 2 chunks)
        for i in range(4):
            writer.write_issue(sample_issue_data)

        # Assert - each chunk should contain serialized issues
        assert len(writer._chunk_paths) == 2

        # Each flush should have uploaded JSON content
        for content in uploaded_contents:
            # Content should be JSONL format (JSON objects separated by newlines)
            lines = content.strip().split("\n")
            for line in lines:
                parsed = json.loads(line)
                assert "node_id" in parsed
                assert "content" in parsed
