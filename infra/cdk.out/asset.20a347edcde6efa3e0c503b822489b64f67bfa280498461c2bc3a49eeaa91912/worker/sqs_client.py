"""SQS client for receiving and managing messages."""

import json
import logging
from typing import Any

import aiobotocore.session
import structlog
from botocore.exceptions import ClientError, ConnectionError, EndpointConnectionError
from botocore.exceptions import ReadTimeoutError, ConnectTimeoutError

from backend.worker.config import Settings, get_settings
from backend.worker.backoff import retry_with_backoff

logger = structlog.get_logger(__name__)

RETRYABLE_EXCEPTIONS = (
    ClientError,
    ConnectionError,
    EndpointConnectionError,
    ReadTimeoutError,
    ConnectTimeoutError,
)


class SQSClient:
    """Async SQS client for message operations."""

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize SQS client."""
        self.settings = settings or get_settings()
        self._session: Any = None

    async def _get_client(self) -> Any:
        """Get or create async SQS client.

        Creates a fresh client from the session for each operation.
        The session manages connection pooling internally.
        """
        if self._session is None:
            self._session = aiobotocore.session.get_session()
        return self._session

    async def _create_client_with_retry(self, service_name: str, **kwargs: Any) -> Any:
        """Create an async client with retry on connection failures."""
        session = await self._get_client()

        async def create_client():
            return session.create_client(service_name, **kwargs)

        max_attempts = min(
            5,
            int(self.settings.backoff_max_delay / self.settings.backoff_base_delay) + 1,
        )
        return await retry_with_backoff(
            create_client,
            max_attempts=max_attempts,
            base_delay=self.settings.backoff_base_delay,
            max_delay=self.settings.backoff_max_delay,
            retryable_exceptions=RETRYABLE_EXCEPTIONS,
        )

    async def receive_messages(
        self,
        queue_url: str | None = None,
        max_messages: int = 10,
        visibility_timeout: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Receive messages from SQS queue.

        Args:
            queue_url: URL of the queue (defaults to main queue)
            max_messages: Maximum messages to receive (1-10)
            visibility_timeout: Message visibility timeout in seconds

        Returns:
            List of SQS messages
        """
        session = await self._get_client()
        queue_url = queue_url or self.settings.sqs_queue_url

        kwargs: dict[str, Any] = {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": min(max_messages, 10),
            "WaitTimeSeconds": 1,  # Short poll
        }

        if visibility_timeout:
            kwargs["VisibilityTimeout"] = visibility_timeout

        try:
            async with await self._create_client_with_retry(
                "sqs",
                endpoint_url=self.settings.aws_endpoint_url,
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            ) as client:
                response = await client.receive_message(**kwargs)
            messages = response.get("Messages", [])
            logger.debug(f"Received {len(messages)} messages from queue")
            return messages

        except ClientError as e:
            logger.error(f"Failed to receive messages: {e}")
            return []

    async def delete_message(self, queue_url: str, receipt_handle: str) -> bool:
        """
        Delete a message from the queue after successful processing.

        Args:
            queue_url: URL of the queue
            receipt_handle: Receipt handle from the message

        Returns:
            True if deletion was successful
        """
        session = await self._get_client()

        try:
            async with session.create_client(
                "sqs",
                endpoint_url=self.settings.aws_endpoint_url,
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            ) as client:
                await client.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle,
                )
            logger.debug(f"Deleted message from queue: {queue_url}")
            return True

        except ClientError as e:
            logger.error(f"Failed to delete message: {e}")
            return False

    async def send_to_dlq(self, message: dict[str, Any]) -> bool:
        """
        Move a failed message to the dead letter queue.

        Args:
            message: The SQS message to move

        Returns:
            True if message was successfully moved
        """
        session = await self._get_client()
        dlq_url = self.settings.sqs_dlq_url

        try:
            # Send the message body to DLQ
            message_body = message.get("Body", "{}")

            # Include attempt count if available
            attributes = message.get("MessageAttributes", {})
            attempt_count = int(
                attributes.get("ApproximateReceiveCount", {}).get("StringValue", 0)
            )

            async with await self._create_client_with_retry(
                "sqs",
                endpoint_url=self.settings.aws_endpoint_url,
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            ) as client:
                await client.send_message(
                    QueueUrl=dlq_url,
                    MessageBody=message_body,
                    MessageAttributes={
                        "OriginalQueueUrl": {
                            "DataType": "String",
                            "StringValue": self.settings.sqs_queue_url,
                        },
                        "AttemptCount": {
                            "DataType": "Number",
                            "StringValue": str(attempt_count),
                        },
                    },
                )
            logger.warning(
                "moved_message_to_dlq",
                original_queue=self.settings.sqs_queue_url,
                attempt_count=attempt_count,
                job_id=message.get("Body", ""),
            )
            return True

        except ClientError as e:
            logger.error(f"Failed to send message to DLQ: {e}")
            return False

    async def change_visibility_timeout(
        self,
        queue_url: str,
        receipt_handle: str,
        timeout: int,
    ) -> bool:
        """
        Change the visibility timeout of a message.

        Args:
            queue_url: URL of the queue
            receipt_handle: Receipt handle from the message
            timeout: New visibility timeout in seconds

        Returns:
            True if successful
        """
        session = await self._get_client()

        try:
            async with session.create_client(
                "sqs",
                endpoint_url=self.settings.aws_endpoint_url,
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            ) as client:
                await client.change_message_visibility(
                    QueueUrl=queue_url,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=timeout,
                )
            return True

        except ClientError as e:
            logger.error(f"Failed to change visibility timeout: {e}")
            return False

    async def health_check(self) -> bool:
        """
        Check if SQS is accessible.

        Returns:
            True if SQS is healthy
        """
        session = await self._get_client()

        try:
            async with await self._create_client_with_retry(
                "sqs",
                endpoint_url=self.settings.aws_endpoint_url,
                region_name=self.settings.aws_region,
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
            ) as client:
                await client.get_queue_url(
                    QueueName=self.settings.sqs_queue_url.split("/")[-1]
                )
            return True
        except ClientError:
            # Try to at least verify the client works
            try:
                async with await self._create_client_with_retry(
                    "sqs",
                    endpoint_url=self.settings.aws_endpoint_url,
                    region_name=self.settings.aws_region,
                    aws_access_key_id=self.settings.aws_access_key_id,
                    aws_secret_access_key=self.settings.aws_secret_access_key,
                ) as client:
                    await client.list_queues(MaxResults=1)
                return True
            except ClientError:
                return False

    async def close(self) -> None:
        """Close the SQS client connection."""
        # Session doesn't need explicit closing, but we reset it
        self._session = None


# Singleton instance
_sqs_client: SQSClient | None = None


def get_sqs_client() -> SQSClient:
    """Get the SQS client singleton."""
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = SQSClient()
    return _sqs_client
