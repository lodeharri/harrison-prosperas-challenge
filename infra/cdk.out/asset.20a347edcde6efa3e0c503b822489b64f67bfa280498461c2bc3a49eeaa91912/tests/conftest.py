"""Pytest configuration and fixtures."""

import pytest


def pytest_configure(config):
    """Configure pytest with test environment variables."""
    import os

    os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["AWS_ACCESS_KEY_ID"] = "test"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
    os.environ["DYNAMODB_TABLE_JOBS"] = "jobs-test"
    os.environ["SQS_QUEUE_URL"] = (
        "http://localhost:4566/000000000000/report-jobs-queue-test"
    )
    os.environ["JWT_SECRET_KEY"] = "test-secret-key"
    os.environ["JWT_ALGORITHM"] = "HS256"


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    from backend.src.config.settings import Settings

    return Settings(
        aws_endpoint_url="http://localhost:4566",
        aws_region="us-east-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        dynamodb_table_jobs="jobs-test",
        sqs_queue_url="http://localhost:4566/000000000000/report-jobs-queue-test",
        sqs_queue_name="report-jobs-queue-test",
        jwt_secret_key="test-secret-key",
        jwt_algorithm="HS256",
    )
