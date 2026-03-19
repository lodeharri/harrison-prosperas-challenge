"""Configuration settings for the worker module.

Loads configuration from environment variables with sensible defaults
for local development with LocalStack.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Worker settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # AWS Configuration
    aws_endpoint_url: str = "http://localhost:4566"
    aws_region: str = "us-east-1"
    aws_access_key_id: str = "test"
    aws_secret_access_key: str = "test"

    # DynamoDB
    dynamodb_table_jobs: str = "jobs"

    # SQS
    sqs_queue_url: str = "http://localhost:4566/000000000000/report-jobs-queue"
    sqs_dlq_url: str = "http://localhost:4566/000000000000/report-jobs-dlq"
    sqs_priority_queue_url: str = (
        "http://localhost:4566/000000000000/report-jobs-priority"
    )

    # Worker Settings
    max_concurrent_jobs: int = 10
    min_concurrent_jobs: int = 2
    poll_interval_seconds: float = 1.0
    max_receive_messages: int = 10
    visibility_timeout: int = 60
    max_retries: int = 3

    # Processing
    min_processing_time: float = 5.0
    max_processing_time: float = 30.0

    # Circuit Breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 300

    # Backoff
    backoff_base_delay: float = 1.0
    backoff_max_delay: float = 60.0

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # API Notification (for WebSocket notifications)
    api_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
