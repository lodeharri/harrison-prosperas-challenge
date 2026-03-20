"""CreateJobUseCase - Creates a new job and queues it for processing.

Supports priority routing based on report type:
- sales_report, financial_report -> High priority queue
- Other types -> Standard queue

Supports idempotency via X-Idempotency-Key header:
- If a job with the same idempotency key exists, returns it instead of creating a new one
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.src.application.ports.job_queue import JobQueue
from backend.src.application.ports.job_repository import JobRepository
from backend.src.domain.entities.job import Job
from backend.src.adapters.secondary.sqs.job_queue import HIGH_PRIORITY_REPORT_TYPES


@dataclass
class CreateJobResult:
    """Result of creating a job with idempotency support."""

    job: Job
    idempotent: bool  # True if this was served from an existing job


class CreateJobUseCase:
    """
    Use case for creating a new report job.

    This use case orchestrates:
    1. Checking for existing job with idempotency key
    2. Creating a new job entity (if no idempotency match)
    3. Persisting it via the repository
    4. Publishing to the queue for async processing

    Following Single Responsibility Principle, this class
    only orchestrates the creation process.
    """

    def __init__(
        self,
        job_repository: JobRepository,
        job_queue: JobQueue,
    ) -> None:
        """
        Initialize the use case with required dependencies.

        Args:
            job_repository: Port for job persistence
            job_queue: Port for job queue
        """
        self._repository = job_repository
        self._queue = job_queue

    async def execute(
        self,
        user_id: str,
        report_type: str,
        date_range: str = "all",
        format: str = "pdf",
        idempotency_key: str | None = None,
    ) -> CreateJobResult:
        """
        Create a new job for processing.

        If an idempotency key is provided and a job with that key already exists,
        returns the existing job instead of creating a new one.

        Args:
            user_id: User creating the job
            report_type: Type of report to generate
            date_range: Date range for the report
            format: Output format (pdf, csv, excel)
            idempotency_key: Optional idempotency key for safe retries

        Returns:
            CreateJobResult with the job and whether it was served from cache
        """
        # Check for existing job with idempotency key
        if idempotency_key:
            existing_job = await self._repository.get_by_idempotency_key(
                idempotency_key
            )
            if existing_job is not None:
                # Return existing job - idempotent response
                return CreateJobResult(job=existing_job, idempotent=True)

        # Generate unique job ID
        job_id = str(uuid.uuid4())

        # Create domain entity
        job = Job.create(
            job_id=job_id,
            user_id=user_id,
            report_type=report_type,
            date_range=date_range,
            format=format,
        )

        # Persist to repository
        await self._repository.create(job)

        # Save idempotency key if provided
        if idempotency_key:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
            await self._repository.save_idempotency_key(
                idempotency_key=idempotency_key,
                job_id=job_id,
                expires_at=expires_at,
            )

        # Route to appropriate queue based on report type priority
        if job.report_type in HIGH_PRIORITY_REPORT_TYPES:
            # High priority: sales_report, financial_report
            await self._queue.publish_priority(job)
        else:
            # Standard priority: all other report types
            self._queue.publish(job)

        return CreateJobResult(job=job, idempotent=False)
