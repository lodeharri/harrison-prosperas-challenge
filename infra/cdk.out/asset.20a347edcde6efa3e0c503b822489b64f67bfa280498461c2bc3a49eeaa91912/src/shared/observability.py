"""CloudWatch observability module for logging and metrics.

This module provides CloudWatch integration for:
- Custom metrics (JobsProcessed, JobsFailed, BatchTotal, etc.)
- Structured logging to CloudWatch Logs
"""

from typing import Any

import boto3

from backend.src.config.settings import get_settings


class CloudWatchMetrics:
    """CloudWatch Metrics publisher for job processing metrics."""

    def __init__(self, namespace: str = "RetoProsperas"):
        self.client = boto3.client("cloudwatch")
        self.namespace = namespace

    def put_job_processed(self, report_type: str, duration_seconds: float) -> None:
        """Record a successful job completion."""
        self.client.put_metric_data(
            Namespace=self.namespace,
            MetricData=[
                {
                    "MetricName": "JobsProcessed",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "ReportType", "Value": report_type}],
                },
                {
                    "MetricName": "ProcessingDuration",
                    "Value": duration_seconds,
                    "Unit": "Seconds",
                    "Dimensions": [{"Name": "ReportType", "Value": report_type}],
                },
            ],
        )

    def put_job_failed(self, report_type: str) -> None:
        """Record a job failure."""
        self.client.put_metric_data(
            Namespace=self.namespace,
            MetricData=[
                {
                    "MetricName": "JobsFailed",
                    "Value": 1,
                    "Unit": "Count",
                    "Dimensions": [{"Name": "ReportType", "Value": report_type}],
                }
            ],
        )

    def put_batch_processed(self, total: int, successful: int, failed: int) -> None:
        """Record batch processing metrics."""
        self.client.put_metric_data(
            Namespace=self.namespace,
            MetricData=[
                {"MetricName": "BatchTotal", "Value": total, "Unit": "Count"},
                {"MetricName": "BatchSuccessful", "Value": successful, "Unit": "Count"},
                {"MetricName": "BatchFailed", "Value": failed, "Unit": "Count"},
            ],
        )


def setup_cloudwatch_logging() -> Any:
    """
    Configure structlog to output JSON to CloudWatch.

    Returns the CloudWatch log handler for cleanup.

    Note: In production, this should be called once at application startup.
    The handler will automatically flush logs to CloudWatch.
    """
    try:
        import structlog
        import watchtower
        from structlog import configure, make_filtering_bound_logger
        import logging

        settings = get_settings()

        # Create CloudWatch handler
        cw_handler = watchtower.CloudWatchLogHandler(
            log_group=settings.cloudwatch_log_group,
            stream_name=settings.cloudwatch_stream_name,
            boto3_client=boto3.client("logs"),
        )

        # Configure structlog with CloudWatch handler
        configure(
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=make_filtering_bound_logger(logging.INFO),
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(file=cw_handler.stream),
        )

        return cw_handler
    except Exception as e:
        # Return None if CloudWatch logging setup fails
        # This ensures backwards compatibility
        import logging

        logging.getLogger(__name__).warning(f"CloudWatch logging setup failed: {e}")
        return None


def get_cloudwatch_logger(name: str = "worker") -> Any:
    """Get a structlog logger configured for CloudWatch."""
    try:
        from structlog import get_logger

        return get_logger().bind(component=name)
    except Exception:
        # Fallback to standard logging if structlog is not configured
        import logging

        return logging.getLogger(name)


def create_cw_metrics_safe() -> "CloudWatchMetrics | None":
    """
    Create CloudWatch metrics client safely.

    Returns None if CloudWatch is not available (e.g., in local dev).
    This ensures backwards compatibility.
    """
    try:
        return CloudWatchMetrics()
    except Exception:
        return None
