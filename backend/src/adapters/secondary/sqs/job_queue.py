"""SQS implementation of JobQueue port.

This adapter implements the JobQueue port using AWS SQS.
It handles publishing job messages to the queue for async processing.
Supports priority routing for high-priority report types.
"""

import json
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from backend.src.application.ports.job_queue import JobQueue
from backend.src.config.settings import Settings, get_settings
from backend.src.domain.entities.job import Job

logger = logging.getLogger(__name__)

# Report types that should be routed to high priority queue
HIGH_PRIORITY_REPORT_TYPES = {"sales_report", "financial_report"}


class SQSJobQueue(JobQueue):
    """
    SQS implementation of the JobQueue port.

    This adapter is responsible for:
    - Converting job entities to SQS messages
    - Handling AWS-specific error translation
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """
        Initialize the SQS queue adapter.

        Args:
            settings: Optional settings instance
        """
        self._settings = settings or get_settings()
        self._client: Any = None

    @property
    def client(self) -> Any:
        """Get SQS client with lazy initialization."""
        if self._client is None:
            self._client = boto3.client(
                "sqs",
                endpoint_url=self._settings.aws_endpoint_url,
                region_name=self._settings.aws_region,
                aws_access_key_id=self._settings.aws_access_key_id,
                aws_secret_access_key=self._settings.aws_secret_access_key,
            )
        return self._client

    def publish(self, job: Job) -> bool:
        """
        Publish a job to the SQS queue.

        Args:
            job: The job entity to publish

        Returns:
            True if published successfully
        """
        try:
            message_body = {
                "job_id": job.job_id,
                "user_id": job.user_id,
                "report_type": job.report_type,
            }

            self.client.send_message(
                QueueUrl=self._settings.sqs_queue_url,
                MessageBody=json.dumps(message_body),
                MessageAttributes={
                    "ReportType": {
                        "DataType": "String",
                        "StringValue": job.report_type,
                    }
                },
            )

            logger.info(f"Published job {job.job_id} to SQS queue")
            return True

        except ClientError as e:
            logger.error(f"Failed to publish job {job.job_id} to SQS: {e}")
            raise

    async def publish_priority(self, job: Job) -> bool:
        """
        Publish a high-priority job to the SQS priority queue.

        Args:
            job: The job entity to publish

        Returns:
            True if published successfully
        """
        try:
            message_body = {
                "job_id": job.job_id,
                "user_id": job.user_id,
                "report_type": job.report_type,
                "priority": "high",
                "created_at": job.created_at.isoformat(),
            }

            await self._send_to_queue(
                queue_url=self._settings.sqs_priority_queue_url,
                message_body=json.dumps(message_body),
                job_id=job.job_id,
                report_type=job.report_type,
                priority="high",
            )

            logger.info(f"Published high-priority job {job.job_id} to priority queue")
            return True

        except ClientError as e:
            logger.error(
                f"Failed to publish high-priority job {job.job_id} to SQS: {e}"
            )
            raise

    async def _send_to_queue(
        self,
        queue_url: str,
        message_body: str,
        job_id: str,
        report_type: str,
        priority: str,
    ) -> None:
        """
        Send message to specified queue with attributes.

        Args:
            queue_url: The SQS queue URL to send to
            message_body: JSON message body
            job_id: Job identifier for logging
            report_type: Report type for message attributes
            priority: Priority level for message attributes
        """
        self.client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body,
            MessageAttributes={
                "priority": {"DataType": "String", "StringValue": priority},
                "report_type": {"DataType": "String", "StringValue": report_type},
            },
        )

    def health_check(self) -> bool:
        """
        Check if SQS queue is accessible.

        Returns:
            True if healthy
        """
        try:
            self.client.get_queue_url(
                QueueName=self._settings.sqs_queue_name.split("/")[-1]
            )
            return True
        except ClientError:
            return False
