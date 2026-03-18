"""JobRepository port - Interface for job persistence.

This port defines the contract for job persistence operations.
Adapters (like DynamoDB, PostgreSQL, in-memory) must implement this interface.
"""

from typing import Protocol, runtime_checkable

from backend.src.domain.entities.job import Job
from backend.src.domain.value_objects.job_status import JobStatus


@runtime_checkable
class JobRepository(Protocol):
    """
    Port interface for job persistence operations.

    This interface follows the Interface Segregation Principle,
    providing only the methods needed for job management.

    Implementations:
        - DynamoDBJobRepository: AWS DynamoDB adapter
        - InMemoryJobRepository: For testing
        - PostgreSQLJobRepository: Future SQL adapter
    """

    async def create(self, job: Job) -> Job:
        """
        Persist a new job.

        Args:
            job: The job entity to persist

        Returns:
            The created job with any modifications
        """
        ...

    async def get_by_id(self, job_id: str) -> Job:
        """
        Retrieve a job by its ID.

        Args:
            job_id: Unique job identifier

        Returns:
            The job entity

        Raises:
            JobNotFoundException: If job doesn't exist
        """
        ...

    async def list_by_user(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Job], int]:
        """
        List jobs for a specific user with pagination.

        Args:
            user_id: User identifier
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            Tuple of (list of jobs, total count)
        """
        ...

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        result_url: str | None = None,
    ) -> Job:
        """
        Update a job's status.

        Args:
            job_id: Job identifier
            status: New status
            result_url: Optional result URL (for completed jobs)

        Returns:
            The updated job
        """
        ...

    async def health_check(self) -> bool:
        """
        Check if the repository is accessible.

        Returns:
            True if healthy, False otherwise
        """
        ...
