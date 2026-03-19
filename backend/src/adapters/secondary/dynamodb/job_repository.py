"""DynamoDB implementation of JobRepository port.

This adapter implements the JobRepository port using AWS DynamoDB.
It handles all the translation between domain entities and DynamoDB items.

Uses two separate tables:
- jobs: Stores job entities
- idempotency_keys: Stores idempotency key references with TTL
"""

import logging
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from backend.src.application.ports.job_repository import JobRepository
from backend.src.config.settings import Settings, get_settings
from backend.src.domain.entities.job import Job
from backend.src.domain.exceptions.domain_exceptions import (
    JobNotFoundException,
    VersionConflictException,
)
from backend.src.domain.value_objects.job_status import JobStatus

logger = logging.getLogger(__name__)


class DynamoDBJobRepository(JobRepository):
    """
    DynamoDB implementation of the JobRepository port.

    This adapter is responsible for:
    - Converting domain entities to DynamoDB items
    - Converting DynamoDB items back to domain entities
    - Handling AWS-specific error translation
    - Managing idempotency keys in a separate table with TTL
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """
        Initialize the DynamoDB repository.

        Args:
            settings: Optional settings instance
        """
        self._settings = settings or get_settings()
        self._client: Any = None
        self._jobs_table: Any = None
        self._idempotency_table: Any = None

    @property
    def client(self) -> Any:
        """Get DynamoDB client with lazy initialization."""
        if self._client is None:
            self._client = boto3.client(
                "dynamodb",
                endpoint_url=self._settings.aws_endpoint_url,
                region_name=self._settings.aws_region,
                aws_access_key_id=self._settings.aws_access_key_id,
                aws_secret_access_key=self._settings.aws_secret_access_key,
            )
        return self._client

    @property
    def jobs_table(self) -> Any:
        """Get DynamoDB jobs table resource with lazy initialization."""
        if self._jobs_table is None:
            resource = boto3.resource(
                "dynamodb",
                endpoint_url=self._settings.aws_endpoint_url,
                region_name=self._settings.aws_region,
                aws_access_key_id=self._settings.aws_access_key_id,
                aws_secret_access_key=self._settings.aws_secret_access_key,
            )
            self._jobs_table = resource.Table(self._settings.dynamodb_table_jobs)
        return self._jobs_table

    @property
    def idempotency_table(self) -> Any:
        """Get DynamoDB idempotency keys table resource with lazy initialization."""
        if self._idempotency_table is None:
            resource = boto3.resource(
                "dynamodb",
                endpoint_url=self._settings.aws_endpoint_url,
                region_name=self._settings.aws_region,
                aws_access_key_id=self._settings.aws_access_key_id,
                aws_secret_access_key=self._settings.aws_secret_access_key,
            )
            self._idempotency_table = resource.Table(
                self._settings.dynamodb_table_idempotency
            )
        return self._idempotency_table

    async def create(self, job: Job) -> Job:
        """
        Create a new job in DynamoDB.

        Args:
            job: The job entity to persist

        Returns:
            The created job
        """
        try:
            item = self._to_dynamodb_item(job)
            self.jobs_table.put_item(Item=item, ReturnValues="ALL_OLD")
            logger.info(f"Created job: {job.job_id}")
            return job
        except ClientError as e:
            logger.error(f"Failed to create job: {e}")
            raise

    async def get_by_id(self, job_id: str) -> Job:
        """
        Get a job by its ID.

        Args:
            job_id: Unique job identifier

        Returns:
            The job entity

        Raises:
            JobNotFoundException: If job doesn't exist
        """
        try:
            response = self.jobs_table.get_item(Key={"job_id": job_id})
            if "Item" not in response:
                raise JobNotFoundException(job_id)
            return self._from_dynamodb_item(response["Item"])
        except JobNotFoundException:
            raise
        except ClientError as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            raise

    async def list_by_user(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Job], int]:
        """
        List jobs for a user with pagination.

        Args:
            user_id: User identifier
            page: Page number (1-indexed)
            page_size: Items per page

        Returns:
            Tuple of (list of jobs, total count)
        """
        try:
            page_size = max(page_size, 20)  # Enforce minimum

            # Scan with filter for user_id
            response = self.jobs_table.scan(
                FilterExpression="user_id = :user_id",
                ExpressionAttributeValues={":user_id": user_id},
            )

            items = response.get("Items", [])

            # Sort by created_at descending
            items.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            total = len(items)

            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_items = items[start_idx:end_idx]

            jobs = [self._from_dynamodb_item(item) for item in paginated_items]
            return jobs, total

        except ClientError as e:
            logger.error(f"Failed to list jobs for user {user_id}: {e}")
            raise

    async def update_status_with_version(
        self,
        job_id: str,
        expected_version: int,
        status: JobStatus,
        result_url: str | None = None,
    ) -> Job:
        """
        Update a job's status with optimistic locking.

        Uses conditional writes to prevent race conditions. If the version
        doesn't match, raises VersionConflictException.

        Args:
            job_id: Job identifier
            expected_version: Expected current version
            status: New status
            result_url: Optional result URL (for completed jobs)

        Returns:
            The updated job with incremented version

        Raises:
            VersionConflictException: If version doesn't match
        """
        try:
            update_expression = "SET #status = :status, updated_at = :updated_at, #version = :new_version"
            expression_values: dict[str, Any] = {
                ":status": status.value,
                ":updated_at": datetime.now(timezone.utc).isoformat(),
                ":expected_version": expected_version,
                ":new_version": expected_version + 1,
            }

            if result_url is not None:
                update_expression += ", result_url = :result_url"
                expression_values[":result_url"] = result_url

            response = self.jobs_table.update_item(
                Key={"job_id": job_id},
                UpdateExpression=update_expression,
                ConditionExpression="#version = :expected_version",
                ExpressionAttributeNames={
                    "#status": "status",
                    "#version": "version",
                },
                ExpressionAttributeValues=expression_values,
                ReturnValues="ALL_NEW",
            )
            logger.info(
                f"Updated job {job_id} status to {status.value} "
                f"(version {expected_version} -> {expected_version + 1})"
            )
            return self._from_dynamodb_item(response["Attributes"])

        except ClientError as e:
            # Check if this is a conditional check failed error
            if (
                e.response.get("Error", {}).get("Code")
                == "ConditionalCheckFailedException"
            ):
                # Get the actual current version to report in the exception
                try:
                    current = await self.get_by_id(job_id)
                    actual_version = current.version
                except JobNotFoundException:
                    actual_version = None

                logger.warning(
                    f"Version conflict for job {job_id}: "
                    f"expected {expected_version}, found {actual_version}"
                )
                raise VersionConflictException(
                    job_id=job_id,
                    expected_version=expected_version,
                    actual_version=actual_version,
                )
            # Other ClientError - re-raise
            logger.error(f"Failed to update job {job_id}: {e}")
            raise

    async def get_by_idempotency_key(self, idempotency_key: str) -> Job | None:
        """
        Retrieve a job by its idempotency key.

        Uses a separate idempotency_keys table to look up the key,
        then fetches the associated job.

        Args:
            idempotency_key: The idempotency key to look up

        Returns:
            The job entity if found, None otherwise
        """
        try:
            # Query the idempotency keys table
            response = self.idempotency_table.get_item(
                Key={"idempotency_key": idempotency_key}
            )
            item = response.get("Item")

            if item is None:
                logger.debug(f"No job found for idempotency key: {idempotency_key}")
                return None

            job_id = item.get("job_id")
            if not job_id:
                logger.warning(
                    f"Idempotency key exists but has no job_id: {idempotency_key}"
                )
                return None

            # Fetch the actual job
            try:
                return await self.get_by_id(job_id)
            except JobNotFoundException:
                logger.warning(
                    f"Job {job_id} for idempotency key {idempotency_key} no longer exists"
                )
                return None

        except ClientError as e:
            logger.error(f"Failed to get job by idempotency key {idempotency_key}: {e}")
            raise

    async def save_idempotency_key(
        self,
        idempotency_key: str,
        job_id: str,
        expires_at: datetime,
    ) -> None:
        """
        Store an idempotency key with a reference to a job.

        Uses a separate idempotency_keys table with TTL enabled,
        so the key reference expires automatically without affecting
        the actual job data.

        Args:
            idempotency_key: The idempotency key
            job_id: The associated job ID
            expires_at: When this key should expire (used for TTL)
        """
        try:
            ttl = int(expires_at.timestamp())
            item = {
                "idempotency_key": idempotency_key,
                "job_id": job_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": ttl,  # DynamoDB TTL attribute
            }
            self.idempotency_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(idempotency_key)",
            )
            logger.info(f"Saved idempotency key {idempotency_key} for job {job_id}")
        except ClientError as e:
            # Check if this is a conditional check failed error
            if (
                e.response.get("Error", {}).get("Code")
                == "ConditionalCheckFailedException"
            ):
                # Idempotency key already exists - this is expected for duplicate requests
                logger.debug(
                    f"Idempotency key {idempotency_key} already exists for another job"
                )
                # Don't raise - the original job with this key already exists
            else:
                # Other ClientError - re-raise
                logger.error(f"Failed to save idempotency key {idempotency_key}: {e}")
                raise

    async def health_check(self) -> bool:
        """
        Check if DynamoDB is accessible.

        Returns:
            True if healthy
        """
        try:
            self.client.describe_table(TableName=self._settings.dynamodb_table_jobs)
            self.client.describe_table(
                TableName=self._settings.dynamodb_table_idempotency
            )
            return True
        except ClientError:
            return False

    def _to_dynamodb_item(self, job: Job) -> dict[str, Any]:
        """
        Convert a Job entity to DynamoDB item format.

        Args:
            job: The job entity

        Returns:
            DynamoDB item dictionary
        """
        item = {
            "job_id": job.job_id,
            "user_id": job.user_id,
            "report_type": job.report_type,
            "date_range": job.date_range,
            "format": job.format,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "version": job.version,
        }
        if job.result_url is not None:
            item["result_url"] = job.result_url
        return item

    def _from_dynamodb_item(self, item: dict[str, Any]) -> Job:
        """
        Convert a DynamoDB item to a Job entity.

        Args:
            item: DynamoDB item dictionary

        Returns:
            Job entity
        """
        # Parse datetime fields
        created_at = item.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        updated_at = item.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        return Job(
            job_id=item["job_id"],
            user_id=item["user_id"],
            report_type=item["report_type"],
            date_range=item.get("date_range", "all"),
            format=item.get("format", "pdf"),
            status=JobStatus(item.get("status", "PENDING")),
            created_at=created_at,
            updated_at=updated_at,
            result_url=item.get("result_url"),
            version=item.get("version", 1),
        )
