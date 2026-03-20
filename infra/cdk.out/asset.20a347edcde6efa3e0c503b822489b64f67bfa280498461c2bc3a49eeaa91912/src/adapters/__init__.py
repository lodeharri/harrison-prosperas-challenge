"""Adapters layer - Concrete implementations of ports.

Primary adapters handle input (e.g., FastAPI routes).
Secondary adapters handle output (e.g., DynamoDB, SQS).
"""

from backend.src.adapters.secondary.dynamodb.job_repository import DynamoDBJobRepository
from backend.src.adapters.secondary.sqs.job_queue import SQSJobQueue

__all__ = [
    "DynamoDBJobRepository",
    "SQSJobQueue",
]
