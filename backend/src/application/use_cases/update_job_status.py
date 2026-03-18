"""UpdateJobStatusUseCase - Updates a job's status."""

from backend.src.application.ports.job_repository import JobRepository
from backend.src.domain.entities.job import Job
from backend.src.domain.value_objects.job_status import JobStatus


class UpdateJobStatusUseCase:
    """
    Use case for updating a job's status.

    This use case handles status transitions like:
    - PENDING -> PROCESSING
    - PROCESSING -> COMPLETED (with result_url)
    - PROCESSING -> FAILED
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
        result_url: str | None = None,
    ) -> Job:
        """
        Update a job's status.

        Args:
            job_id: Job to update
            new_status: Target status
            result_url: Optional result URL (for completed jobs)

        Returns:
            The updated job
        """
        return await self._repository.update_status(
            job_id=job_id,
            status=new_status,
            result_url=result_url,
        )
