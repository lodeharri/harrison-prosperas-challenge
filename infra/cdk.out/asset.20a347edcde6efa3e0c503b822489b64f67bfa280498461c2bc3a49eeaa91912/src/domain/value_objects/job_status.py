"""JobStatus value object representing the state of a job.

This is a pure domain value object with no external dependencies.
"""

from enum import Enum


class JobStatus(str, Enum):
    """
    Enumeration representing possible job states.

    States follow a lifecycle:
    - PENDING: Job created, waiting to be processed
    - PROCESSING: Job is being processed
    - COMPLETED: Job finished successfully
    - FAILED: Job processing failed
    """

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

    def can_transition_to(self, target: "JobStatus") -> bool:
        """
        Check if a transition from this status to target is valid.

        Valid transitions:
        - PENDING -> PROCESSING
        - PROCESSING -> COMPLETED, FAILED
        """
        valid_transitions = {
            JobStatus.PENDING: {JobStatus.PROCESSING},
            JobStatus.PROCESSING: {JobStatus.COMPLETED, JobStatus.FAILED},
            JobStatus.COMPLETED: set(),  # Terminal state
            JobStatus.FAILED: set(),  # Terminal state
        }
        return target in valid_transitions.get(self, set())

    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in {JobStatus.COMPLETED, JobStatus.FAILED}

    def is_processing(self) -> bool:
        """Check if job is currently being processed."""
        return self == JobStatus.PROCESSING

    def is_pending(self) -> bool:
        """Check if job is pending."""
        return self == JobStatus.PENDING

    def is_completed(self) -> bool:
        """Check if job completed successfully."""
        return self == JobStatus.COMPLETED

    def is_failed(self) -> bool:
        """Check if job failed."""
        return self == JobStatus.FAILED
