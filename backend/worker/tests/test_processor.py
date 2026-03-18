"""Tests for the main job processor."""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from backend.worker.models import (
    JobMessage,
    JobPriority,
    JobStatus,
    NonRetryableError,
    RetryableError,
)
from backend.worker.processor import JobProcessor, ProcessingMetrics


class TestJobMessage:
    """Tests for JobMessage parsing."""

    def test_from_sqs_message_with_body(self) -> None:
        """Test parsing JobMessage from SQS message body."""
        message = {
            "Body": json.dumps(
                {
                    "job_id": "job-123",
                    "user_id": "user-456",
                    "report_type": "sales_report",
                }
            ),
            "MessageAttributes": {},
        }

        job_message = JobMessage.from_sqs_message(message)

        assert job_message.job_id == "job-123"
        assert job_message.user_id == "user-456"
        assert job_message.report_type == "sales_report"
        assert job_message.priority == JobPriority.STANDARD

    def test_from_sqs_message_with_attributes(self) -> None:
        """Test parsing JobMessage from SQS message with attributes."""
        message = {
            "Body": "{}",
            "MessageAttributes": {
                "job_id": {"DataType": "String", "StringValue": "job-123"},
                "user_id": {"DataType": "String", "StringValue": "user-456"},
                "report_type": {"DataType": "String", "StringValue": "sales_report"},
                "priority": {"DataType": "String", "StringValue": "high"},
            },
        }

        job_message = JobMessage.from_sqs_message(message)

        assert job_message.job_id == "job-123"
        assert job_message.priority == JobPriority.HIGH


class TestProcessingMetrics:
    """Tests for ProcessingMetrics."""

    def test_record_success(self) -> None:
        """Test recording successful job completion."""
        metrics = ProcessingMetrics()

        metrics.record_success("sales_report", 10.5)

        assert metrics.jobs_processed == 1
        assert metrics.jobs_failed == 0
        assert metrics.jobs_by_type["sales_report"] == 1
        assert len(metrics.processing_times) == 1
        assert metrics.processing_times[0] == 10.5

    def test_record_failure(self) -> None:
        """Test recording job failure."""
        metrics = ProcessingMetrics()

        metrics.record_failure("sales_report")

        assert metrics.jobs_processed == 0
        assert metrics.jobs_failed == 1

    def test_get_summary(self) -> None:
        """Test getting metrics summary."""
        metrics = ProcessingMetrics()
        metrics.record_success("sales_report", 10.0)
        metrics.record_success("inventory_report", 15.0)
        metrics.record_failure("sales_report")

        summary = metrics.get_summary()

        assert summary["jobs_processed"] == 2
        assert summary["jobs_failed"] == 1
        assert summary["jobs_by_type"]["sales_report"] == 1
        assert summary["jobs_by_type"]["inventory_report"] == 1
        assert summary["avg_processing_time_seconds"] == 12.5


class TestJobProcessor:
    """Tests for JobProcessor."""

    @pytest_asyncio.fixture
    async def processor_with_mocks(
        self,
        mock_sqs_client: AsyncMock,
        mock_dynamodb_client: AsyncMock,
    ) -> JobProcessor:
        """Create processor with mocked dependencies."""
        proc = JobProcessor(
            sqs_client=mock_sqs_client,
            dynamodb_client=mock_dynamodb_client,
        )
        yield proc
        await proc.stop()

    async def test_process_single_job_success(
        self,
        processor_with_mocks: JobProcessor,
        sample_sqs_message: dict[str, Any],
    ) -> None:
        """Test successful job processing."""
        # Mock the report processing to be fast
        with patch.object(
            processor_with_mocks,
            "_process_report",
            new_callable=AsyncMock,
            return_value={
                "job_id": "test-job-123",
                "result_url": "https://example.com/report.pdf",
            },
        ):
            result = await processor_with_mocks.process_single_job(sample_sqs_message)

        assert result is True
        processor_with_mocks.dynamodb.update_job_status.assert_any_call(
            "test-job-123", JobStatus.PROCESSING
        )
        processor_with_mocks.dynamodb.update_job_status.assert_any_call(
            "test-job-123",
            JobStatus.COMPLETED,
            result_url="https://example.com/report.pdf",
        )
        processor_with_mocks.sqs.delete_message.assert_called_once()

    async def test_process_single_job_move_to_dlq_after_max_retries(
        self,
        mock_sqs_client: AsyncMock,
        mock_dynamodb_client: AsyncMock,
        sample_sqs_message: dict[str, Any],
    ) -> None:
        """Test job moves to DLQ after max retries."""
        # Set receive count to max retries
        sample_sqs_message["MessageAttributes"]["ApproximateReceiveCount"][
            "StringValue"
        ] = "3"

        proc = JobProcessor(
            sqs_client=mock_sqs_client,
            dynamodb_client=mock_dynamodb_client,
        )

        # Mock report processing to raise retryable error
        with patch.object(
            proc,
            "_process_report",
            new_callable=AsyncMock,
            side_effect=RetryableError("Test error", job_id="test-job-123"),
        ):
            result = await proc.process_single_job(sample_sqs_message)

        assert result is False
        mock_sqs_client.send_to_dlq.assert_called_once()
        mock_dynamodb_client.update_job_status.assert_any_call(
            "test-job-123", JobStatus.FAILED
        )
        await proc.stop()

    async def test_process_single_job_non_retryable_error(
        self,
        mock_sqs_client: AsyncMock,
        mock_dynamodb_client: AsyncMock,
        sample_sqs_message: dict[str, Any],
    ) -> None:
        """Test non-retryable errors go directly to DLQ."""
        proc = JobProcessor(
            sqs_client=mock_sqs_client,
            dynamodb_client=mock_dynamodb_client,
        )

        # Mock report processing to raise non-retryable error
        with patch.object(
            proc,
            "_process_report",
            new_callable=AsyncMock,
            side_effect=NonRetryableError("Non-retryable error", job_id="test-job-123"),
        ):
            result = await proc.process_single_job(sample_sqs_message)

        assert result is False
        mock_sqs_client.send_to_dlq.assert_called_once()
        await proc.stop()

    async def test_health_check(
        self,
        processor_with_mocks: JobProcessor,
    ) -> None:
        """Test health check returns expected structure."""
        health = await processor_with_mocks.health_check()

        assert "worker_running" in health
        assert "sqs_healthy" in health
        assert "dynamodb_healthy" in health
        assert "metrics" in health
        assert "circuit_breakers" in health


class TestProcessorConcurrency:
    """Tests for processor concurrency handling."""

    async def test_processes_multiple_jobs_concurrently(self) -> None:
        """Test that processor can handle multiple jobs."""
        mock_sqs = AsyncMock()
        mock_dynamodb = AsyncMock()

        # Return 5 messages
        mock_sqs.receive_messages = AsyncMock(
            return_value=[
                {
                    "MessageId": f"msg-{i}",
                    "ReceiptHandle": f"receipt-{i}",
                    "Body": json.dumps(
                        {
                            "job_id": f"job-{i}",
                            "user_id": "user-1",
                            "report_type": "sales_report",
                        }
                    ),
                    "MessageAttributes": {
                        "ApproximateReceiveCount": {
                            "DataType": "Number",
                            "StringValue": "1",
                        },
                    },
                }
                for i in range(5)
            ]
        )

        proc = JobProcessor(
            sqs_client=mock_sqs,
            dynamodb_client=mock_dynamodb,
        )

        # Mock report processing
        async def mock_process(job_id: str, report_type: str) -> dict:
            await asyncio.sleep(0.01)  # Small delay
            return {"job_id": job_id, "result_url": f"https://example.com/{job_id}.pdf"}

        with patch.object(proc, "_process_report", side_effect=mock_process):
            # Run the main loop for a short time
            proc.running = True
            initial_metrics = proc.metrics.jobs_processed

            # Process one batch
            messages = await proc.sqs.receive_messages()
            tasks = [proc._bounded_process(msg) for msg in messages]
            await asyncio.gather(*tasks)

            assert proc.metrics.jobs_processed == initial_metrics + 5

        await proc.stop()

    async def test_semaphore_limits_concurrency(self) -> None:
        """Test that semaphore limits concurrent processing."""
        settings = MagicMock()
        settings.max_concurrent_jobs = 2
        settings.circuit_breaker_failure_threshold = 5
        settings.circuit_breaker_recovery_timeout = 300

        proc = JobProcessor(settings=settings)

        assert proc.semaphore._value == 2
        await proc.stop()
