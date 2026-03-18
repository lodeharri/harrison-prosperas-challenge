"""Shared Pydantic schemas for API request/response validation.

These schemas provide a clean interface between the domain entities
and the API layer.
"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from backend.src.domain.entities.job import Job
from backend.src.domain.value_objects.job_status import JobStatus


class JobStatusSchema(str):
    """JobStatus compatible with both domain and API."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Use domain JobStatus for consistency
JobStatus = JobStatus


class JobCreate(BaseModel):
    """Request schema for creating a new job."""

    report_type: Annotated[
        str,
        Field(min_length=1, max_length=100, description="Type of report to generate"),
    ]


class JobResponse(BaseModel):
    """Response schema for job details."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str = Field(description="Unique job identifier")
    user_id: str = Field(description="User who created the job")
    status: JobStatus = Field(description="Current job status")
    report_type: str = Field(description="Type of report")
    created_at: datetime = Field(description="Job creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    result_url: str | None = Field(
        default=None, description="URL to download result (if completed)"
    )

    @classmethod
    def from_entity(cls, job: Job) -> "JobResponse":
        """Create response from domain entity."""
        return cls(
            job_id=job.job_id,
            user_id=job.user_id,
            status=job.status,
            report_type=job.report_type,
            created_at=job.created_at,
            updated_at=job.updated_at,
            result_url=job.result_url,
        )


class JobCreateResponse(BaseModel):
    """Response schema for job creation."""

    job_id: str = Field(description="Unique job identifier")
    status: JobStatus = Field(description="Initial job status (PENDING)")


class JobListResponse(BaseModel):
    """Paginated response schema for job listing."""

    items: list[JobResponse] = Field(description="List of jobs")
    total: int = Field(description="Total number of jobs for the user")
    page: int = Field(description="Current page number (1-indexed)")
    page_size: int = Field(description="Number of items per page")


class TokenRequest(BaseModel):
    """Request schema for getting an access token (testing purposes)."""

    user_id: Annotated[str, Field(min_length=1, description="User identifier")]


class TokenResponse(BaseModel):
    """Response schema for access token."""

    access_token: str = Field(description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Token expiration time in seconds")


class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str = Field(description="Overall health status")
    version: str = Field(description="Application version")
    dependencies: dict[str, str] = Field(description="Status of each dependency")


class ErrorDetail(BaseModel):
    """Error detail schema."""

    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: dict | None = Field(default=None, description="Additional error details")


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: ErrorDetail = Field(description="Error information")
