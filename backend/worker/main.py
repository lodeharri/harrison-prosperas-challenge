"""Worker entry point with asyncio.gather for concurrent job processing."""

import asyncio
import logging
import signal
import sys
from typing import Any

import structlog

from backend.worker.config import get_settings
from backend.worker.processor import JobProcessor

# Configure structured logging
# Using stdlib logging as base to avoid structlog compatibility issues
import logging as stdlib_logging

stdlib_logging.basicConfig(
    format="%(message)s",
    level=stdlib_logging.INFO,
)

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.BoundLogger,
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger()


class WorkerManager:
    """Manages the worker lifecycle and graceful shutdown."""

    SHUTDOWN_TIMEOUT_SECONDS = 30  # Maximum time to wait for graceful shutdown

    def __init__(self) -> None:
        self.processor: JobProcessor | None = None
        self.tasks: list[asyncio.Task[Any]] = []
        self.shutdown_event = asyncio.Event()
        self._shutdown_with_timeout_setup = False

    async def start(self) -> None:
        """Start the worker and all background tasks."""
        settings = get_settings()

        # Configure logging level
        logging.getLogger().setLevel(getattr(logging, settings.log_level))

        logger.info(
            "worker_initializing",
            version="1.0.0",
            max_concurrent=settings.max_concurrent_jobs,
            sqs_queue=settings.sqs_queue_url,
            dynamodb_table=settings.dynamodb_table_jobs,
        )

        # Initialize processor
        self.processor = JobProcessor()

        # Setup signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(self.shutdown(s)),
            )

        try:
            # Verify connectivity
            health = await self.processor.health_check()
            logger.info("health_check", **health)

            if not health["sqs_healthy"]:
                logger.warning("SQS health check failed, but continuing...")
            if not health["dynamodb_healthy"]:
                logger.warning("DynamoDB health check failed, but continuing...")

            # Run the processor
            await self.processor.run()

        except asyncio.CancelledError:
            logger.info("Worker cancelled")
        except Exception as e:
            logger.error("Worker failed", error=str(e), error_type=type(e).__name__)
            raise
        finally:
            await self.shutdown()

    async def shutdown(self, sig: signal.Signals | None = None) -> None:
        """Gracefully shutdown the worker."""
        if sig:
            logger.info("shutdown_initiated", signal=sig.name if sig else None)
        else:
            logger.info("shutdown_initiated")

        # Setup safety timeout with signal.alarm
        # This ensures shutdown doesn't hang indefinitely
        if not self._shutdown_with_timeout_setup:
            self._shutdown_with_timeout_setup = True
            signal.signal(signal.SIGALRM, self._shutdown_timeout_handler)
            signal.alarm(self.SHUTDOWN_TIMEOUT_SECONDS)

        self.shutdown_event.set()

        if self.processor:
            await self.processor.stop()

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        # Cancel safety timeout
        signal.alarm(0)
        logger.info("shutdown_complete")

    def _shutdown_timeout_handler(self, signum: int, frame: Any) -> None:
        """Handle timeout during shutdown - forces exit."""
        logger.warning(
            "shutdown_timeout_forced",
            timeout_seconds=self.SHUTDOWN_TIMEOUT_SECONDS,
            message="Forcing worker shutdown due to timeout",
        )
        # Force exit - this is a last resort
        import os

        os._exit(1)


async def run_worker() -> None:
    """Main entry point for the worker."""
    manager = WorkerManager()
    await manager.start()


def main() -> None:
    """CLI entry point."""
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error("Worker failed to start", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
