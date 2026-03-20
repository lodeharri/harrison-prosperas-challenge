"""Reto Prosperas - Hexagonal Architecture Backend.

This module contains the refactored backend following
Clean Architecture / Hexagonal Architecture principles.

Structure:
    src/
        domain/        # Core business logic (no dependencies)
        application/   # Use cases and ports
        adapters/      # Infrastructure implementations
        config/        # Configuration
        shared/        # Shared utilities
"""

# Import commonly used items for easy access
from backend.src.domain import Job, JobStatus
from backend.src.domain.exceptions import (
    DomainException,
    JobNotFoundException,
    InvalidJobStateException,
)
from backend.src.application import (
    JobRepository,
    JobQueue,
    CreateJobUseCase,
    GetJobUseCase,
    ListJobsUseCase,
)

__all__ = [
    # Domain
    "Job",
    "JobStatus",
    "DomainException",
    "JobNotFoundException",
    "InvalidJobStateException",
    # Application
    "JobRepository",
    "JobQueue",
    "CreateJobUseCase",
    "GetJobUseCase",
    "ListJobsUseCase",
]
