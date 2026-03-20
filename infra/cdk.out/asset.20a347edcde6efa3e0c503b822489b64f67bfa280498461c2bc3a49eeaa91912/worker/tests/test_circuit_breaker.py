"""Tests for the circuit breaker implementation."""

import asyncio
import time
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from backend.worker.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.fixture
    def circuit_breaker(self) -> CircuitBreaker:
        """Create a circuit breaker for testing."""
        return CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=5,
            half_open_max_calls=1,
        )

    @pytest.mark.asyncio
    async def test_circuit_starts_closed(self, circuit_breaker: CircuitBreaker) -> None:
        """Test that circuit starts in closed state."""
        is_open, retry_after = await circuit_breaker.is_open("new_report_type")

        assert is_open is False
        assert retry_after == 0.0

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that circuit opens after failure threshold is reached."""
        report_type = "failing_report"

        # Record failures up to threshold
        for _ in range(3):
            await circuit_breaker.record_failure(report_type)

        is_open, retry_after = await circuit_breaker.is_open(report_type)

        assert is_open is True
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_circuit_closes_after_success(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that circuit closes after successful recovery in half-open state."""
        report_type = "recovering_report"

        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure(report_type)

        # Force to half-open state (simulate timeout passing)
        circuit = circuit_breaker._circuits[report_type]
        circuit.opened_at = 0  # Set to 0 so elapsed time check passes
        circuit.state = CircuitState.HALF_OPEN

        # Now record success should close the circuit
        await circuit_breaker.record_success(report_type)

        is_open, _ = await circuit_breaker.is_open(report_type)
        assert is_open is False

    @pytest.mark.asyncio
    async def test_circuit_moves_to_half_open_after_timeout(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that circuit moves to half-open after recovery timeout."""
        report_type = "timeout_report"

        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure(report_type)

        # Immediately check - should be open
        is_open, _ = await circuit_breaker.is_open(report_type)
        assert is_open is True

        # With very short timeout, simulate time passage
        # The implementation uses real time, so we need to adjust
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0)  # 0 second timeout
        for _ in range(3):
            await cb.record_failure(report_type)

        # Small sleep to ensure time passes
        await asyncio.sleep(0.1)

        is_open, _ = await cb.is_open(report_type)
        # Should be closed or half-open, not open
        assert is_open is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_success(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that call() executes function on closed circuit."""
        mock_func = AsyncMock(return_value="success")

        result = await circuit_breaker.call("test_report", mock_func)

        assert result == "success"
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_raises_when_open(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that call() raises CircuitBreakerOpenError when open."""
        report_type = "open_circuit_report"

        # Open the circuit
        for _ in range(3):
            await circuit_breaker.record_failure(report_type)

        mock_func = AsyncMock(return_value="success")

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await circuit_breaker.call(report_type, mock_func)

        assert exc_info.value.report_type == report_type
        mock_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_records_failure(
        self, circuit_breaker: CircuitBreaker
    ) -> None:
        """Test that call() records failures from wrapped function."""
        mock_func = AsyncMock(side_effect=ValueError("test error"))

        with pytest.raises(ValueError):
            await circuit_breaker.call("test_report", mock_func)

        # Circuit should have recorded the failure (1 failure recorded)
        # but not open yet (threshold is 3)
        stats = circuit_breaker.get_stats()
        assert "test_report" in stats
        assert stats["test_report"]["failures"] == 1

    @pytest.mark.asyncio
    async def test_get_stats(self, circuit_breaker: CircuitBreaker) -> None:
        """Test getting circuit breaker statistics."""
        # Add some circuits
        await circuit_breaker.record_failure("report1")
        await circuit_breaker.record_failure("report1")

        for _ in range(3):
            await circuit_breaker.record_failure("report2")

        stats = circuit_breaker.get_stats()

        assert "report1" in stats
        assert "report2" in stats
        assert stats["report1"]["failures"] == 2
        assert stats["report2"]["state"] == CircuitState.OPEN.value

    @pytest.mark.asyncio
    async def test_reset(self, circuit_breaker: CircuitBreaker) -> None:
        """Test resetting all circuits."""
        # Add some failures
        await circuit_breaker.record_failure("report1")
        await circuit_breaker.record_failure("report2")

        # Reset
        circuit_breaker.reset()

        stats = circuit_breaker.get_stats()
        assert len(stats) == 0

    @pytest.mark.asyncio
    async def test_half_open_allows_one_request(
        self,
    ) -> None:
        """Test that half-open state allows limited requests."""
        # Create circuit breaker with very short recovery timeout
        cb = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0,
            half_open_max_calls=1,
        )

        # Open the circuit (2 failures)
        for _ in range(2):
            await cb.record_failure("test_report")

        # Check state is now HALF_OPEN (since timeout is 0)
        # Actually with 0 timeout, is_open will immediately transition to HALF_OPEN
        is_open, _ = await cb.is_open("test_report")

        # Since timeout is 0, the circuit should move to HALF_OPEN state
        # and is_open returns False because half_open allows requests
        stats = cb.get_stats()
        assert stats["test_report"]["state"] == CircuitState.HALF_OPEN.value


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_circuit_state_values(self) -> None:
        """Test CircuitState enum values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.recovery_timeout == 300
        assert config.half_open_max_calls == 1

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=600,
            half_open_max_calls=3,
        )

        assert config.failure_threshold == 10
        assert config.recovery_timeout == 600
        assert config.half_open_max_calls == 3
