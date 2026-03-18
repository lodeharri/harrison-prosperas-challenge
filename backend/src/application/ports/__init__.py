"""Ports (interfaces) for the application layer.

Ports define the contracts that adapters must implement,
enabling dependency inversion throughout the application.
"""

from backend.src.application.ports.job_repository import JobRepository
from backend.src.application.ports.job_queue import JobQueue

__all__ = ["JobRepository", "JobQueue"]
