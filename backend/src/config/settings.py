"""Application settings loaded from environment variables.

Centralized configuration following the Configuration Principle,
avoiding magic numbers and hardcoded values.

Supports two modes:
- LocalStack (development): AWS_ENDPOINT_URL is defined
- AWS Production: AWS_ENDPOINT_URL is NOT defined (uses native AWS endpoints)
"""

import os
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file for local development
from dotenv import load_dotenv

load_dotenv()


def _is_localstack() -> bool:
    """Check if running with LocalStack (development mode).

    Returns True if AWS_ENDPOINT_URL is defined, False for production AWS.
    """
    return os.getenv("AWS_ENDPOINT_URL") is not None


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All AWS, JWT, and application-specific settings are centralized here.
    This allows easy configuration changes without code modifications.

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
    aws_endpoint_url: str | None = os.getenv("AWS_ENDPOINT_URL") or None
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    aws_access_key_id: str | None = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = os.getenv("AWS_SECRET_ACCESS_KEY")

    # =====================================================================
    # DynamoDB Tables (names defined by CDK for production)
    # =====================================================================
    # Production (AWS): {STACK_PREFIX}-jobs, {STACK_PREFIX}-idempotency
    # LocalStack (dev): jobs, idempotency_keys
    dynamodb_table_jobs: str = os.getenv("DYNAMODB_TABLE_JOBS", "jobs")
    dynamodb_table_idempotency: str = os.getenv(
        "DYNAMODB_TABLE_IDEMPOTENCY", "idempotency_keys"
    )

    # =====================================================================
    # SQS Queues (URLs provided by CDK for production)
    # =====================================================================
    # Production (AWS): Full SQS URLs from CDK
    # LocalStack (dev): LocalStack URLs with localhost:4566
    # Note: Queue names should be set via environment variables
    sqs_queue_url: str = os.getenv(
        "SQS_QUEUE_URL", "http://localhost:4566/000000000000/report-jobs-queue"
    )
    sqs_queue_name: str = os.getenv("SQS_QUEUE_NAME", "report-jobs-queue")
    sqs_dlq_url: str = os.getenv(
        "SQS_DLQ_URL", "http://localhost:4566/000000000000/report-jobs-dlq"
    )
    sqs_priority_queue_url: str = os.getenv(
        "SQS_PRIORITY_QUEUE_URL",
        "http://localhost:4566/000000000000/report-jobs-priority",
    )

    # =====================================================================
    # JWT Authentication
    # =====================================================================
    # Production: JWT_SECRET_KEY from AWS Secrets Manager
    # LocalStack (dev): Default key for development only
    jwt_secret_key: str = os.getenv(
        "JWT_SECRET_KEY", "super-secret-key-change-in-production"
    )
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # =====================================================================
    # Application
    # =====================================================================
    app_name: str = "Reto Prosperas API"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # =====================================================================
    # CloudWatch (production only - metrics and logs)
    # =====================================================================
    cloudwatch_log_group: str = os.getenv(
        "CLOUDWATCH_LOG_GROUP", "/reto-prosperas/jobs"
    )
    cloudwatch_stream_name: str = os.getenv("CLOUDWATCH_STREAM_NAME", "worker")

    # =====================================================================
    # Backoff Configuration
    # =====================================================================
    backoff_base_delay: float = float(os.getenv("BACKOFF_BASE_DELAY", "1.0"))
    backoff_max_delay: float = float(os.getenv("BACKOFF_MAX_DELAY", "60.0"))

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
    """
    Get cached settings instance.

    Uses lru_cache to ensure only one Settings instance is created,
    following the Singleton pattern for configuration.
    """
    return Settings()
