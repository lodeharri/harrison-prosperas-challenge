"""Application settings loaded from environment variables.

Centralized configuration following the Configuration Principle,
avoiding magic numbers and hardcoded values.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All AWS, JWT, and application-specific settings are centralized here.
    This allows easy configuration changes without code modifications.
    """

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
    dynamodb_table_idempotency: str = "idempotency_keys"

    # SQS
    sqs_queue_url: str = "http://localhost:4566/000000000000/report-jobs-queue"
    sqs_queue_name: str = "report-jobs-queue"
    sqs_dlq_url: str = "http://localhost:4566/000000000000/report-jobs-dlq"
    sqs_priority_queue_url: str = (
        "http://localhost:4566/000000000000/report-jobs-priority"
    )

    # JWT Authentication
    jwt_secret_key: str = "super-secret-key-change-in-production"
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # Application
    app_name: str = "Reto Prosperas API"
    app_version: str = "1.0.0"
    debug: bool = False

    # CloudWatch
    cloudwatch_log_group: str = "/reto-prosperas/jobs"
    cloudwatch_stream_name: str = "worker"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure only one Settings instance is created,
    following the Singleton pattern for configuration.
    """
    return Settings()
