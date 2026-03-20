"""Local observability module for worker - CloudWatch metrics only."""
from typing import Optional
import boto3
from backend.worker.config import get_settings


class CloudWatchMetrics:
    """CloudWatch Metrics publisher for job processing metrics (worker-local version)."""
    
    def __init__(self, namespace: str = "RetoProsperas"):
        try:
            self.client = boto3.client("cloudwatch")
            self.namespace = namespace
            self._available = True
        except Exception:
            self._available = False

    def put_job_processed(self, report_type: str, duration_seconds: float) -> None:
        """Record a successful job completion."""
        if not self._available:
            return
            
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
        if not self._available:
            return
            
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
        if not self._available:
            return
            
        self.client.put_metric_data(
            Namespace=self.namespace,
            MetricData=[
                {"MetricName": "BatchTotal", "Value": total, "Unit": "Count"},
                {"MetricName": "BatchSuccessful", "Value": successful, "Unit": "Count"},
                {"MetricName": "BatchFailed", "Value": failed, "Unit": "Count"},
            ],
        )


def create_cw_metrics_safe() -> Optional[CloudWatchMetrics]:
    """
    Create CloudWatch metrics client safely.
    
    Returns None if CloudWatch is not available (e.g., in local dev without credentials).
    This ensures backwards compatibility and matches the original interface.
    """
    try:
        return CloudWatchMetrics()
    except Exception:
        return None
