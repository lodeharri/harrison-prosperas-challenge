"""ListJobsUseCase - Lists jobs for a user with pagination."""

from backend.src.application.ports.job_repository import JobRepository
from backend.src.domain.entities.job import Job


class ListJobsUseCase:
    """
    Use case for listing jobs for a specific user.

    This use case retrieves paginated jobs for the authenticated user.
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
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Job], int]:
        """
        List jobs for a user with pagination.

        Args:
            user_id: User whose jobs to list
            page: Page number (1-indexed)
            page_size: Items per page (minimum 20 enforced by repository)

        Returns:
            Tuple of (list of jobs, total count)
        """
        return await self._repository.list_by_user(
            user_id=user_id,
            page=page,
            page_size=max(page_size, 20),  # Enforce minimum
        )
