"""JobQueue port - Interface for job queue operations.

This port defines the contract for publishing jobs to a message queue.
Adapters (like SQS, RabbitMQ, in-memory) must implement this interface.
"""

from typing import Protocol, runtime_checkable

from backend.src.domain.entities.job import Job


@runtime_checkable
class JobQueue(Protocol):
    """
    Port interface for job queue operations.

    This interface enables the application to publish jobs
    for async processing without knowing the underlying queue implementation.

    Implementations:
        - SQSJobQueue: AWS SQS adapter
        - InMemoryJobQueue: For testing
        - RabbitMQJobQueue: Future adapter
    """

    def publish(self, job: Job) -> bool:
        """
        Publish a job to the queue for async processing.

        Args:
            job: The job to publish

        Returns:
            True if published successfully
        """
        ...

    async def publish_priority(self, job: Job) -> bool:
        """
        Publish a high-priority job to the priority queue.

        Args:
            job: The high-priority job to publish

        Returns:
            True if published successfully
        """
        ...

    def health_check(self) -> bool:
        """
        Check if the queue is accessible.

        Returns:
            True if healthy, False otherwise
        """
        ...
