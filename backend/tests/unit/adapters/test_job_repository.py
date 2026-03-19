"""Tests for DynamoDB JobRepository adapter."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, PropertyMock

from backend.src.adapters.secondary.dynamodb.job_repository import DynamoDBJobRepository
from backend.src.domain.entities.job import Job
from backend.src.domain.value_objects.job_status import JobStatus
from backend.src.domain.exceptions.domain_exceptions import (
    JobNotFoundException,
    VersionConflictException,
)


class MockDynamoDBJobRepository(DynamoDBJobRepository):
    """Mock DynamoDB repository for testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mock_jobs_table = None
        self._mock_idempotency_table = None
        self._mock_client = None

    @property
    def jobs_table(self):
        return self._mock_jobs_table

    @property
    def idempotency_table(self):
        return self._mock_idempotency_table

    @property
    def client(self):
        return self._mock_client

    def set_mock_jobs_table(self, table):
        self._mock_jobs_table = table

    def set_mock_idempotency_table(self, table):
        self._mock_idempotency_table = table

    def set_mock_client(self, client):
        self._mock_client = client


class TestDynamoDBJobRepositoryCreate:
    """Tests for create() method."""

    @pytest.mark.asyncio
    async def test_create_job_success(self, mock_settings):
        """Test creating a job successfully."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)

        mock_table = MagicMock()
        mock_table.put_item.return_value = {}
        repo.set_mock_jobs_table(mock_table)

        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )

        result = await repo.create(job)

        assert result.job_id == "test-123"
        mock_table.put_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_job_client_error(self, mock_settings):
        """Test create job raises on ClientError."""
        from botocore.exceptions import ClientError

        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test"}}, "PutItem"
        )
        repo.set_mock_jobs_table(mock_table)

        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )

        with pytest.raises(ClientError):
            await repo.create(job)


class TestDynamoDBJobRepositoryGetById:
    """Tests for get_by_id() method."""

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, mock_settings):
        """Test getting a job by ID successfully."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "job_id": "test-123",
                "user_id": "user-456",
                "report_type": "sales_report",
                "date_range": "all",
                "format": "pdf",
                "status": "PENDING",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
                "version": 1,
            }
        }
        repo.set_mock_jobs_table(mock_table)

        result = await repo.get_by_id("test-123")

        assert result.job_id == "test-123"
        assert result.user_id == "user-456"
        assert result.status == JobStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, mock_settings):
        """Test get_by_id raises JobNotFoundException when job doesn't exist."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        repo.set_mock_jobs_table(mock_table)

        with pytest.raises(JobNotFoundException):
            await repo.get_by_id("nonexistent-id")

    @pytest.mark.asyncio
    async def test_get_by_id_client_error(self, mock_settings):
        """Test get_by_id raises on ClientError."""
        from botocore.exceptions import ClientError

        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test"}}, "GetItem"
        )
        repo.set_mock_jobs_table(mock_table)

        with pytest.raises(ClientError):
            await repo.get_by_id("test-123")


class TestDynamoDBJobRepositoryUpdateStatus:
    """Tests for update_status_with_version() method."""

    @pytest.mark.asyncio
    async def test_update_status_success(self, mock_settings):
        """Test updating job status with version successfully."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.update_item.return_value = {
            "Attributes": {
                "job_id": "test-123",
                "user_id": "user-456",
                "report_type": "sales_report",
                "date_range": "all",
                "format": "pdf",
                "status": "PROCESSING",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:01:00+00:00",
                "version": 2,
            }
        }
        repo.set_mock_jobs_table(mock_table)

        result = await repo.update_status_with_version(
            job_id="test-123",
            expected_version=1,
            status=JobStatus.PROCESSING,
        )

        assert result.status == JobStatus.PROCESSING
        assert result.version == 2

    @pytest.mark.asyncio
    async def test_update_status_with_result_url(self, mock_settings):
        """Test updating job status with result URL."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.update_item.return_value = {
            "Attributes": {
                "job_id": "test-123",
                "user_id": "user-456",
                "report_type": "sales_report",
                "date_range": "all",
                "format": "pdf",
                "status": "COMPLETED",
                "result_url": "https://example.com/results/test-123.pdf",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:01:00+00:00",
                "version": 2,
            }
        }
        repo.set_mock_jobs_table(mock_table)

        result = await repo.update_status_with_version(
            job_id="test-123",
            expected_version=1,
            status=JobStatus.COMPLETED,
            result_url="https://example.com/results/test-123.pdf",
        )

        assert result.status == JobStatus.COMPLETED
        assert result.result_url == "https://example.com/results/test-123.pdf"

    @pytest.mark.asyncio
    async def test_update_status_version_conflict(self, mock_settings):
        """Test update raises VersionConflictException on conditional check failure."""
        from botocore.exceptions import ClientError

        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
        )
        # Mock get_by_id to return job with different version
        mock_table.get_item.return_value = {
            "Item": {
                "job_id": "test-123",
                "user_id": "user-456",
                "report_type": "sales_report",
                "status": "PROCESSING",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
                "version": 5,
            }
        }
        repo.set_mock_jobs_table(mock_table)

        with pytest.raises(VersionConflictException) as exc_info:
            await repo.update_status_with_version(
                job_id="test-123",
                expected_version=1,
                status=JobStatus.PROCESSING,
            )

        assert exc_info.value.expected_version == 1
        assert exc_info.value.actual_version == 5

    @pytest.mark.asyncio
    async def test_update_status_version_conflict_job_not_found(self, mock_settings):
        """Test update raises VersionConflictException when job not found during conflict."""
        from botocore.exceptions import ClientError

        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
        )
        # Mock get_by_id to raise JobNotFoundException
        mock_table.get_item.side_effect = JobNotFoundException("test-123")

        repo.set_mock_jobs_table(mock_table)

        with pytest.raises(VersionConflictException) as exc_info:
            await repo.update_status_with_version(
                job_id="test-123",
                expected_version=1,
                status=JobStatus.PROCESSING,
            )

        assert exc_info.value.actual_version is None


class TestDynamoDBJobRepositoryIdempotency:
    """Tests for idempotency methods."""

    @pytest.mark.asyncio
    async def test_get_by_idempotency_key_found(self, mock_settings):
        """Test get_by_idempotency_key returns job when found."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)

        mock_idempotency_table = MagicMock()
        mock_idempotency_table.get_item.return_value = {
            "Item": {
                "idempotency_key": "my-key-123",
                "job_id": "test-123",
            }
        }
        repo.set_mock_idempotency_table(mock_idempotency_table)

        mock_jobs_table = MagicMock()
        mock_jobs_table.get_item.return_value = {
            "Item": {
                "job_id": "test-123",
                "user_id": "user-456",
                "report_type": "sales_report",
                "date_range": "all",
                "format": "pdf",
                "status": "PENDING",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T00:00:00+00:00",
                "version": 1,
            }
        }
        repo.set_mock_jobs_table(mock_jobs_table)

        result = await repo.get_by_idempotency_key("my-key-123")

        assert result is not None
        assert result.job_id == "test-123"

    @pytest.mark.asyncio
    async def test_get_by_idempotency_key_not_found(self, mock_settings):
        """Test get_by_idempotency_key returns None when not found."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)

        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        repo.set_mock_idempotency_table(mock_table)

        result = await repo.get_by_idempotency_key("nonexistent-key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_idempotency_key_no_job_id(self, mock_settings):
        """Test get_by_idempotency_key returns None when key has no job_id."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "idempotency_key": "my-key-123",
            }
        }
        repo.set_mock_idempotency_table(mock_table)

        result = await repo.get_by_idempotency_key("my-key-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_idempotency_key_job_not_found(self, mock_settings):
        """Test get_by_idempotency_key returns None when job no longer exists."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)

        mock_idempotency_table = MagicMock()
        mock_idempotency_table.get_item.return_value = {
            "Item": {
                "idempotency_key": "my-key-123",
                "job_id": "deleted-job-123",
            }
        }
        repo.set_mock_idempotency_table(mock_idempotency_table)

        mock_jobs_table = MagicMock()
        mock_jobs_table.get_item.side_effect = JobNotFoundException("deleted-job-123")
        repo.set_mock_jobs_table(mock_jobs_table)

        result = await repo.get_by_idempotency_key("my-key-123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_idempotency_key_client_error(self, mock_settings):
        """Test get_by_idempotency_key raises on ClientError."""
        from botocore.exceptions import ClientError

        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test"}}, "GetItem"
        )
        repo.set_mock_idempotency_table(mock_table)

        with pytest.raises(ClientError):
            await repo.get_by_idempotency_key("my-key-123")

    @pytest.mark.asyncio
    async def test_save_idempotency_key_success(self, mock_settings):
        """Test saving idempotency key successfully."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        repo.set_mock_idempotency_table(mock_table)

        expires_at = datetime.now(timezone.utc)
        await repo.save_idempotency_key(
            idempotency_key="my-key-123",
            job_id="test-123",
            expires_at=expires_at,
        )

        mock_table.put_item.assert_called_once()
        call_kwargs = mock_table.put_item.call_args.kwargs
        assert call_kwargs["Item"]["idempotency_key"] == "my-key-123"
        assert call_kwargs["Item"]["job_id"] == "test-123"
        assert "expires_at" in call_kwargs["Item"]

    @pytest.mark.asyncio
    async def test_save_idempotency_key_already_exists(self, mock_settings):
        """Test save_idempotency_key handles existing key gracefully."""
        from botocore.exceptions import ClientError

        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
        )
        repo.set_mock_idempotency_table(mock_table)

        # Should not raise - existing key is expected
        expires_at = datetime.now(timezone.utc)
        await repo.save_idempotency_key(
            idempotency_key="existing-key",
            job_id="test-123",
            expires_at=expires_at,
        )

    @pytest.mark.asyncio
    async def test_save_idempotency_key_other_error(self, mock_settings):
        """Test save_idempotency_key raises on other ClientError."""
        from botocore.exceptions import ClientError

        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test"}}, "PutItem"
        )
        repo.set_mock_idempotency_table(mock_table)

        expires_at = datetime.now(timezone.utc)
        with pytest.raises(ClientError):
            await repo.save_idempotency_key(
                idempotency_key="my-key-123",
                job_id="test-123",
                expires_at=expires_at,
            )


class TestDynamoDBJobRepositoryListByUser:
    """Tests for list_by_user() method."""

    @pytest.mark.asyncio
    async def test_list_by_user_success(self, mock_settings):
        """Test listing jobs for user successfully."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.scan.return_value = {
            "Items": [
                {
                    "job_id": "job-1",
                    "user_id": "user-456",
                    "report_type": "sales_report",
                    "date_range": "all",
                    "format": "pdf",
                    "status": "PENDING",
                    "created_at": "2024-01-02T00:00:00+00:00",
                    "updated_at": "2024-01-02T00:00:00+00:00",
                    "version": 1,
                },
                {
                    "job_id": "job-2",
                    "user_id": "user-456",
                    "report_type": "inventory_report",
                    "date_range": "all",
                    "format": "csv",
                    "status": "COMPLETED",
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "updated_at": "2024-01-01T00:01:00+00:00",
                    "version": 2,
                },
            ]
        }
        repo.set_mock_jobs_table(mock_table)

        jobs, total = await repo.list_by_user("user-456", page=1, page_size=20)

        assert len(jobs) == 2
        assert total == 2
        # Should be sorted by created_at descending
        assert jobs[0].job_id == "job-1"
        assert jobs[1].job_id == "job-2"

    @pytest.mark.asyncio
    async def test_list_by_user_pagination(self, mock_settings):
        """Test listing jobs with pagination."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.scan.return_value = {
            "Items": [
                {
                    "job_id": f"job-{i}",
                    "user_id": "user-456",
                    "report_type": "sales_report",
                    "date_range": "all",
                    "format": "pdf",
                    "status": "PENDING",
                    "created_at": f"2024-01-{i:02d}T00:00:00+00:00",
                    "updated_at": f"2024-01-{i:02d}T00:00:00+00:00",
                    "version": 1,
                }
                for i in range(1, 6)
            ]
        }
        repo.set_mock_jobs_table(mock_table)

        # Note: page_size is enforced to minimum 20, so with 5 items we get all 5
        jobs, total = await repo.list_by_user("user-456", page=1, page_size=20)

        assert len(jobs) == 5
        assert total == 5

    @pytest.mark.asyncio
    async def test_list_by_user_enforces_minimum_page_size(self, mock_settings):
        """Test that list_by_user enforces minimum page size."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.scan.return_value = {"Items": []}
        repo.set_mock_jobs_table(mock_table)

        jobs, total = await repo.list_by_user("user-456", page=1, page_size=10)

        assert total == 0

    @pytest.mark.asyncio
    async def test_list_by_user_client_error(self, mock_settings):
        """Test list_by_user raises on ClientError."""
        from botocore.exceptions import ClientError

        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_table = MagicMock()
        mock_table.scan.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test"}}, "Scan"
        )
        repo.set_mock_jobs_table(mock_table)

        with pytest.raises(ClientError):
            await repo.list_by_user("user-456", page=1, page_size=20)


class TestDynamoDBJobRepositoryHealthCheck:
    """Tests for health_check() method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_settings):
        """Test health_check returns True when healthy."""
        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_client = MagicMock()
        repo.set_mock_client(mock_client)

        result = await repo.health_check()

        assert result is True
        assert mock_client.describe_table.call_count == 2

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_settings):
        """Test health_check returns False on ClientError."""
        from botocore.exceptions import ClientError

        repo = MockDynamoDBJobRepository(settings=mock_settings)
        mock_client = MagicMock()
        mock_client.describe_table.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "Test"}}, "DescribeTable"
        )
        repo.set_mock_client(mock_client)

        result = await repo.health_check()

        assert result is False


class TestDynamoDBItemConversion:
    """Tests for DynamoDB item conversion methods."""

    def test_to_dynamodb_item(self, mock_settings):
        """Test _to_dynamodb_item converts job correctly."""
        repo = DynamoDBJobRepository(settings=mock_settings)

        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
            date_range="2024-01-01 to 2024-01-31",
            format="csv",
        )

        item = repo._to_dynamodb_item(job)

        assert item["job_id"] == "test-123"
        assert item["user_id"] == "user-456"
        assert item["report_type"] == "sales_report"
        assert item["date_range"] == "2024-01-01 to 2024-01-31"
        assert item["format"] == "csv"
        assert item["status"] == "PENDING"
        assert item["version"] == 1
        assert "created_at" in item
        assert "updated_at" in item

    def test_to_dynamodb_item_with_result_url(self, mock_settings):
        """Test _to_dynamodb_item includes result_url when present."""
        repo = DynamoDBJobRepository(settings=mock_settings)

        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )
        job.mark_processing()
        job.mark_completed("https://example.com/results/test-123.pdf")

        item = repo._to_dynamodb_item(job)

        assert item["result_url"] == "https://example.com/results/test-123.pdf"

    def test_from_dynamodb_item(self, mock_settings):
        """Test _from_dynamodb_item converts item correctly."""
        repo = DynamoDBJobRepository(settings=mock_settings)

        item = {
            "job_id": "test-123",
            "user_id": "user-456",
            "report_type": "sales_report",
            "date_range": "2024-01-01 to 2024-01-31",
            "format": "excel",
            "status": "PROCESSING",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:01:00+00:00",
            "result_url": "https://example.com/results/test-123.pdf",
            "version": 3,
        }

        job = repo._from_dynamodb_item(item)

        assert job.job_id == "test-123"
        assert job.user_id == "user-456"
        assert job.report_type == "sales_report"
        assert job.date_range == "2024-01-01 to 2024-01-31"
        assert job.format == "excel"
        assert job.status == JobStatus.PROCESSING
        assert job.result_url == "https://example.com/results/test-123.pdf"
        assert job.version == 3

    def test_from_dynamodb_item_with_defaults(self, mock_settings):
        """Test _from_dynamodb_item uses defaults for missing optional fields."""
        repo = DynamoDBJobRepository(settings=mock_settings)

        item = {
            "job_id": "test-123",
            "user_id": "user-456",
            "report_type": "sales_report",
            "status": "PENDING",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:00:00+00:00",
        }

        job = repo._from_dynamodb_item(item)

        assert job.date_range == "all"
        assert job.format == "pdf"
        assert job.version == 1
        assert job.result_url is None

    def test_from_dynamodb_item_handles_z_suffix(self, mock_settings):
        """Test _from_dynamodb_item handles ISO format with Z suffix."""
        repo = DynamoDBJobRepository(settings=mock_settings)

        item = {
            "job_id": "test-123",
            "user_id": "user-456",
            "report_type": "sales_report",
            "status": "PENDING",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }

        job = repo._from_dynamodb_item(item)

        assert job.created_at.year == 2024
        assert job.created_at.month == 1
        assert job.created_at.day == 1
