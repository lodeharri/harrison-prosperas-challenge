"""DynamoDB client for job status operations."""

from datetime import datetime, timezone
from typing import Any

import aiobotocore.session
import structlog
from botocore.exceptions import ClientError

from backend.worker.config import Settings, get_settings
from backend.worker.models import JobStatus

logger = structlog.get_logger(__name__)


class DynamoDBClient:
    """Async DynamoDB client for job operations."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize DynamoDB client."""
        self.settings = settings or get_settings()
        self._session: Any = None

    async def _get_session(self) -> Any:
        """Get or create aiobotocore session."""
        if self._session is None:
            self._session = aiobotocore.session.get_session()
        return self._session

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        """
        Get a job by its ID.

        Args:
            job_id: The unique job identifier

        Returns:
            Job data dict or None if not found
        """
        session = await self._get_session()

        try:
            async with session.create_client(
                "dynamodb",
                endpoint_url=self.settings.aws_endpoint_url,
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            ) as client:
                response = await client.get_item(
                    TableName=self.settings.dynamodb_table_jobs,
                    Key={"job_id": {"S": job_id}},
                )
                item = response.get("Item")
                if not item:
                    return None
                return self._unmarshall_item(item)

        except ClientError as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            raise

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        result_url: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Update a job's status in DynamoDB.

        Args:
            job_id: The unique job identifier
            status: New status value
            result_url: Optional result URL (for completed jobs)

        Returns:
            Updated job data or None if job not found
        """
        session = await self._get_session()
        updated_at = datetime.now(timezone.utc).isoformat()

        # Build update expression
        update_expression = "SET #status = :status, updated_at = :updated_at"
        expression_values: dict[str, Any] = {
            ":status": {"S": status.value},
            ":updated_at": {"S": updated_at},
        }

        if result_url is not None:
            update_expression += ", result_url = :result_url"
            expression_values[":result_url"] = {"S": result_url}

        try:
            async with session.create_client(
                "dynamodb",
                endpoint_url=self.settings.aws_endpoint_url,
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            ) as client:
                response = await client.update_item(
                    TableName=self.settings.dynamodb_table_jobs,
                    Key={"job_id": {"S": job_id}},
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues=expression_values,
                    ReturnValues="ALL_NEW",
                )
                logger.info(f"Updated job {job_id} status to {status.value}")
                return self._unmarshall_item(response.get("Attributes", {}))

        except ClientError as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check if DynamoDB is accessible.

        Returns:
            True if DynamoDB is healthy
        """
        session = await self._get_session()

        try:
            async with session.create_client(
                "dynamodb",
                endpoint_url=self.settings.aws_endpoint_url,
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            ) as client:
                await client.describe_table(TableName=self.settings.dynamodb_table_jobs)
            return True
        except ClientError:
            return False

    def _unmarshall_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """
        Convert DynamoDB item format to Python dict.

        Args:
            item: DynamoDB item with type descriptors

        Returns:
            Plain Python dictionary
        """
        result = {}
        for key, value in item.items():
            if "S" in value:
                result[key] = value["S"]
            elif "N" in value:
                # Handle both int and float
                num_str = value["N"]
                result[key] = float(num_str) if "." in num_str else int(num_str)
            elif "BOOL" in value:
                result[key] = value["BOOL"]
            elif "NULL" in value:
                result[key] = None
            elif "L" in value:
                result[key] = [self._unmarshall_value(v) for v in value["L"]]
            elif "M" in value:
                result[key] = self._unmarshall_item(value["M"])
        return result

    def _unmarshall_value(self, value: dict[str, Any]) -> Any:
        """Unmarshall a single DynamoDB value."""
        if "S" in value:
            return value["S"]
        elif "N" in value:
            num_str = value["N"]
            return float(num_str) if "." in num_str else int(num_str)
        elif "BOOL" in value:
            return value["BOOL"]
        elif "NULL" in value:
            return None
        elif "L" in value:
            return [self._unmarshall_value(v) for v in value["L"]]
        elif "M" in value:
            return self._unmarshall_item(value["M"])
        return value

    async def close(self) -> None:
        """Close the DynamoDB client connection."""
        self._session = None


# Singleton instance
_dynamodb_client: DynamoDBClient | None = None


def get_dynamodb_client() -> DynamoDBClient:
    """Get the DynamoDB client singleton."""
    global _dynamodb_client
    if _dynamodb_client is None:
        _dynamodb_client = DynamoDBClient()
    return _dynamodb_client
