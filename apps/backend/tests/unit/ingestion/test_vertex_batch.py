"""Unit tests for Vertex AI Batch Prediction wrapper"""

from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.vertex_batch import (
    EMBEDDING_MODEL,
    BatchPredictionResult,
    VertexBatchEmbedder,
)


class TestBatchPredictionResult:
    def test_creates_with_required_fields(self):
        result = BatchPredictionResult(
            job_name="projects/p/locations/l/jobs/j",
            output_gcs_path="gs://bucket/output",
            state="SUCCEEDED",
        )
        
        assert result.job_name == "projects/p/locations/l/jobs/j"
        assert result.output_gcs_path == "gs://bucket/output"
        assert result.state == "SUCCEEDED"

    def test_optional_fields_default_to_none(self):
        result = BatchPredictionResult(
            job_name="job",
            output_gcs_path="path",
            state="SUCCEEDED",
        )
        
        assert result.input_count is None
        assert result.output_count is None
        assert result.error_message is None

    def test_creates_with_all_fields(self):
        result = BatchPredictionResult(
            job_name="job",
            output_gcs_path="path",
            state="FAILED",
            input_count=100,
            output_count=95,
            error_message="Quota exceeded",
        )
        
        assert result.input_count == 100
        assert result.output_count == 95
        assert result.error_message == "Quota exceeded"


class TestEmbeddingModel:
    def test_uses_text_embedding_004(self):
        assert EMBEDDING_MODEL == "publishers/google/models/text-embedding-004"


class TestVertexBatchEmbedder:
    @pytest.fixture
    def mock_aiplatform(self):
        with patch("src.ingestion.vertex_batch.aiplatform") as mock_ai:
            yield mock_ai

    def test_initializes_with_project_and_region(self, mock_aiplatform):
        embedder = VertexBatchEmbedder(project="my-project", region="us-east1")
        
        mock_aiplatform.init.assert_called_once_with(
            project="my-project",
            location="us-east1",
        )

    def test_default_region_is_us_central1(self, mock_aiplatform):
        embedder = VertexBatchEmbedder(project="my-project")
        
        mock_aiplatform.init.assert_called_once_with(
            project="my-project",
            location="us-central1",
        )


class TestSubmitBatchJob:
    @pytest.fixture
    def mock_aiplatform(self):
        with patch("src.ingestion.vertex_batch.aiplatform") as mock_ai:
            mock_job = MagicMock()
            mock_job.resource_name = "projects/p/locations/l/batchPredictionJobs/123"
            mock_ai.BatchPredictionJob.create.return_value = mock_job
            yield mock_ai

    @pytest.fixture
    def embedder(self, mock_aiplatform):
        return VertexBatchEmbedder(project="test-project")

    def test_returns_job_resource_name(self, embedder, mock_aiplatform):
        job_name = embedder.submit_batch_job(
            input_gcs_path="gs://bucket/input.jsonl",
            output_gcs_bucket="gs://bucket/output",
        )
        
        assert job_name == "projects/p/locations/l/batchPredictionJobs/123"

    def test_calls_batch_prediction_create(self, embedder, mock_aiplatform):
        embedder.submit_batch_job(
            input_gcs_path="gs://bucket/input.jsonl",
            output_gcs_bucket="gs://bucket/output",
        )
        
        mock_aiplatform.BatchPredictionJob.create.assert_called_once()

    def test_passes_model_name(self, embedder, mock_aiplatform):
        embedder.submit_batch_job(
            input_gcs_path="gs://bucket/input.jsonl",
            output_gcs_bucket="gs://bucket/output",
        )
        
        call_kwargs = mock_aiplatform.BatchPredictionJob.create.call_args[1]
        assert call_kwargs["model_name"] == EMBEDDING_MODEL

    def test_passes_gcs_source(self, embedder, mock_aiplatform):
        embedder.submit_batch_job(
            input_gcs_path="gs://my-bucket/my-input.jsonl",
            output_gcs_bucket="gs://output",
        )
        
        call_kwargs = mock_aiplatform.BatchPredictionJob.create.call_args[1]
        assert call_kwargs["gcs_source"] == "gs://my-bucket/my-input.jsonl"

    def test_passes_gcs_destination(self, embedder, mock_aiplatform):
        embedder.submit_batch_job(
            input_gcs_path="gs://input.jsonl",
            output_gcs_bucket="gs://my-bucket/output",
        )
        
        call_kwargs = mock_aiplatform.BatchPredictionJob.create.call_args[1]
        assert call_kwargs["gcs_destination_prefix"] == "gs://my-bucket/output"

    def test_uses_custom_job_name(self, embedder, mock_aiplatform):
        embedder.submit_batch_job(
            input_gcs_path="gs://input.jsonl",
            output_gcs_bucket="gs://output",
            job_display_name="custom-job",
        )
        
        call_kwargs = mock_aiplatform.BatchPredictionJob.create.call_args[1]
        assert call_kwargs["job_display_name"] == "custom-job"

    def test_generates_job_name_if_not_provided(self, embedder, mock_aiplatform):
        embedder.submit_batch_job(
            input_gcs_path="gs://input.jsonl",
            output_gcs_bucket="gs://output",
        )
        
        call_kwargs = mock_aiplatform.BatchPredictionJob.create.call_args[1]
        assert call_kwargs["job_display_name"].startswith("issueindex-embedding-")

    def test_sets_sync_false_for_async(self, embedder, mock_aiplatform):
        embedder.submit_batch_job(
            input_gcs_path="gs://input.jsonl",
            output_gcs_bucket="gs://output",
        )
        
        call_kwargs = mock_aiplatform.BatchPredictionJob.create.call_args[1]
        assert call_kwargs["sync"] is False

    def test_passes_model_parameters_for_embedding(self, embedder, mock_aiplatform):
        embedder.submit_batch_job(
            input_gcs_path="gs://input.jsonl",
            output_gcs_bucket="gs://output",
        )
        
        call_kwargs = mock_aiplatform.BatchPredictionJob.create.call_args[1]
        params = call_kwargs["model_parameters"]
        assert params["outputDimensionality"] == 768
        assert params["taskType"] == "RETRIEVAL_DOCUMENT"


class TestWaitForCompletion:
    @pytest.fixture
    def mock_aiplatform(self):
        with patch("src.ingestion.vertex_batch.aiplatform") as mock_ai:
            yield mock_ai

    @pytest.fixture
    def embedder(self, mock_aiplatform):
        return VertexBatchEmbedder(project="test-project")

    def test_returns_succeeded_result(self, embedder, mock_aiplatform):
        mock_job = MagicMock()
        mock_job.state.name = "JOB_STATE_SUCCEEDED"
        mock_job.output_info.gcs_output_directory = "gs://bucket/output/dir"
        mock_aiplatform.BatchPredictionJob.return_value = mock_job
        
        result = embedder.wait_for_completion(
            "job-name",
            poll_interval_seconds=0,
        )
        
        assert result.state == "SUCCEEDED"
        assert result.output_gcs_path == "gs://bucket/output/dir"

    def test_returns_failed_result(self, embedder, mock_aiplatform):
        mock_job = MagicMock()
        mock_job.state.name = "JOB_STATE_FAILED"
        mock_job.error = "Some error"
        mock_aiplatform.BatchPredictionJob.return_value = mock_job
        
        result = embedder.wait_for_completion(
            "job-name",
            poll_interval_seconds=0,
        )
        
        assert result.state == "JOB_STATE_FAILED"
        assert result.error_message == "Some error"

    def test_returns_cancelled_result(self, embedder, mock_aiplatform):
        mock_job = MagicMock()
        mock_job.state.name = "JOB_STATE_CANCELLED"
        mock_job.error = None
        mock_aiplatform.BatchPredictionJob.return_value = mock_job
        
        result = embedder.wait_for_completion(
            "job-name",
            poll_interval_seconds=0,
        )
        
        assert result.state == "JOB_STATE_CANCELLED"
        assert result.error_message == "Job failed"

    def test_returns_timeout_result(self, embedder, mock_aiplatform):
        mock_job = MagicMock()
        mock_job.state.name = "JOB_STATE_RUNNING"
        mock_aiplatform.BatchPredictionJob.return_value = mock_job
        
        result = embedder.wait_for_completion(
            "job-name",
            poll_interval_seconds=0,
            timeout_seconds=0,  # Immediate timeout
        )
        
        assert result.state == "TIMEOUT"
        assert "timed out" in result.error_message

    def test_polls_until_complete(self, embedder, mock_aiplatform):
        # Simulate running then succeeded
        mock_job = MagicMock()
        states = ["JOB_STATE_RUNNING", "JOB_STATE_RUNNING", "JOB_STATE_SUCCEEDED"]
        call_count = [0]
        
        def get_state():
            state = states[min(call_count[0], len(states) - 1)]
            call_count[0] += 1
            mock = MagicMock()
            mock.name = state
            return mock
        
        type(mock_job).state = property(lambda self: get_state())
        mock_job.output_info.gcs_output_directory = "gs://output"
        mock_aiplatform.BatchPredictionJob.return_value = mock_job
        
        with patch("src.ingestion.vertex_batch.time.sleep"):
            result = embedder.wait_for_completion(
                "job-name",
                poll_interval_seconds=0,
                timeout_seconds=100,
            )
        
        assert result.state == "SUCCEEDED"


class TestSubmitAndWait:
    @pytest.fixture
    def mock_aiplatform(self):
        with patch("src.ingestion.vertex_batch.aiplatform") as mock_ai:
            yield mock_ai

    @pytest.fixture
    def embedder(self, mock_aiplatform):
        return VertexBatchEmbedder(project="test-project")

    def test_combines_submit_and_wait(self, embedder, mock_aiplatform):
        # Setup submit
        mock_submit_job = MagicMock()
        mock_submit_job.resource_name = "job-123"
        mock_aiplatform.BatchPredictionJob.create.return_value = mock_submit_job
        
        # Setup wait
        mock_wait_job = MagicMock()
        mock_wait_job.state.name = "JOB_STATE_SUCCEEDED"
        mock_wait_job.output_info.gcs_output_directory = "gs://output"
        mock_aiplatform.BatchPredictionJob.return_value = mock_wait_job
        
        result = embedder.submit_and_wait(
            input_gcs_path="gs://input.jsonl",
            output_gcs_bucket="gs://output",
            poll_interval_seconds=0,
        )
        
        assert result.state == "SUCCEEDED"
        assert result.job_name == "job-123"

    def test_passes_timeout_to_wait(self, embedder, mock_aiplatform):
        mock_submit_job = MagicMock()
        mock_submit_job.resource_name = "job-123"
        mock_aiplatform.BatchPredictionJob.create.return_value = mock_submit_job
        
        mock_wait_job = MagicMock()
        mock_wait_job.state.name = "JOB_STATE_RUNNING"
        mock_aiplatform.BatchPredictionJob.return_value = mock_wait_job
        
        result = embedder.submit_and_wait(
            input_gcs_path="gs://input.jsonl",
            output_gcs_bucket="gs://output",
            poll_interval_seconds=0,
            timeout_seconds=0,  # Immediate timeout
        )
        
        assert result.state == "TIMEOUT"
