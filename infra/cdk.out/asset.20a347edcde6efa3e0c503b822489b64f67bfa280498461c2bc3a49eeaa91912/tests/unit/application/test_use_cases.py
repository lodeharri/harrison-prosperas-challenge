"""Tests for use cases with mocked dependencies."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.src.application.use_cases.create_job import (
    CreateJobResult,
    CreateJobUseCase,
)
from backend.src.application.use_cases.get_job import GetJobUseCase
from backend.src.application.use_cases.list_jobs import ListJobsUseCase
from backend.src.domain.entities.job import Job
from backend.src.domain.value_objects.job_status import JobStatus
from backend.src.domain.exceptions.domain_exceptions import (
    JobNotFoundException,
    JobAccessDeniedException,
)


class TestCreateJobUseCase:
    """Tests for CreateJobUseCase."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock repository."""
        repo = MagicMock()
        repo.create = AsyncMock(return_value=None)
        repo.get_by_idempotency_key = AsyncMock(return_value=None)
        repo.save_idempotency_key = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def mock_queue(self):
        """Create a mock queue."""
        queue = MagicMock()
        queue.publish = MagicMock(return_value=True)
        queue.publish_priority = AsyncMock(return_value=True)
        return queue

    @pytest.mark.asyncio
    async def test_creates_job_and_publishes(self, mock_repository, mock_queue):
        """Test that use case creates job and publishes to queue."""
        use_case = CreateJobUseCase(
            job_repository=mock_repository,
            job_queue=mock_queue,
        )

        result = await use_case.execute(
            user_id="user-123",
            report_type="sales_report",
        )

        # Verify result is CreateJobResult with idempotent=False
        assert isinstance(result, CreateJobResult)
        assert result.idempotent is False
        job = result.job

        # Verify job was created with correct attributes
        assert job.user_id == "user-123"
        assert job.report_type == "sales_report"
        assert job.status == JobStatus.PENDING
        assert job.job_id is not None

        # Verify repository was called
        mock_repository.create.assert_called_once()

        # Verify priority queue was called for high-priority report type
        mock_queue.publish_priority.assert_called_once()
        mock_queue.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_standard_job(self, mock_repository, mock_queue):
        """Test that use case routes standard jobs to regular queue."""
        use_case = CreateJobUseCase(
            job_repository=mock_repository,
            job_queue=mock_queue,
        )

        result = await use_case.execute(
            user_id="user-123",
            report_type="inventory_report",
        )

        job = result.job
        # Verify job was created with correct attributes
        assert job.user_id == "user-123"
        assert job.report_type == "inventory_report"
        assert job.status == JobStatus.PENDING

        # Verify standard queue was called for non-high-priority report type
        mock_queue.publish.assert_called_once()
        mock_queue.publish_priority.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_existing_job_for_idempotency_key(
        self, mock_repository, mock_queue
    ):
        """Test that use case returns existing job when idempotency key matches."""
        # Create an existing job
        existing_job = Job.create(
            job_id="existing-job-123",
            user_id="user-123",
            report_type="sales_report",
        )
        mock_repository.get_by_idempotency_key = AsyncMock(return_value=existing_job)

        use_case = CreateJobUseCase(
            job_repository=mock_repository,
            job_queue=mock_queue,
        )

        result = await use_case.execute(
            user_id="user-123",
            report_type="sales_report",
            idempotency_key="my-unique-key-123",
        )

        # Verify result indicates idempotent response
        assert isinstance(result, CreateJobResult)
        assert result.idempotent is True
        assert result.job.job_id == "existing-job-123"

        # Verify no new job was created
        mock_repository.create.assert_not_called()

        # Verify no message was published
        mock_queue.publish.assert_not_called()
        mock_queue.publish_priority.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_new_job_and_saves_idempotency_key(
        self, mock_repository, mock_queue
    ):
        """Test that use case saves idempotency key after creating job."""
        use_case = CreateJobUseCase(
            job_repository=mock_repository,
            job_queue=mock_queue,
        )

        result = await use_case.execute(
            user_id="user-123",
            report_type="sales_report",
            idempotency_key="my-unique-key-456",
        )

        # Verify idempotency key was checked first
        mock_repository.get_by_idempotency_key.assert_called_once_with(
            "my-unique-key-456"
        )

        # Verify idempotency key was saved after job creation
        mock_repository.save_idempotency_key.assert_called_once()
        call_args = mock_repository.save_idempotency_key.call_args
        assert call_args.kwargs["idempotency_key"] == "my-unique-key-456"
        assert call_args.kwargs["job_id"] == result.job.job_id
        assert call_args.kwargs["expires_at"] is not None

        # Verify result is not idempotent
        assert result.idempotent is False


class TestGetJobUseCase:
    """Tests for GetJobUseCase."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock repository."""
        repo = MagicMock()
        return repo

    @pytest.mark.asyncio
    async def test_returns_job_for_owner(self, mock_repository):
        """Test that use case returns job when user is owner."""
        job = Job.create(
            job_id="job-123",
            user_id="user-123",
            report_type="sales_report",
        )
        mock_repository.get_by_id = AsyncMock(return_value=job)

        use_case = GetJobUseCase(job_repository=mock_repository)
        result = await use_case.execute(
            job_id="job-123",
            requesting_user_id="user-123",
        )

        assert result.job_id == "job-123"

    @pytest.mark.asyncio
    async def test_raises_not_found_for_missing_job(self, mock_repository):
        """Test that use case raises exception when job not found."""
        mock_repository.get_by_id = AsyncMock(
            side_effect=JobNotFoundException("job-123")
        )

        use_case = GetJobUseCase(job_repository=mock_repository)

        with pytest.raises(JobNotFoundException):
            await use_case.execute(
                job_id="job-123",
                requesting_user_id="user-123",
            )

    @pytest.mark.asyncio
    async def test_raises_access_denied_for_non_owner(self, mock_repository):
        """Test that use case raises exception when user is not owner."""
        job = Job.create(
            job_id="job-123",
            user_id="user-123",
            report_type="sales_report",
        )
        mock_repository.get_by_id = AsyncMock(return_value=job)

        use_case = GetJobUseCase(job_repository=mock_repository)

        with pytest.raises(JobAccessDeniedException):
            await use_case.execute(
                job_id="job-123",
                requesting_user_id="other-user",
            )


class TestListJobsUseCase:
    """Tests for ListJobsUseCase."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock repository."""
        repo = MagicMock()
        return repo

    @pytest.mark.asyncio
    async def test_lists_jobs_for_user(self, mock_repository):
        """Test that use case lists jobs for user."""
        jobs = [
            Job.create(
                job_id=f"job-{i}",
                user_id="user-123",
                report_type="sales_report",
            )
            for i in range(3)
        ]
        mock_repository.list_by_user = AsyncMock(return_value=(jobs, 3))

        use_case = ListJobsUseCase(job_repository=mock_repository)
        result_jobs, total = await use_case.execute(
            user_id="user-123",
            page=1,
            page_size=20,
        )

        assert len(result_jobs) == 3
        assert total == 3
        mock_repository.list_by_user.assert_called_once_with(
            user_id="user-123",
            page=1,
            page_size=20,
        )

    @pytest.mark.asyncio
    async def test_enforces_minimum_page_size(self, mock_repository):
        """Test that use case enforces minimum page size."""
        mock_repository.list_by_user = AsyncMock(return_value=([], 0))

        use_case = ListJobsUseCase(job_repository=mock_repository)
        await use_case.execute(
            user_id="user-123",
            page=1,
            page_size=10,  # Below minimum
        )

        # Should be called with max(10, 20) = 20
        mock_repository.list_by_user.assert_called_once_with(
            user_id="user-123",
            page=1,
            page_size=20,
        )
