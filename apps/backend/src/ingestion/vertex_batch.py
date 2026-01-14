"""Vertex AI Batch Prediction wrapper for text embeddings"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from google.cloud import aiplatform

logger = logging.getLogger(__name__)

# Vertex AI text-embedding-004 model resource name
EMBEDDING_MODEL = "publishers/google/models/text-embedding-004"


@dataclass
class BatchPredictionResult:
    """Result of a batch prediction job"""
    job_name: str
    output_gcs_path: str
    state: str
    input_count: int | None = None
    output_count: int | None = None
    error_message: str | None = None


class VertexBatchEmbedder:
    """
    Submits embedding requests to Vertex AI Batch Prediction API.

    This is significantly faster than real-time API calls because:
    - Vertex AI handles parallelization internally
    - Optimized for throughput over latency
    - Can process thousands of texts in minutes
    """

    def __init__(self, project: str, region: str = "us-central1"):
        self._project = project
        self._region = region
        aiplatform.init(project=project, location=region)

    def submit_batch_job(
        self,
        input_gcs_path: str,
        output_gcs_bucket: str,
        job_display_name: str | None = None,
    ) -> str:
        """
        Submit a batch embedding job.

        Args:
            input_gcs_path: GCS path to JSONL file with 'content' field
            output_gcs_bucket: GCS bucket for output (gs://bucket-name)
            job_display_name: Optional display name for the job

        Returns:
            Job resource name for polling
        """
        if job_display_name is None:
            job_display_name = f"issueindex-embedding-{int(time.time())}"

        logger.info(
            f"Submitting batch embedding job: {job_display_name}",
            extra={
                "input_path": input_gcs_path,
                "output_bucket": output_gcs_bucket,
            },
        )

        # Create the batch prediction job
        batch_prediction_job = aiplatform.BatchPredictionJob.create(
            job_display_name=job_display_name,
            model_name=EMBEDDING_MODEL,
            gcs_source=input_gcs_path,
            gcs_destination_prefix=output_gcs_bucket,
            # text-embedding-004 specific parameters
            model_parameters={
                "outputDimensionality": 768,
                "taskType": "RETRIEVAL_DOCUMENT",
            },
            sync=False,  # Don't wait for completion
        )

        logger.info(
            f"Batch job submitted: {batch_prediction_job.resource_name}",
            extra={"job_name": batch_prediction_job.resource_name},
        )

        return batch_prediction_job.resource_name

    def wait_for_completion(
        self,
        job_name: str,
        poll_interval_seconds: int = 30,
        timeout_seconds: int = 7200,  # 2 hours
    ) -> BatchPredictionResult:
        """
        Poll for job completion.

        Args:
            job_name: Resource name from submit_batch_job
            poll_interval_seconds: How often to check status
            timeout_seconds: Maximum time to wait

        Returns:
            BatchPredictionResult with job details
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                return BatchPredictionResult(
                    job_name=job_name,
                    output_gcs_path="",
                    state="TIMEOUT",
                    error_message=f"Job timed out after {timeout_seconds}s",
                )

            job = aiplatform.BatchPredictionJob(job_name)
            state = job.state.name

            logger.info(
                f"Batch job status: {state} (elapsed: {int(elapsed)}s)",
                extra={"job_name": job_name, "state": state, "elapsed_seconds": int(elapsed)},
            )

            if state == "JOB_STATE_SUCCEEDED":
                # Get output location
                output_info = job.output_info
                output_gcs_path = output_info.gcs_output_directory if output_info else ""

                return BatchPredictionResult(
                    job_name=job_name,
                    output_gcs_path=output_gcs_path,
                    state="SUCCEEDED",
                )

            if state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED"):
                error_msg = getattr(job, "error", None)
                return BatchPredictionResult(
                    job_name=job_name,
                    output_gcs_path="",
                    state=state,
                    error_message=str(error_msg) if error_msg else "Job failed",
                )

            time.sleep(poll_interval_seconds)

    def submit_and_wait(
        self,
        input_gcs_path: str,
        output_gcs_bucket: str,
        job_display_name: str | None = None,
        poll_interval_seconds: int = 30,
        timeout_seconds: int = 7200,
    ) -> BatchPredictionResult:
        """
        Convenience method to submit and wait for completion.
        """
        job_name = self.submit_batch_job(
            input_gcs_path=input_gcs_path,
            output_gcs_bucket=output_gcs_bucket,
            job_display_name=job_display_name,
        )

        return self.wait_for_completion(
            job_name=job_name,
            poll_interval_seconds=poll_interval_seconds,
            timeout_seconds=timeout_seconds,
        )
