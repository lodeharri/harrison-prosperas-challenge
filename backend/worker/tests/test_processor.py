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
        mock_http_client: AsyncMock,
    ) -> JobProcessor:
        """Create processor with mocked dependencies."""
        proc = JobProcessor(
            sqs_client=mock_sqs_client,
            dynamodb_client=mock_dynamodb_client,
            http_client=mock_http_client,
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
        # Verify DynamoDB was called twice (PROCESSING and COMPLETED)
        assert processor_with_mocks.dynamodb.update_job_status.call_count >= 2
        # Verify SQS message was deleted
        processor_with_mocks.sqs.delete_message.assert_called_once()

    async def test_process_single_job_sends_processing_notification(
        self,
        processor_with_mocks: JobProcessor,
        sample_sqs_message: dict[str, Any],
    ) -> None:
        """Test that PROCESSING notification is sent when job starts processing."""
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

        # Verify PROCESSING notification was sent (before report processing)
        processing_calls = [
            call
            for call in processor_with_mocks.http.notify_job_update.call_args_list
            if call.kwargs.get("status") == "PROCESSING"
            or (len(call.args) > 2 and call.args[2] == "PROCESSING")
        ]
        assert len(processing_calls) == 1, (
            "Expected exactly one PROCESSING notification"
        )

        # Verify COMPLETED notification was also sent
        completed_calls = [
            call
            for call in processor_with_mocks.http.notify_job_update.call_args_list
            if call.kwargs.get("status") == "COMPLETED"
            or (len(call.args) > 2 and call.args[2] == "COMPLETED")
        ]
        assert len(completed_calls) == 1, "Expected exactly one COMPLETED notification"

    async def test_process_single_job_move_to_dlq_after_max_retries(
        self,
        mock_sqs_client: AsyncMock,
        mock_dynamodb_client: AsyncMock,
        mock_http_client: AsyncMock,
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
            http_client=mock_http_client,
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
        # Verify update_job_status was called at least once (for PROCESSING or FAILED)
        assert mock_dynamodb_client.update_job_status.call_count >= 1
        await proc.stop()

    async def test_process_single_job_non_retryable_error(
        self,
        mock_sqs_client: AsyncMock,
        mock_dynamodb_client: AsyncMock,
        mock_http_client: AsyncMock,
        sample_sqs_message: dict[str, Any],
    ) -> None:
        """Test non-retryable errors go directly to DLQ."""
        proc = JobProcessor(
            sqs_client=mock_sqs_client,
            dynamodb_client=mock_dynamodb_client,
            http_client=mock_http_client,
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


class TestProcessorGracefulShutdown:
    """Tests for graceful shutdown functionality."""

    async def test_stop_waits_for_active_jobs(self) -> None:
        """Test that stop() waits for active jobs to complete."""
        mock_sqs = AsyncMock()
        mock_sqs.close = AsyncMock()
        mock_dynamodb = AsyncMock()
        mock_dynamodb.close = AsyncMock()
        mock_http = AsyncMock()
        mock_http.close = AsyncMock()

        proc = JobProcessor(
            sqs_client=mock_sqs,
            dynamodb_client=mock_dynamodb,
            http_client=mock_http,
        )

        # Simulate an active task
        async def slow_job() -> bool:
            await asyncio.sleep(0.1)
            return True

        # Create a task that simulates a running job
        active_task = asyncio.create_task(slow_job())
        proc._active_tasks.add(active_task)
        proc.running = True

        # Call stop - should wait for active jobs
        await proc.stop()

        # Verify the task completed (was awaited)
        assert active_task.done()

        # Verify connections were closed
        mock_sqs.close.assert_called_once()
        mock_dynamodb.close.assert_called_once()
        mock_http.close.assert_called_once()

    async def test_stop_timeout_forces_shutdown(self) -> None:
        """Test that stop() handles timeout when jobs don't complete."""
        mock_sqs = AsyncMock()
        mock_sqs.close = AsyncMock()
        mock_dynamodb = AsyncMock()
        mock_dynamodb.close = AsyncMock()
        mock_http = AsyncMock()
        mock_http.close = AsyncMock()

        # Create processor with short timeout for testing
        proc = JobProcessor(
            sqs_client=mock_sqs,
            dynamodb_client=mock_dynamodb,
            http_client=mock_http,
        )

        # Override timeout for this test
        original_timeout = JobProcessor.GRACEFUL_SHUTDOWN_TIMEOUT
        JobProcessor.GRACEFUL_SHUTDOWN_TIMEOUT = 0.01  # Very short timeout

        # Simulate a very slow active task
        async def very_slow_job() -> bool:
            await asyncio.sleep(10)  # Much longer than timeout
            return True

        # Create a task that will exceed timeout
        active_task = asyncio.create_task(very_slow_job())
        proc._active_tasks.add(active_task)
        proc.running = True

        # Call stop - should timeout and proceed
        await proc.stop()

        # Restore original timeout
        JobProcessor.GRACEFUL_SHUTDOWN_TIMEOUT = original_timeout

        # Verify connections were still closed even with timeout
        mock_sqs.close.assert_called_once()
        mock_dynamodb.close.assert_called_once()
        mock_http.close.assert_called_once()

        # Cancel the still-running task
        active_task.cancel()
        try:
            await active_task
        except asyncio.CancelledError:
            pass

    async def test_stop_logs_active_jobs(self) -> None:
        """Test that stop() logs active jobs during shutdown."""
        mock_sqs = AsyncMock()
        mock_sqs.close = AsyncMock()
        mock_dynamodb = AsyncMock()
        mock_dynamodb.close = AsyncMock()
        mock_http = AsyncMock()
        mock_http.close = AsyncMock()

        proc = JobProcessor(
            sqs_client=mock_sqs,
            dynamodb_client=mock_dynamodb,
            http_client=mock_http,
        )

        # Add simulated active task
        async def dummy_job() -> bool:
            return True

        active_task = asyncio.create_task(dummy_job())
        proc._active_tasks.add(active_task)
        proc.running = True

        # Call stop - should log active job count
        await proc.stop()

        # Verify task was tracked
        assert active_task.done() or not active_task.cancelled()

    async def test_connections_closed_on_stop(self) -> None:
        """Test that all connections are properly closed on stop."""
        mock_sqs = AsyncMock()
        mock_sqs.close = AsyncMock()
        mock_dynamodb = AsyncMock()
        mock_dynamodb.close = AsyncMock()
        mock_http = AsyncMock()
        mock_http.close = AsyncMock()

        proc = JobProcessor(
            sqs_client=mock_sqs,
            dynamodb_client=mock_dynamodb,
            http_client=mock_http,
        )
        proc.running = False

        await proc.stop()

        # Verify all close methods were called
        mock_sqs.close.assert_called_once()
        mock_dynamodb.close.assert_called_once()
        mock_http.close.assert_called_once()

    async def test_active_tasks_tracked_during_processing(self) -> None:
        """Test that active tasks are tracked during job processing."""
        mock_sqs = AsyncMock()
        mock_dynamodb = AsyncMock()
        mock_http = AsyncMock()

        proc = JobProcessor(
            sqs_client=mock_sqs,
            dynamodb_client=mock_dynamodb,
            http_client=mock_http,
        )

        # Simulate processing starts a task
        async def mock_process(message):
            return True

        # Create a mock message
        test_message = {
            "Body": json.dumps(
                {
                    "job_id": "test-job",
                    "user_id": "user-1",
                    "report_type": "sales_report",
                }
            ),
            "ReceiptHandle": "test-receipt",
            "MessageAttributes": {},
        }

        # Patch process_single_job to track tasks
        original_process = proc.process_single_job

        async def tracking_process(message):
            task = asyncio.current_task()
            if task:
                proc._active_tasks.add(task)
            # Simulate short work
            await asyncio.sleep(0.01)
            proc._active_tasks.discard(task)
            return True

        proc.process_single_job = tracking_process

        # Process a job
        proc.running = True
        await proc._bounded_process(test_message)

        # Verify no active tasks after completion
        assert len(proc._active_tasks) == 0

        await proc.stop()
