"""Job entity - Core domain model for a report job.

This is a pure domain entity with no external dependencies.
It encapsulates all business rules related to jobs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.src.domain.value_objects.job_status import JobStatus
from backend.src.domain.exceptions.domain_exceptions import InvalidJobStateException


@dataclass
class Job:
    """
    Domain entity representing a report job.

    This entity is immutable in terms of its identity (job_id).
    Status can be changed through the defined transitions.

    Attributes:
        job_id: Unique identifier for the job
        user_id: User who created the job
        report_type: Type of report to generate
        date_range: Date range for the report (YYYY-MM-DD to YYYY-MM-DD or 'all')
        format: Output format (pdf, csv, excel)
        status: Current job status
        created_at: When the job was created
        updated_at: When the job was last updated
        result_url: URL to download results (only if completed)
        version: Version number for optimistic locking
    """

    job_id: str
    user_id: str
    report_type: str
    date_range: str = "all"
    format: str = "pdf"
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    result_url: str | None = None
    version: int = 1

    @classmethod
    def create(
        cls,
        job_id: str,
        user_id: str,
        report_type: str,
        date_range: str = "all",
        format: str = "pdf",
    ) -> "Job":
        """
        Factory method to create a new job.

        Args:
            job_id: Unique identifier
            user_id: User creating the job
            report_type: Type of report
            date_range: Date range for the report
            format: Output format (pdf, csv, excel)

        Returns:
            New Job instance in PENDING status
        """
        return cls(
            job_id=job_id,
            user_id=user_id,
            report_type=report_type,
            date_range=date_range,
            format=format,
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            result_url=None,
            version=1,
        )

    def transition_to(self, new_status: JobStatus) -> None:
        """
        Transition the job to a new status.

        Args:
            new_status: Target status

        Raises:
            InvalidJobStateException: If transition is not allowed
        """
        if not self.status.can_transition_to(new_status):
            raise InvalidJobStateException(
                current_status=self.status,
                target_status=new_status,
                job_id=self.job_id,
            )
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)

    def mark_processing(self) -> None:
        """Mark job as being processed."""
        self.transition_to(JobStatus.PROCESSING)

    def mark_completed(self, result_url: str) -> None:
        """
        Mark job as completed with result URL.

        Args:
            result_url: URL to download the generated report
        """
        self.result_url = result_url
        self.transition_to(JobStatus.COMPLETED)

    def mark_failed(self) -> None:
        """Mark job as failed."""
        self.transition_to(JobStatus.FAILED)

    def belongs_to(self, user_id: str) -> bool:
        """Check if job belongs to the given user."""
        return self.user_id == user_id

    def can_be_cancelled(self) -> bool:
        """Check if job can be cancelled."""
        return self.status in {JobStatus.PENDING, JobStatus.PROCESSING}

    def to_dict(self) -> dict[str, Any]:
        """Convert entity to dictionary representation."""
        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "report_type": self.report_type,
            "date_range": self.date_range,
            "format": self.format,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "result_url": self.result_url,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Job":
        """
        Create Job entity from dictionary.

        Args:
            data: Dictionary with job data

        Returns:
            Job instance
        """
        # Parse datetime fields
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        elif created_at is None:
            created_at = datetime.now(timezone.utc)

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        elif updated_at is None:
            updated_at = datetime.now(timezone.utc)

        return cls(
            job_id=data["job_id"],
            user_id=data["user_id"],
            report_type=data["report_type"],
            date_range=data.get("date_range", "all"),
            format=data.get("format", "pdf"),
            status=JobStatus(data.get("status", "PENDING")),
            created_at=created_at,
            updated_at=updated_at,
            result_url=data.get("result_url"),
            version=data.get("version", 1),
        )
