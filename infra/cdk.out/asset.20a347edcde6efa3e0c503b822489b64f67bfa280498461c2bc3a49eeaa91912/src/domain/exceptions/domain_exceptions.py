"""Domain exceptions representing business rule violations.

These exceptions are used to express domain-level errors
without coupling to infrastructure concerns.
"""

from typing import Any

from backend.src.domain.value_objects.job_status import JobStatus


class DomainException(Exception):
    """
    Base exception for domain-level errors.

    Domain exceptions represent violations of business rules
    and should be caught and translated to appropriate
    HTTP responses at the application layer.
    """

    def __init__(
        self,
        message: str,
        code: str = "DOMAIN_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class JobNotFoundException(DomainException):
    """Exception raised when a job cannot be found."""

    def __init__(self, job_id: str) -> None:
        super().__init__(
            message=f"Job with id '{job_id}' not found",
            code="JOB_NOT_FOUND",
            details={"job_id": job_id},
        )
        self.job_id = job_id


class InvalidJobStateException(DomainException):
    """Exception raised when a job state transition is invalid."""

    def __init__(
        self,
        current_status: JobStatus,
        target_status: JobStatus,
        job_id: str,
    ) -> None:
        super().__init__(
            message=(
                f"Cannot transition job '{job_id}' from "
                f"{current_status.value} to {target_status.value}"
            ),
            code="INVALID_JOB_STATE",
            details={
                "job_id": job_id,
                "current_status": current_status.value,
                "target_status": target_status.value,
            },
        )
        self.current_status = current_status
        self.target_status = target_status
        self.job_id = job_id


class JobAccessDeniedException(DomainException):
    """Exception raised when user tries to access job they don't own."""

    def __init__(self, job_id: str, user_id: str) -> None:
        super().__init__(
            message=f"User '{user_id}' does not have access to job '{job_id}'",
            code="JOB_ACCESS_DENIED",
            details={"job_id": job_id, "user_id": user_id},
        )
        self.job_id = job_id
        self.user_id = user_id


class VersionConflictException(DomainException):
    """Raised when optimistic locking detects a version mismatch."""

    def __init__(
        self,
        job_id: str,
        expected_version: int,
        actual_version: int | None = None,
    ) -> None:
        details = {
            "job_id": job_id,
            "expected_version": expected_version,
        }
        if actual_version is not None:
            details["actual_version"] = actual_version

        super().__init__(
            message=(
                f"Job '{job_id}' was modified by another request. "
                f"Expected version {expected_version}"
                + (f", found {actual_version}" if actual_version is not None else "")
            ),
            code="VERSION_CONFLICT",
            details=details,
        )
        self.job_id = job_id
        self.expected_version = expected_version
        self.actual_version = actual_version
