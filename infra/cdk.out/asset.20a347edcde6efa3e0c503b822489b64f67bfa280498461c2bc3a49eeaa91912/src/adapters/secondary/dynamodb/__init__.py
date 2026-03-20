"""DynamoDB adapter for job persistence."""

from backend.src.adapters.secondary.dynamodb.job_repository import DynamoDBJobRepository

__all__ = ["DynamoDBJobRepository"]
