"""CreateJobUseCase - Creates a new job and queues it for processing.

Supports priority routing based on report type:
- sales_report, financial_report -> High priority queue
- Other types -> Standard queue
"""

import uuid

from backend.src.application.ports.job_queue import JobQueue
from backend.src.application.ports.job_repository import JobRepository
from backend.src.domain.entities.job import Job
from backend.src.adapters.secondary.sqs.job_queue import HIGH_PRIORITY_REPORT_TYPES


class CreateJobUseCase:
    """
    Use case for creating a new report job.

    This use case orchestrates:
    1. Creating a new job entity
    2. Persisting it via the repository
    3. Publishing to the queue for async processing

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
    ) -> Job:
        """
        Create a new job for processing.

        Args:
            user_id: User creating the job
            report_type: Type of report to generate

        Returns:
            The created job entity
        """
        # Generate unique job ID
        job_id = str(uuid.uuid4())

        # Create domain entity
        job = Job.create(
            job_id=job_id,
            user_id=user_id,
            report_type=report_type,
        )

        # Persist to repository
        await self._repository.create(job)

        # Route to appropriate queue based on report type priority
        if job.report_type in HIGH_PRIORITY_REPORT_TYPES:
            # High priority: sales_report, financial_report
            await self._queue.publish_priority(job)
        else:
            # Standard priority: all other report types
            self._queue.publish(job)

        return job
