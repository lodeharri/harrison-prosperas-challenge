"""Main processing logic for report jobs."""

import asyncio
import logging
import random
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import structlog

from backend.worker.observability import create_cw_metrics_safe
from backend.worker.backoff import exponential_backoff
from backend.worker.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from backend.worker.config import Settings, get_settings
from backend.worker.dynamodb_client import DynamoDBClient, get_dynamodb_client
from backend.worker.http_client import HttpClient, get_http_client
from backend.worker.models import (
    JobMessage,
    JobPriority,
    JobStatus,
    NonRetryableError,
    ProcessingError,
    RetryableError,
)
from backend.worker.sqs_client import SQSClient, get_sqs_client

# Configure structured logging
# Using stdlib logging as base to avoid structlog compatibility issues
import logging as stdlib_logging

stdlib_logging.basicConfig(
    format="%(message)s",
    level=stdlib_logging.INFO,
)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.BoundLogger,
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger()

# Priority polling intervals
PRIORITY_POLL_INTERVAL = 0.5  # seconds - poll priority queue more frequently
STANDARD_POLL_INTERVAL = 2.0  # seconds - poll standard queue less frequently


class ProcessingMetrics:
    """Metrics collector for job processing with CloudWatch integration."""

    def __init__(self) -> None:
        self.jobs_processed: int = 0
        self.jobs_failed: int = 0
        self.jobs_by_type: dict[str, int] = defaultdict(int)
        self.processing_times: list[float] = []
        self.start_time: float = time.time()
        # CloudWatch metrics publisher (optional - won't fail if unavailable)
        self.cw_metrics = create_cw_metrics_safe()

    def record_success(self, report_type: str, duration: float) -> None:
        """Record a successful job completion."""
        self.jobs_processed += 1
        self.jobs_by_type[report_type] += 1
        self.processing_times.append(duration)
        # Send to CloudWatch (backwards compatible)
        if self.cw_metrics:
            try:
                self.cw_metrics.put_job_processed(report_type, duration)
            except Exception:
                pass  # Don't fail if CloudWatch is unavailable

    def record_failure(self, report_type: str) -> None:
        """Record a job failure."""
        self.jobs_failed += 1
        # Send to CloudWatch (backwards compatible)
        if self.cw_metrics:
            try:
                self.cw_metrics.put_job_failed(report_type)
            except Exception:
                pass  # Don't fail if CloudWatch is unavailable

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary."""
        uptime = time.time() - self.start_time
        avg_processing_time = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times
            else 0
        )
        return {
            "uptime_seconds": uptime,
            "jobs_processed": self.jobs_processed,
            "jobs_failed": self.jobs_failed,
            "jobs_by_type": dict(self.jobs_by_type),
            "avg_processing_time_seconds": avg_processing_time,
        }


class JobProcessor:
    """Main job processor with concurrency and error handling."""

    def __init__(
        self,
        settings: Settings | None = None,
        sqs_client: SQSClient | None = None,
        dynamodb_client: DynamoDBClient | None = None,
        http_client: HttpClient | None = None,
    ) -> None:
        """Initialize job processor."""
        self.settings = settings or get_settings()
        self.sqs = sqs_client or get_sqs_client()
        self.dynamodb = dynamodb_client or get_dynamodb_client()
        self.http = http_client or get_http_client()
        self.running = False
        self.metrics = ProcessingMetrics()

        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.settings.circuit_breaker_failure_threshold,
            recovery_timeout=self.settings.circuit_breaker_recovery_timeout,
        )

        # Semaphore for bounded concurrency
        self.semaphore = asyncio.Semaphore(self.settings.max_concurrent_jobs)

    async def process_single_job(self, message: dict[str, Any]) -> bool:
        """
        Process a single job from the queue.

        Args:
            message: SQS message containing job data

        Returns:
            True if job was processed successfully
        """
        receipt_handle = message.get("ReceiptHandle", "")
        job_message: JobMessage | None = None

        try:
            # Parse message
            job_message = JobMessage.from_sqs_message(message)
            job_id = job_message.job_id

            logger.info(
                "job_processing_started",
                job_id=job_id,
                report_type=job_message.report_type,
                priority=job_message.priority.value,
            )

            # Update status to PROCESSING (with optimistic locking)
            current_job = await self.dynamodb.get_job(job_id)
            if not current_job:
                raise NonRetryableError(f"Job {job_id} not found", job_id=job_id)
            current_version = current_job.get("version", 1)

            await self.dynamodb.update_job_status(
                job_id,
                JobStatus.PROCESSING,
                expected_version=current_version,
            )

            # Notify API for WebSocket when status changes to PROCESSING
            processing_updated_at = datetime.now(timezone.utc).isoformat()
            await self.http.notify_job_update(
                user_id=job_message.user_id,
                job_id=job_id,
                status=JobStatus.PROCESSING.value,
                updated_at=processing_updated_at,
                report_type=job_message.report_type,
            )

            # Check circuit breaker
            is_open, retry_after = await self.circuit_breaker.is_open(
                job_message.report_type
            )
            if is_open:
                raise RetryableError(
                    f"Circuit breaker open for {job_message.report_type}",
                    job_id=job_id,
                )

            # Process the report with circuit breaker
            start_time = time.time()
            result = await self.circuit_breaker.call(
                job_message.report_type,
                self._process_report,
                job_id,
                job_message.report_type,
            )
            duration = time.time() - start_time

            # Update status to COMPLETED (with optimistic locking)
            updated_at = datetime.now(timezone.utc).isoformat()
            # Re-fetch job to get current version
            current_job = await self.dynamodb.get_job(job_id)
            current_version = current_job.get("version", 1) if current_job else 1

            await self.dynamodb.update_job_status(
                job_id,
                JobStatus.COMPLETED,
                result_url=result["result_url"],
                expected_version=current_version,
            )

            # Record metrics
            self.metrics.record_success(job_message.report_type, duration)

            logger.info(
                "job_processing_completed",
                job_id=job_id,
                report_type=job_message.report_type,
                duration_seconds=duration,
                result_url=result["result_url"],
            )

            # Notify API for WebSocket (non-blocking)
            await self.http.notify_job_update(
                user_id=job_message.user_id,
                job_id=job_id,
                status=JobStatus.COMPLETED.value,
                result_url=result["result_url"],
                updated_at=updated_at,
                report_type=job_message.report_type,
            )

            # Delete message from the correct queue based on priority
            is_high_priority = job_message.priority == JobPriority.HIGH
            source_queue_url = (
                self.settings.sqs_priority_queue_url
                if is_high_priority
                else self.settings.sqs_queue_url
            )
            await self.sqs.delete_message(source_queue_url, receipt_handle)

            return True

        except CircuitBreakerOpenError as e:
            logger.warning(
                "circuit_breaker_open",
                job_id=job_message.job_id if job_message else "unknown",
                report_type=e.report_type,
                retry_after=e.retry_after,
            )
            # Don't delete message, let it become visible again
            return False

        except NonRetryableError as e:
            logger.error(
                "job_processing_non_retryable_error",
                job_id=e.job_id or (job_message.job_id if job_message else "unknown"),
                error=str(e),
            )
            self.metrics.record_failure(
                job_message.report_type if job_message else "unknown"
            )
            # Move to DLQ
            await self._handle_failure(message, job_message, e)
            return False

        except RetryableError as e:
            logger.warning(
                "job_processing_retryable_error",
                job_id=e.job_id or (job_message.job_id if job_message else "unknown"),
                error=str(e),
            )
            # Check if we should move to DLQ
            attempt_count = self._get_attempt_count(message)
            if attempt_count >= self.settings.max_retries:
                self.metrics.record_failure(
                    job_message.report_type if job_message else "unknown"
                )
                await self._handle_failure(message, job_message, e)
            return False

        except Exception as e:
            logger.error(
                "job_processing_unexpected_error",
                job_id=job_message.job_id if job_message else "unknown",
                error=str(e),
                error_type=type(e).__name__,
            )
            self.metrics.record_failure(
                job_message.report_type if job_message else "unknown"
            )
            await self._handle_failure(message, job_message, e)
            return False

    async def _process_report(self, job_id: str, report_type: str) -> dict[str, Any]:
        """
        Simulate report generation with random processing time.

        Args:
            job_id: The job identifier
            report_type: Type of report to generate

        Returns:
            Processing result with result URL
        """
        # Simulate processing time (5-30 seconds)
        processing_time = random.uniform(
            self.settings.min_processing_time,
            self.settings.max_processing_time,
        )
        await asyncio.sleep(processing_time)

        # Generate dummy result
        result_id = uuid.uuid4().hex[:12]
        result_url = (
            f"https://reports.example.com/{report_type}/{job_id}/{result_id}.pdf"
        )

        return {
            "job_id": job_id,
            "report_type": report_type,
            "result_url": result_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": {
                "total_records": random.randint(100, 10000),
                "summary": f"Dummy {report_type} report summary",
                "processing_time": processing_time,
            },
        }

    def _get_attempt_count(self, message: dict[str, Any]) -> int:
        """Extract attempt count from SQS message."""
        attrs = message.get("MessageAttributes", {})
        count = attrs.get("ApproximateReceiveCount", {})
        if isinstance(count, dict):
            try:
                return int(count.get("StringValue", 1))
            except (ValueError, TypeError):
                return 1
        return 1

    async def _handle_failure(
        self,
        message: dict[str, Any],
        job_message: JobMessage | None,
        error: ProcessingError,
    ) -> None:
        """Handle a failed message by moving to DLQ or retrying."""
        attempt_count = self._get_attempt_count(message)
        job_id = job_message.job_id if job_message else "unknown"
        user_id = job_message.user_id if job_message else "unknown"
        report_type = job_message.report_type if job_message else "unknown"

        logger.warning(
            "job_failed",
            job_id=job_id,
            attempt=attempt_count,
            max_attempts=self.settings.max_retries,
            error=str(error),
        )

        # Update job status to FAILED (with optimistic locking)
        try:
            updated_at = datetime.now(timezone.utc).isoformat()
            current_job = await self.dynamodb.get_job(job_id)
            current_version = current_job.get("version", 1) if current_job else 1
            await self.dynamodb.update_job_status(
                job_id,
                JobStatus.FAILED,
                expected_version=current_version,
            )

            # Notify API for WebSocket (non-blocking) - only if we have user info
            if job_message:
                await self.http.notify_job_update(
                    user_id=user_id,
                    job_id=job_id,
                    status=JobStatus.FAILED.value,
                    updated_at=updated_at,
                    report_type=report_type,
                )
        except Exception as e:
            logger.error(f"Failed to update job status to FAILED: {e}")

        # Determine which queue the message came from based on priority
        is_high_priority = job_message and job_message.priority == JobPriority.HIGH
        source_queue_url = (
            self.settings.sqs_priority_queue_url
            if is_high_priority
            else self.settings.sqs_queue_url
        )

        # Move to DLQ
        await self.sqs.send_to_dlq(message)
        receipt_handle = message.get("ReceiptHandle", "")
        if receipt_handle:
            await self.sqs.delete_message(source_queue_url, receipt_handle)

    async def _bounded_process(self, message: dict[str, Any]) -> bool:
        """Process a message with semaphore for bounded concurrency."""
        async with self.semaphore:
            return await self.process_single_job(message)

    async def run(self) -> None:
        """Main worker loop that prefers high-priority jobs."""
        self.running = True
        logger.info(
            "worker_started",
            max_concurrent=self.settings.max_concurrent_jobs,
            min_concurrent=self.settings.min_concurrent_jobs,
        )

        while self.running:
            try:
                # FIRST: Check high-priority queue
                priority_messages = await self.sqs.receive_messages(
                    queue_url=self.settings.sqs_priority_queue_url,
                    max_messages=self.settings.max_receive_messages,
                )

                # Process priority messages immediately
                if priority_messages:
                    logger.info(
                        "received_priority_messages", count=len(priority_messages)
                    )

                    # Process messages with bounded concurrency
                    tasks = [
                        asyncio.create_task(self._bounded_process(msg))
                        for msg in priority_messages
                    ]

                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Log results
                    success_count = sum(1 for r in results if r is True)
                    failure_count = len(results) - success_count
                    logger.info(
                        "priority_batch_processed",
                        total=len(results),
                        successful=success_count,
                        failed=failure_count,
                    )

                    # Send batch metrics to CloudWatch (backwards compatible)
                    if self.metrics.cw_metrics:
                        try:
                            self.metrics.cw_metrics.put_batch_processed(
                                len(results), success_count, failure_count
                            )
                        except Exception:
                            pass  # Don't fail if CloudWatch is unavailable

                    continue  # Skip standard queue this iteration

                # SECOND: Only check standard queue if priority is empty
                standard_messages = await self.sqs.receive_messages(
                    queue_url=self.settings.sqs_queue_url,
                    max_messages=self.settings.max_receive_messages,
                )

                if standard_messages:
                    logger.info(
                        "received_standard_messages", count=len(standard_messages)
                    )

                    # Process messages with bounded concurrency
                    tasks = [
                        asyncio.create_task(self._bounded_process(msg))
                        for msg in standard_messages
                    ]

                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Log results
                    success_count = sum(1 for r in results if r is True)
                    failure_count = len(results) - success_count
                    logger.info(
                        "standard_batch_processed",
                        total=len(results),
                        successful=success_count,
                        failed=failure_count,
                    )

                    # Send batch metrics to CloudWatch (backwards compatible)
                    if self.metrics.cw_metrics:
                        try:
                            self.metrics.cw_metrics.put_batch_processed(
                                len(results), success_count, failure_count
                            )
                        except Exception:
                            pass  # Don't fail if CloudWatch is unavailable

                else:
                    # Both queues empty - sleep less time for priority check
                    await asyncio.sleep(PRIORITY_POLL_INTERVAL)

            except asyncio.CancelledError:
                logger.info("Worker cancelled, shutting down...")
                self.running = False
                break
            except Exception as e:
                logger.error("worker_error", error=str(e))
                await asyncio.sleep(5)  # Back off on errors

        logger.info("Worker stopped")

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        self.running = False
        await self.sqs.close()
        await self.dynamodb.close()
        await self.http.close()

    async def health_check(self) -> dict[str, Any]:
        """Check health of worker and dependencies."""
        sqs_healthy = await self.sqs.health_check()
        dynamo_healthy = await self.dynamodb.health_check()

        return {
            "worker_running": self.running,
            "sqs_healthy": sqs_healthy,
            "dynamodb_healthy": dynamo_healthy,
            "metrics": self.metrics.get_summary(),
            "circuit_breakers": self.circuit_breaker.get_stats(),
        }
