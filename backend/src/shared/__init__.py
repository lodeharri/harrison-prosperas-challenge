"""Shared utilities for adapters and application."""

from backend.src.shared.exceptions import (
    AppException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from backend.src.shared.dependencies import get_current_user
from backend.src.shared.jwt_service import JWTService, get_jwt_service
from backend.src.shared.schemas import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    JobCreate,
    JobCreateResponse,
    JobListResponse,
    JobResponse,
    JobStatus,
    TokenRequest,
    TokenResponse,
)

__all__ = [
    # Exceptions
    "AppException",
    "ForbiddenException",
    "NotFoundException",
    "UnauthorizedException",
    # Dependencies
    "get_current_user",
    # JWT
    "JWTService",
    "get_jwt_service",
    # Schemas
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "JobCreate",
    "JobCreateResponse",
    "JobListResponse",
    "JobResponse",
    "JobStatus",
    "TokenRequest",
    "TokenResponse",
]
