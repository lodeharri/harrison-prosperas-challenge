"""Pytest fixtures for worker tests."""

import asyncio
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from backend.worker.config import Settings, get_settings
from backend.worker.models import JobMessage, JobPriority, JobStatus
from backend.worker.processor import JobProcessor


@pytest.fixture
def settings() -> Settings:
    """Get test settings."""
    return get_settings()


@pytest.fixture
def sample_job_message() -> JobMessage:
    """Create a sample job message."""
    return JobMessage(
        job_id="test-job-123",
        user_id="test-user-456",
        report_type="sales_report",
        priority=JobPriority.STANDARD,
    )


@pytest.fixture
def sample_sqs_message() -> dict[str, Any]:
    """Create a sample SQS message."""
    import json

    return {
        "MessageId": "msg-123",
        "ReceiptHandle": "receipt-123",
        "Body": json.dumps(
            {
                "job_id": "test-job-123",
                "user_id": "test-user-456",
                "report_type": "sales_report",
            }
        ),
        "MessageAttributes": {
            "job_id": {"DataType": "String", "StringValue": "test-job-123"},
            "user_id": {"DataType": "String", "StringValue": "test-user-456"},
            "report_type": {"DataType": "String", "StringValue": "sales_report"},
            "ApproximateReceiveCount": {"DataType": "Number", "StringValue": "1"},
        },
    }


@pytest.fixture
def mock_sqs_client() -> AsyncMock:
    """Create a mock SQS client."""
    client = AsyncMock()
    client.receive_messages = AsyncMock(return_value=[])
    client.delete_message = AsyncMock(return_value=True)
    client.send_to_dlq = AsyncMock(return_value=True)
    client.health_check = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_dynamodb_client() -> AsyncMock:
    """Create a mock DynamoDB client."""
    client = AsyncMock()

    # Track calls for get_job - needs to be awaitable
    mock_job_data = {
        "job_id": "test-job-123",
        "user_id": "test-user-456",
        "status": "PENDING",
        "report_type": "sales_report",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "version": 1,
    }
    client.get_job = AsyncMock(return_value=mock_job_data)

    # Use AsyncMock for update_job_status since it's awaited in the code
    client.update_job_status = AsyncMock(
        return_value={
            "job_id": "test-job-123",
            "status": "COMPLETED",
            "result_url": "https://example.com/report.pdf",
        }
    )
    # Idempotency methods - return False (message not processed yet)
    client.check_message_id_exists = AsyncMock(return_value=False)
    client.save_message_id = AsyncMock(return_value=True)
    client.health_check = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Create a mock HTTP client."""
    client = AsyncMock()
    client.notify_job_update = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest_asyncio.fixture
async def processor(
    mock_sqs_client: AsyncMock,
    mock_dynamodb_client: AsyncMock,
    mock_http_client: AsyncMock,
) -> AsyncGenerator[JobProcessor, None]:
    """Create a processor with mocked dependencies."""
    with (
        patch("backend.worker.processor.get_sqs_client", return_value=mock_sqs_client),
        patch(
            "backend.worker.processor.get_dynamodb_client",
            return_value=mock_dynamodb_client,
        ),
        patch(
            "backend.worker.processor.get_http_client",
            return_value=mock_http_client,
        ),
    ):
        proc = JobProcessor(
            sqs_client=mock_sqs_client,
            dynamodb_client=mock_dynamodb_client,
            http_client=mock_http_client,
        )
        yield proc
        await proc.stop()


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
