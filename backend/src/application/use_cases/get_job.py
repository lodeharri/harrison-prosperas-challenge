"""GetJobUseCase - Retrieves a job by ID."""

from backend.src.application.ports.job_repository import JobRepository
from backend.src.domain.entities.job import Job
from backend.src.domain.exceptions.domain_exceptions import JobAccessDeniedException


class GetJobUseCase:
    """
    Use case for retrieving a job by its ID.

    This use case verifies that the requesting user has access
    to the job before returning it.
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
        requesting_user_id: str,
    ) -> Job:
        """
        Retrieve a job, verifying access rights.

        Args:
            job_id: ID of the job to retrieve
            requesting_user_id: User requesting the job

        Returns:
            The job entity

        Raises:
            JobNotFoundException: If job doesn't exist
            JobAccessDeniedException: If user doesn't own the job
        """
        # Get job from repository
        job = await self._repository.get_by_id(job_id)

        # Verify access rights
        if not job.belongs_to(requesting_user_id):
            raise JobAccessDeniedException(job_id=job_id, user_id=requesting_user_id)

        return job
