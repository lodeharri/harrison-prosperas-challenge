"""Shared exception classes for application layer.

These exceptions bridge domain exceptions to HTTP responses.
"""

from typing import Any

from fastapi import HTTPException, status


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        status_code: int,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "details": self.details,
            }
        }


class NotFoundException(AppException):
    """Resource not found exception."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            message=f"{resource} with id '{identifier}' not found",
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier},
        )


class UnauthorizedException(AppException):
    """Authentication required or failed exception."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message=message,
            error_code="UNAUTHORIZED",
        )


class ForbiddenException(AppException):
    """Access denied exception."""

    def __init__(self, message: str = "Access denied") -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            message=message,
            error_code="FORBIDDEN",
        )


class ConflictException(AppException):
    """Raised when there's a race condition conflict (e.g., version mismatch)."""

    def __init__(
        self,
        resource: str,
        message: str = "Resource was modified by another request",
        details: dict[str, Any] | None = None,
    ) -> None:
        # Merge resource into details
        merged_details = {"resource": resource}
        if details:
            merged_details.update(details)

        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            message=message,
            error_code="CONFLICT",
            details=merged_details,
        )


def http_exception_from_app_exception(exc: AppException) -> HTTPException:
    """Convert AppException to FastAPI HTTPException."""
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.to_dict(),
    )
