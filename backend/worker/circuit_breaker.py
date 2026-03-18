"""Circuit breaker implementation for handling failing report types.

The circuit breaker pattern prevents cascading failures by temporarily
pausing processing for report types that have exceeded a failure threshold.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class Circuit:
    """Individual circuit for a report type."""

    failures: int = 0
    opened_at: float = 0.0
    state: CircuitState = CircuitState.CLOSED


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5
    recovery_timeout: int = 300  # 5 minutes
    half_open_max_calls: int = 1


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, report_type: str, retry_after: float):
        self.report_type = report_type
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker is open for '{report_type}'. "
            f"Retry after {retry_after:.0f} seconds."
        )


class CircuitBreaker:
    """
    Circuit breaker to pause processing for failing report types.

    The circuit breaker has three states:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests are rejected
    - HALF_OPEN: Testing if the service has recovered

    When the failure count exceeds `failure_threshold`, the circuit opens.
    After `recovery_timeout` seconds, it moves to HALF_OPEN state.
    In HALF_OPEN state, one test request is allowed.
    If it succeeds, the circuit closes; if it fails, it opens again.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,
        half_open_max_calls: int = 1,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before testing recovery
            half_open_max_calls: Max calls allowed in half-open state
        """
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_max_calls=half_open_max_calls,
        )
        self._circuits: dict[str, Circuit] = {}
        self._half_open_calls: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def is_open(self, report_type: str) -> tuple[bool, float]:
        """
        Check if circuit is open for a report type.

        Args:
            report_type: The report type to check

        Returns:
            Tuple of (is_open, retry_after_seconds)
        """
        async with self._lock:
            circuit = self._circuits.get(report_type)

            if circuit is None:
                return False, 0.0

            if circuit.state == CircuitState.CLOSED:
                return False, 0.0

            if circuit.state == CircuitState.OPEN:
                elapsed = time.time() - circuit.opened_at
                if elapsed >= self.config.recovery_timeout:
                    # Move to half-open state
                    circuit.state = CircuitState.HALF_OPEN
                    self._half_open_calls[report_type] = 0
                    logger.info(f"Circuit for '{report_type}' moved to HALF_OPEN")
                    return False, 0.0
                return True, self.config.recovery_timeout - elapsed

            if circuit.state == CircuitState.HALF_OPEN:
                current_calls = self._half_open_calls.get(report_type, 0)
                if current_calls >= self.config.half_open_max_calls:
                    return True, 1.0  # Retry soon
                return False, 0.0

            return False, 0.0

    async def record_success(self, report_type: str) -> None:
        """
        Record a successful call for a report type.

        Args:
            report_type: The report type that succeeded
        """
        async with self._lock:
            circuit = self._circuits.get(report_type)

            if circuit is None:
                return

            if circuit.state == CircuitState.HALF_OPEN:
                # Successful test call, close the circuit
                logger.info(
                    f"Circuit for '{report_type}' CLOSED after successful recovery"
                )
                self._circuits.pop(report_type, None)
                self._half_open_calls.pop(report_type, None)
            elif circuit.failures > 0:
                # Reset failure count on success in closed state
                circuit.failures = 0

    async def record_failure(self, report_type: str) -> None:
        """
        Record a failed call for a report type.

        Args:
            report_type: The report type that failed
        """
        async with self._lock:
            circuit = self._circuits.get(report_type)

            if circuit is None:
                circuit = Circuit()
                self._circuits[report_type] = circuit

            if circuit.state == CircuitState.HALF_OPEN:
                # Failed during recovery test, reopen
                circuit.opened_at = time.time()
                circuit.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit for '{report_type}' REOPENED after failed recovery test"
                )
                return

            circuit.failures += 1

            if circuit.failures >= self.config.failure_threshold:
                circuit.opened_at = time.time()
                circuit.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit for '{report_type}' OPENED after "
                    f"{circuit.failures} failures"
                )

    async def record_half_open_call(self, report_type: str) -> None:
        """Record a call made in half-open state."""
        async with self._lock:
            self._half_open_calls[report_type] = (
                self._half_open_calls.get(report_type, 0) + 1
            )

    async def call(
        self, report_type: str, func: Callable[..., T], *args: ..., **kwargs: ...
    ) -> T:
        """
        Execute a function with circuit breaker protection.

        Args:
            report_type: The report type being processed
            func: Async function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function call

        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        is_open, retry_after = await self.is_open(report_type)

        if is_open:
            raise CircuitBreakerOpenError(report_type, retry_after)

        circuit = self._circuits.get(report_type)
        if circuit and circuit.state == CircuitState.HALF_OPEN:
            await self.record_half_open_call(report_type)

        try:
            result = await func(*args, **kwargs)
            await self.record_success(report_type)
            return result
        except Exception as e:
            await self.record_failure(report_type)
            raise

    def get_stats(self) -> dict[str, dict[str, any]]:
        """Get statistics for all circuits."""
        stats = {}
        for report_type, circuit in self._circuits.items():
            stats[report_type] = {
                "state": circuit.state.value,
                "failures": circuit.failures,
                "opened_at": circuit.opened_at,
            }
        return stats

    def reset(self) -> None:
        """Reset all circuits to closed state."""
        self._circuits.clear()
        self._half_open_calls.clear()
        logger.info("All circuit breakers reset")
