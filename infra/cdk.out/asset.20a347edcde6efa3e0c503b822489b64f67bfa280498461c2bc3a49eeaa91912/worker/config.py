"""Configuration settings for the worker module.

Loads configuration from environment variables with sensible defaults
for local development with LocalStack.

Supports two modes:
- LocalStack (development): AWS_ENDPOINT_URL is defined
- AWS Production: AWS_ENDPOINT_URL is NOT defined (uses native AWS endpoints)
"""

import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from dotenv import load_dotenv

load_dotenv()

LOG_LEVELS = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


def _is_localstack() -> bool:
    """Check if running with LocalStack (development mode).

    Returns True if AWS_ENDPOINT_URL is defined, False for production AWS.
    """
    return os.getenv("AWS_ENDPOINT_URL") is not None


class Settings(BaseSettings):
    """Worker settings loaded from environment variables.

    Detection Logic:
    - If AWS_ENDPOINT_URL is set → LocalStack (create resources, use local endpoints)
    - If AWS_ENDPOINT_URL is NOT set → AWS Production (CDK provisions resources)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =====================================================================
    # AWS Configuration
    # =====================================================================
    # AWS_ENDPOINT_URL: If set, use LocalStack. If not set, use native AWS.
    aws_endpoint_url: str | None = os.getenv("AWS_ENDPOINT_URL")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    aws_access_key_id: str | None = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")

    # =====================================================================
    # DynamoDB Tables (names defined by CDK for production)
    # =====================================================================
    # Production (AWS): harrison-jobs, harrison-idempotency
    # LocalStack (dev): jobs, idempotency_keys
    dynamodb_table_jobs: str = os.getenv("DYNAMODB_TABLE_JOBS", "jobs")

    # =====================================================================
    # SQS Queues (URLs provided by CDK for production)
    # =====================================================================
    # Production (AWS): Full SQS URLs from CDK
    # LocalStack (dev): LocalStack URLs with localhost:4566
    sqs_queue_url: str = os.getenv(
        "SQS_QUEUE_URL", "http://localhost:4566/000000000000/harrison-jobs-queue"
    )
    sqs_dlq_url: str = os.getenv(
        "SQS_DLQ_URL", "http://localhost:4566/000000000000/harrison-jobs-dlq"
    )
    sqs_priority_queue_url: str = os.getenv(
        "SQS_PRIORITY_QUEUE_URL",
        "http://localhost:4566/000000000000/harrison-jobs-priority",
    )

    # =====================================================================
    # Worker Settings
    # =====================================================================
    max_concurrent_jobs: int = int(os.getenv("MAX_CONCURRENT_JOBS", "10"))
    min_concurrent_jobs: int = int(os.getenv("MIN_CONCURRENT_JOBS", "2"))
    poll_interval_seconds: float = float(os.getenv("POLL_INTERVAL_SECONDS", "1.0"))
    max_receive_messages: int = int(os.getenv("MAX_RECEIVE_MESSAGES", "10"))
    visibility_timeout: int = int(os.getenv("VISIBILITY_TIMEOUT", "60"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))

    # =====================================================================
    # Processing
    # =====================================================================
    min_processing_time: float = float(os.getenv("MIN_PROCESSING_TIME", "5.0"))
    max_processing_time: float = float(os.getenv("MAX_PROCESSING_TIME", "30.0"))

    # =====================================================================
    # Circuit Breaker
    # =====================================================================
    circuit_breaker_failure_threshold: int = int(
        os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5")
    )
    circuit_breaker_recovery_timeout: int = int(
        os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT", "300")
    )

    # =====================================================================
    # Backoff
    # =====================================================================
    backoff_base_delay: float = float(os.getenv("BACKOFF_BASE_DELAY", "1.0"))
    backoff_max_delay: float = float(os.getenv("BACKOFF_MAX_DELAY", "60.0"))

    # =====================================================================
    # Logging
    # =====================================================================
    log_level: LOG_LEVELS = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def validate_log_level(cls, v: str | None) -> LOG_LEVELS:
        """Validate and normalize log level from environment variable."""
        if v is None:
            return "INFO"
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR"}
        upper = v.upper()
        if upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of: {valid_levels}")
        return upper  # type: ignore

    # =====================================================================
    # API Notification (for WebSocket notifications)
    # =====================================================================
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")

    # =====================================================================
    # Computed Properties
    # =====================================================================
    @property
    def is_localstack(self) -> bool:
        """Check if running with LocalStack."""
        return _is_localstack()

    @property
    def is_production(self) -> bool:
        """Check if running on AWS production."""
        return not _is_localstack()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
