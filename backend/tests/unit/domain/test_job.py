"""Tests for Job entity."""

import pytest
from datetime import datetime, timezone

from backend.src.domain.entities.job import Job
from backend.src.domain.value_objects.job_status import JobStatus
from backend.src.domain.exceptions.domain_exceptions import InvalidJobStateException


class TestJobCreation:
    """Tests for Job factory and creation."""

    def test_create_job_generates_pending_status(self):
        """Test that create() generates a job with PENDING status."""
        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )
        assert job.status == JobStatus.PENDING
        assert job.job_id == "test-123"
        assert job.user_id == "user-456"
        assert job.report_type == "sales_report"
        assert job.result_url is None

    def test_create_job_sets_timestamps(self):
        """Test that create() sets created_at and updated_at."""
        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )
        assert job.created_at is not None
        assert job.updated_at is not None
        assert isinstance(job.created_at, datetime)
        assert isinstance(job.updated_at, datetime)


class TestJobStatusTransitions:
    """Tests for job status transitions."""

    def test_can_transition_pending_to_processing(self):
        """Test that PENDING can transition to PROCESSING."""
        assert JobStatus.PENDING.can_transition_to(JobStatus.PROCESSING)

    def test_cannot_transition_pending_to_completed(self):
        """Test that PENDING cannot transition directly to COMPLETED."""
        assert not JobStatus.PENDING.can_transition_to(JobStatus.COMPLETED)

    def test_can_transition_processing_to_completed(self):
        """Test that PROCESSING can transition to COMPLETED."""
        assert JobStatus.PROCESSING.can_transition_to(JobStatus.COMPLETED)

    def test_can_transition_processing_to_failed(self):
        """Test that PROCESSING can transition to FAILED."""
        assert JobStatus.PROCESSING.can_transition_to(JobStatus.FAILED)

    def test_completed_is_terminal(self):
        """Test that COMPLETED is a terminal state."""
        assert JobStatus.COMPLETED.is_terminal()
        assert not JobStatus.COMPLETED.can_transition_to(JobStatus.PENDING)

    def test_failed_is_terminal(self):
        """Test that FAILED is a terminal state."""
        assert JobStatus.FAILED.is_terminal()
        assert not JobStatus.FAILED.can_transition_to(JobStatus.PENDING)


class TestJobTransitions:
    """Tests for Job entity transitions."""

    def test_mark_processing(self):
        """Test marking job as processing."""
        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )
        job.mark_processing()
        assert job.status == JobStatus.PROCESSING

    def test_mark_completed_with_result_url(self):
        """Test marking job as completed with result URL."""
        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )
        job.mark_processing()
        result_url = "https://example.com/results/test-123.pdf"
        job.mark_completed(result_url)
        assert job.status == JobStatus.COMPLETED
        assert job.result_url == result_url

    def test_invalid_transition_raises_exception(self):
        """Test that invalid transition raises exception."""
        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )
        with pytest.raises(InvalidJobStateException):
            job.mark_completed("https://example.com/result")

    def test_mark_failed(self):
        """Test marking job as failed."""
        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )
        job.mark_processing()
        job.mark_failed()
        assert job.status == JobStatus.FAILED


class TestJobOwnership:
    """Tests for job ownership verification."""

    def test_belongs_to_returns_true_for_owner(self):
        """Test that belongs_to returns True for the owner."""
        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )
        assert job.belongs_to("user-456")

    def test_belongs_to_returns_false_for_non_owner(self):
        """Test that belongs_to returns False for non-owner."""
        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )
        assert not job.belongs_to("other-user")


class TestJobSerialization:
    """Tests for job serialization."""

    def test_to_dict(self):
        """Test converting job to dictionary."""
        job = Job.create(
            job_id="test-123",
            user_id="user-456",
            report_type="sales_report",
        )
        data = job.to_dict()
        assert data["job_id"] == "test-123"
        assert data["user_id"] == "user-456"
        assert data["report_type"] == "sales_report"
        assert data["status"] == "PENDING"
        assert "created_at" in data
        assert "updated_at" in data

    def test_from_dict(self):
        """Test creating job from dictionary."""
        data = {
            "job_id": "test-123",
            "user_id": "user-456",
            "report_type": "sales_report",
            "status": "PROCESSING",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-01T00:01:00+00:00",
        }
        job = Job.from_dict(data)
        assert job.job_id == "test-123"
        assert job.status == JobStatus.PROCESSING
