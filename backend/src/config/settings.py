"""Application settings loaded from environment variables.

Centralized configuration following the Configuration Principle,
avoiding magic numbers and hardcoded values.
"""
import os
from dotenv import load_dotenv
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()
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
    aws_endpoint_url: str = os.getenv("AWS_ENDPOINT_URL")
    aws_region: str =  os.getenv("AWS_REGION")
    aws_access_key_id: str =  os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str =  os.getenv("AWS_SECRET_ACCESS_KEY")

    # DynamoDB
    dynamodb_table_jobs: str = os.getenv("DYNAMODB_TABLE_JOBS")
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

    # Backoff
    backoff_base_delay: float = 1.0
    backoff_max_delay: float = 60.0


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure only one Settings instance is created,
    following the Singleton pattern for configuration.
    """
    return Settings()
