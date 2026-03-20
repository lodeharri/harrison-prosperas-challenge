"""Data models for the worker module."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobPriority(str, Enum):
    """Job priority levels."""

    HIGH = "high"
    STANDARD = "standard"


class JobMessage(BaseModel):
    """Message received from SQS queue."""

    job_id: str = Field(description="Unique job identifier")
    user_id: str = Field(description="User who created the job")
    report_type: str = Field(description="Type of report to generate")
    date_range: str = Field(
        default="all",
        description="Date range for the report",
    )
    format: str = Field(
        default="pdf",
        description="Output format for the report",
    )
    priority: JobPriority = Field(
        default=JobPriority.STANDARD,
        description="Job priority level",
    )

    @classmethod
    def from_sqs_message(cls, message: dict[str, Any]) -> "JobMessage":
        """Parse a JobMessage from an SQS message body.

        Args:
            message: SQS message dict with 'Body' containing JSON

        Returns:
            Parsed JobMessage instance
        """
        import json

        body = message.get("Body", "{}")
        if isinstance(body, str):
            body_data = json.loads(body)
        else:
            body_data = body

        # SQS message attributes may contain additional data
        message_attributes = message.get("MessageAttributes", {})

        # Merge body data with message attributes
        data = {**body_data}
        for attr_name, attr_value in message_attributes.items():
            if attr_name in ["job_id", "user_id", "report_type", "priority"]:
                data[attr_name] = attr_value.get("StringValue", data.get(attr_name))

        return cls(**data)


class JobData(BaseModel):
    """Complete job data stored in DynamoDB."""

    job_id: str
    user_id: str
    status: JobStatus
    report_type: str
    date_range: str = "all"
    format: str = "pdf"
    created_at: datetime
    updated_at: datetime
    result_url: str | None = None

    def to_dynamodb_item(self) -> dict[str, Any]:
        """Convert to DynamoDB item format."""
        item = {
            "job_id": {"S": self.job_id},
            "user_id": {"S": self.user_id},
            "status": {"S": self.status.value},
            "report_type": {"S": self.report_type},
            "date_range": {"S": self.date_range},
            "format": {"S": self.format},
            "created_at": {"S": self.created_at.isoformat()},
            "updated_at": {"S": self.updated_at.isoformat()},
        }
        if self.result_url:
            item["result_url"] = {"S": self.result_url}
        return item


class ProcessingResult(BaseModel):
    """Result of job processing."""

    job_id: str
    report_type: str
    result_url: str
    processing_time: float
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    data: dict[str, Any] = Field(default_factory=dict)

    def to_dynamodb_update(self) -> dict[str, Any]:
        """Generate update expression values for DynamoDB."""
        return {
            ":status": self.result_url.split("/")[-1]
            if self.result_url
            else "COMPLETED",
            ":result_url": self.result_url,
            ":updated_at": datetime.utcnow().isoformat(),
        }


class ProcessingError(Exception):
    """Base exception for processing errors."""

    def __init__(self, message: str, job_id: str | None = None, retryable: bool = True):
        super().__init__(message)
        self.job_id = job_id
        self.retryable = retryable


class RetryableError(ProcessingError):
    """Error that can be retried."""

    def __init__(self, message: str, job_id: str | None = None):
        super().__init__(message, job_id, retryable=True)


class NonRetryableError(ProcessingError):
    """Error that should not be retried."""

    def __init__(self, message: str, job_id: str | None = None):
        super().__init__(message, job_id, retryable=False)
