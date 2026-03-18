"""Tests for schemas and API responses."""

import pytest
from datetime import datetime, timezone

from backend.src.domain.entities.job import Job
from backend.src.domain.value_objects.job_status import JobStatus
from backend.src.shared.schemas import (
    JobCreate,
    JobCreateResponse,
    JobListResponse,
    JobResponse,
    JobStatus as JobStatusSchema,
    TokenResponse,
    HealthResponse,
    ErrorDetail,
    ErrorResponse,
)


class TestJobSchemas:
    """Tests for Pydantic job schemas."""

    def test_job_create_requires_report_type(self):
        """Test that JobCreate requires report_type field."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            JobCreate()

    def test_job_create_validates_empty_report_type(self):
        """Test that JobCreate validates report_type is not empty."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            JobCreate(report_type="")

    def test_job_create_accepts_valid_report_type(self):
        """Test that JobCreate accepts valid report_type."""
        job = JobCreate(report_type="sales_report")
        assert job.report_type == "sales_report"

    def test_job_create_response_has_required_fields(self):
        """Test that JobCreateResponse has required fields."""
        response = JobCreateResponse(
            job_id="test-123",
            status=JobStatusSchema.PENDING,
        )
        assert response.job_id == "test-123"
        assert response.status == JobStatusSchema.PENDING

    def test_job_list_response_structure(self):
        """Test that JobListResponse has correct structure."""
        response = JobListResponse(
            items=[],
            total=0,
            page=1,
            page_size=20,
        )
        assert response.items == []
        assert response.total == 0
        assert response.page == 1
        assert response.page_size == 20

    def test_job_response_from_entity(self):
        """Test that JobResponse can be created from domain entity."""
        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )
        response = JobResponse.from_entity(job)
        assert response.job_id == "test-123"
        assert response.user_id == "user-456"
        assert response.status == JobStatusSchema.PENDING
        assert response.result_url is None


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_job_status_values(self):
        """Test that JobStatus has expected values."""
        assert JobStatusSchema.PENDING.value == "PENDING"
        assert JobStatusSchema.PROCESSING.value == "PROCESSING"
        assert JobStatusSchema.COMPLETED.value == "COMPLETED"
        assert JobStatusSchema.FAILED.value == "FAILED"

    def test_job_status_is_string(self):
        """Test that JobStatus values are strings."""
        assert isinstance(JobStatusSchema.PENDING, str)
        assert JobStatusSchema.PENDING == "PENDING"


class TestExceptions:
    """Tests for exception handling."""

    def test_not_found_exception(self):
        """Test NotFoundException creation."""
        from backend.src.shared.exceptions import NotFoundException

        exc = NotFoundException("Job", "test-123")
        assert exc.status_code == 404
        assert "test-123" in exc.message
        assert exc.error_code == "NOT_FOUND"

    def test_unauthorized_exception(self):
        """Test UnauthorizedException creation."""
        from backend.src.shared.exceptions import UnauthorizedException

        exc = UnauthorizedException("Invalid token")
        assert exc.status_code == 401
        assert exc.error_code == "UNAUTHORIZED"

    def test_forbidden_exception(self):
        """Test ForbiddenException creation."""
        from backend.src.shared.exceptions import ForbiddenException

        exc = ForbiddenException()
        assert exc.status_code == 403
        assert exc.error_code == "FORBIDDEN"

    def test_app_exception_to_dict(self):
        """Test AppException.to_dict() method."""
        from backend.src.shared.exceptions import AppException

        exc = AppException(
            status_code=400,
            message="Test error",
            error_code="TEST_ERROR",
        )
        result = exc.to_dict()

        assert "error" in result
        assert result["error"]["code"] == "TEST_ERROR"
        assert result["error"]["message"] == "Test error"


class TestHealthResponse:
    """Tests for health response schema."""

    def test_health_response_schema(self):
        """Test HealthResponse schema structure."""
        response = HealthResponse(
            status="healthy",
            version="1.0.0",
            dependencies={"dynamodb": "ok", "sqs": "ok"},
        )
        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.dependencies["dynamodb"] == "ok"


class TestErrorResponse:
    """Tests for error response schema."""

    def test_error_detail_schema(self):
        """Test ErrorDetail schema."""
        error = ErrorDetail(
            code="ERROR_CODE",
            message="Error message",
            details={"key": "value"},
        )
        assert error.code == "ERROR_CODE"
        assert error.message == "Error message"
        assert error.details["key"] == "value"

    def test_error_response_schema(self):
        """Test ErrorResponse schema."""
        response = ErrorResponse(
            error=ErrorDetail(
                code="ERROR_CODE",
                message="Error message",
            )
        )
        assert response.error.code == "ERROR_CODE"
