"""
In-memory retry queue for embedding operations.
Implements exponential backoff with configurable max retries.
For local development; production will use Cloud Tasks.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    INTENT_VECTOR = "intent_vector"
    RESUME_VECTOR = "resume_vector"
    GITHUB_VECTOR = "github_vector"
    COMBINED_VECTOR = "combined_vector"


@dataclass
class RetryJob:
    id: UUID
    job_type: JobType
    user_id: UUID
    payload: dict[str, Any]
    status: JobStatus = JobStatus.QUEUED
    attempt: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_attempt_at: Optional[datetime] = None
    error_message: Optional[str] = None


class RetryQueue:
    """
    Asyncio-based in-memory queue with exponential backoff.
    
    State Machine:
        queued -> processing -> completed
                            |-> failed (after max_retries)
                            |-> cancelled (if profile deleted)
    
    Backoff formula: 2^attempt seconds (1s, 2s, 4s)
    """
    
    def __init__(self):
        self._queue: asyncio.Queue[RetryJob] = asyncio.Queue()
        self._jobs: dict[UUID, RetryJob] = {}
        self._cancelled_users: set[UUID] = set()
        self._handlers: dict[JobType, Callable[..., Coroutine[Any, Any, Any]]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def register_handler(
        self,
        job_type: JobType,
        handler: Callable[..., Coroutine[Any, Any, Any]],
    ) -> None:
        """Registers an async handler for a job type."""
        self._handlers[job_type] = handler
        logger.info(f"Registered handler for {job_type.value}")
    
    async def enqueue(
        self,
        job_type: JobType,
        user_id: UUID,
        payload: dict[str, Any],
        max_retries: int = 3,
    ) -> UUID:
        """
        Adds a job to the queue. Returns job ID for tracking.
        """
        job_id = uuid4()
        job = RetryJob(
            id=job_id,
            job_type=job_type,
            user_id=user_id,
            payload=payload,
            max_retries=max_retries,
        )
        
        self._jobs[job_id] = job
        await self._queue.put(job)
        
        logger.info(
            f"Enqueued job {job_id}: type={job_type.value}, user={user_id}"
        )
        
        return job_id
    
    def cancel_user_jobs(self, user_id: UUID) -> int:
        """
        Marks all pending jobs for a user as cancelled.
        Used when profile is deleted during processing.
        Returns count of cancelled jobs.
        """
        self._cancelled_users.add(user_id)
        count = 0
        
        for job in self._jobs.values():
            if job.user_id == user_id and job.status in (JobStatus.QUEUED, JobStatus.PROCESSING):
                job.status = JobStatus.CANCELLED
                count += 1
        
        logger.info(f"Cancelled {count} jobs for user {user_id}")
        return count
    
    def get_job_status(self, job_id: UUID) -> Optional[RetryJob]:
        """Returns job details or None if not found."""
        return self._jobs.get(job_id)
    
    async def start(self) -> None:
        """Starts the background queue processor."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._process_queue())
        logger.info("Retry queue started")
    
    async def stop(self) -> None:
        """Stops the queue processor gracefully."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Retry queue stopped")
    
    async def _process_queue(self) -> None:
        """Main processing loop with exponential backoff."""
        while self._running:
            try:
                job = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            
            if job.user_id in self._cancelled_users:
                job.status = JobStatus.CANCELLED
                logger.info(f"Job {job.id} cancelled: user {job.user_id} in cancelled set")
                continue
            
            if job.status == JobStatus.CANCELLED:
                logger.info(f"Skipping cancelled job {job.id}")
                continue
            
            await self._execute_with_backoff(job)
    
    async def _execute_with_backoff(self, job: RetryJob) -> None:
        """Executes job with exponential backoff on failure."""
        handler = self._handlers.get(job.job_type)
        
        if handler is None:
            logger.error(f"No handler for job type {job.job_type.value}")
            job.status = JobStatus.FAILED
            job.error_message = "No handler registered"
            return
        
        job.status = JobStatus.PROCESSING
        job.attempt += 1
        job.last_attempt_at = datetime.now(timezone.utc)
        
        logger.info(
            f"Processing job {job.id}: type={job.job_type.value}, "
            f"attempt={job.attempt}/{job.max_retries}"
        )
        
        try:
            await handler(job.user_id, job.payload)
            job.status = JobStatus.COMPLETED
            logger.info(f"Job {job.id} completed successfully")
            
        except Exception as e:
            job.error_message = str(e)
            logger.warning(
                f"Job {job.id} failed on attempt {job.attempt}: {e}"
            )
            
            if job.attempt >= job.max_retries:
                job.status = JobStatus.FAILED
                logger.error(
                    f"Job {job.id} permanently failed after {job.attempt} attempts"
                )
            else:
                backoff_seconds = 2 ** job.attempt
                logger.info(
                    f"Job {job.id} will retry in {backoff_seconds}s"
                )
                
                await asyncio.sleep(backoff_seconds)
                
                if job.user_id not in self._cancelled_users:
                    job.status = JobStatus.QUEUED
                    await self._queue.put(job)


_queue_instance: Optional[RetryQueue] = None


def get_retry_queue() -> RetryQueue:
    """Returns the singleton retry queue instance."""
    global _queue_instance
    
    if _queue_instance is None:
        _queue_instance = RetryQueue()
    
    return _queue_instance


async def init_retry_queue() -> RetryQueue:
    """Initializes and starts the retry queue."""
    queue = get_retry_queue()
    await queue.start()
    return queue


async def shutdown_retry_queue() -> None:
    """Stops the retry queue."""
    global _queue_instance
    
    if _queue_instance is not None:
        await _queue_instance.stop()
        _queue_instance = None


__all__ = [
    "JobStatus",
    "JobType",
    "RetryJob",
    "RetryQueue",
    "get_retry_queue",
    "init_retry_queue",
    "shutdown_retry_queue",
]

