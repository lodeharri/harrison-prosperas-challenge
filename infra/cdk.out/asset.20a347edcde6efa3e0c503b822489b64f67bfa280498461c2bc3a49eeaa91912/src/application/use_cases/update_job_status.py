"""UpdateJobStatusUseCase - Updates a job's status with optimistic locking."""

from backend.src.application.ports.job_repository import JobRepository
from backend.src.domain.entities.job import Job
from backend.src.domain.value_objects.job_status import JobStatus


class UpdateJobStatusUseCase:
    """
    Use case for updating a job's status with optimistic locking.

    This use case handles status transitions like:
    - PENDING -> PROCESSING
    - PROCESSING -> COMPLETED (with result_url)
    - PROCESSING -> FAILED

    Uses version-based optimistic locking to prevent race conditions
    when multiple processes try to update the same job simultaneously.
    """

    def __init__(
        self,
        job_repository: JobRepository,
    ) -> None:
        """
        Initialize the use case with required dependencies.

        Args:
            job_repository: Port for job persistence
        """
        self._repository = job_repository

    async def execute(
        self,
        job_id: str,
        new_status: JobStatus,
        expected_version: int,
        result_url: str | None = None,
    ) -> Job:
        """
        Update a job's status with optimistic locking.

        Args:
            job_id: Job to update
            new_status: Target status
            expected_version: Expected current version for optimistic locking
            result_url: Optional result URL (for completed jobs)

        Returns:
            The updated job with incremented version

        Raises:
            VersionConflictException: If version doesn't match (concurrent modification)
        """
        return await self._repository.update_status_with_version(
            job_id=job_id,
            expected_version=expected_version,
            status=new_status,
            result_url=result_url,
        )
