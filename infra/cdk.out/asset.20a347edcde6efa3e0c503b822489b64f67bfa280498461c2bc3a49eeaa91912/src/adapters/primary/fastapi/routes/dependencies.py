"""Dependency injection for FastAPI routes.

This module provides FastAPI dependencies that inject
use cases and services into route handlers.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.src.adapters.secondary.dynamodb.job_repository import DynamoDBJobRepository
from backend.src.adapters.secondary.sqs.job_queue import SQSJobQueue
from backend.src.application.ports.job_queue import JobQueue
from backend.src.application.ports.job_repository import JobRepository
from backend.src.application.use_cases.create_job import CreateJobUseCase
from backend.src.application.use_cases.get_job import GetJobUseCase
from backend.src.application.use_cases.list_jobs import ListJobsUseCase
from backend.src.config.settings import Settings, get_settings
from backend.src.shared.exceptions import UnauthorizedException
from backend.src.shared.jwt_service import JWTService, get_jwt_service

# HTTP Bearer scheme
security = HTTPBearer()


def get_job_repository() -> JobRepository:
    """Get the job repository singleton."""
    return DynamoDBJobRepository()


def get_job_queue() -> JobQueue:
    """Get the job queue singleton."""
    return SQSJobQueue()


def get_create_job_use_case(
    repository: Annotated[JobRepository, Depends(get_job_repository)],
    queue: Annotated[JobQueue, Depends(get_job_queue)],
) -> CreateJobUseCase:
    """Create CreateJobUseCase with injected dependencies."""
    return CreateJobUseCase(
        job_repository=repository,
        job_queue=queue,
    )


def get_get_job_use_case(
    repository: Annotated[JobRepository, Depends(get_job_repository)],
) -> GetJobUseCase:
    """Create GetJobUseCase with injected dependencies."""
    return GetJobUseCase(job_repository=repository)


def get_list_jobs_use_case(
    repository: Annotated[JobRepository, Depends(get_job_repository)],
) -> ListJobsUseCase:
    """Create ListJobsUseCase with injected dependencies."""
    return ListJobsUseCase(job_repository=repository)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    jwt_service: Annotated[JWTService, Depends(get_jwt_service)],
) -> str:
    """
    Dependency to get the current authenticated user from JWT token.

    Args:
        credentials: The HTTP Bearer credentials
        jwt_service: The JWT service

    Returns:
        The user_id from the verified token

    Raises:
        UnauthorizedException: If authentication fails
    """
    return jwt_service.verify_token(credentials.credentials)


__all__ = [
    "get_current_user",
    "get_job_repository",
    "get_job_queue",
    "get_create_job_use_case",
    "get_get_job_use_case",
    "get_list_jobs_use_case",
    "get_jwt_service",
]
