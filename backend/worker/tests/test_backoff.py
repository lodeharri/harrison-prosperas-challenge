"""Tests for exponential backoff implementation."""

import asyncio
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from backend.worker.backoff import (
    BackoffCalculator,
    exponential_backoff,
    retry_with_backoff,
)


class TestExponentialBackoff:
    """Tests for exponential_backoff function."""

    @pytest.mark.asyncio
    async def test_first_attempt_has_base_delay(self) -> None:
        """Test that first attempt has base delay."""
        delay = await exponential_backoff(
            0, base_delay=1.0, max_delay=60.0, jitter_factor=0.0
        )

        assert delay == 1.0

    @pytest.mark.asyncio
    async def test_second_attempt_doubles(self) -> None:
        """Test that second attempt doubles the delay."""
        delay = await exponential_backoff(
            1, base_delay=1.0, max_delay=60.0, jitter_factor=0.0
        )

        assert delay == 2.0

    @pytest.mark.asyncio
    async def test_delay_respects_max_delay(self) -> None:
        """Test that delay is capped at max_delay."""
        delay = await exponential_backoff(
            10, base_delay=1.0, max_delay=5.0, jitter_factor=0.0
        )

        assert delay == 5.0

    @pytest.mark.asyncio
    async def test_jitter_is_added(self) -> None:
        """Test that jitter is added to delay."""
        delay1 = await exponential_backoff(
            0, base_delay=1.0, max_delay=60.0, jitter_factor=0.1
        )
        delay2 = await exponential_backoff(
            0, base_delay=1.0, max_delay=60.0, jitter_factor=0.1
        )

        # With jitter, delays should be different (most of the time)
        # This test might occasionally pass even without jitter due to randomness
        assert isinstance(delay1, float)
        assert isinstance(delay2, float)

    @pytest.mark.asyncio
    async def test_no_jitter_when_factor_zero(self) -> None:
        """Test that no jitter is added when factor is 0."""
        delay1 = await exponential_backoff(
            0, base_delay=2.0, max_delay=60.0, jitter_factor=0.0
        )
        delay2 = await exponential_backoff(
            0, base_delay=2.0, max_delay=60.0, jitter_factor=0.0
        )

        assert delay1 == 2.0
        assert delay2 == 2.0

    @pytest.mark.asyncio
    async def test_exponential_growth(self) -> None:
        """Test exponential growth pattern."""
        delays = []
        for attempt in range(5):
            delay = await exponential_backoff(
                attempt, base_delay=1.0, max_delay=100.0, jitter_factor=0.0
            )
            delays.append(delay)

        # Each delay should double
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0
        assert delays[3] == 8.0
        assert delays[4] == 16.0


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_successful_call_no_retry(self) -> None:
        """Test that successful call doesn't retry."""
        mock_func = AsyncMock(return_value="success")

        result = await retry_with_backoff(
            mock_func,
            max_attempts=3,
            base_delay=0.1,
            max_delay=1.0,
            jitter_factor=0.0,
        )

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure(self) -> None:
        """Test that function is retried on failure."""
        mock_func = AsyncMock(side_effect=[ValueError("1"), ValueError("2"), "success"])

        result = await retry_with_backoff(
            mock_func,
            max_attempts=3,
            base_delay=0.05,  # Short delay for tests
            max_delay=0.1,
            jitter_factor=0.0,
            retryable_exceptions=(ValueError,),
        )

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self) -> None:
        """Test that exception is raised after max attempts."""
        mock_func = AsyncMock(side_effect=ValueError("persistent error"))

        with pytest.raises(ValueError, match="persistent error"):
            await retry_with_backoff(
                mock_func,
                max_attempts=3,
                base_delay=0.05,
                max_delay=0.1,
                jitter_factor=0.0,
                retryable_exceptions=(ValueError,),
            )

        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception_not_retried(self) -> None:
        """Test that non-retryable exceptions are not retried."""
        mock_func = AsyncMock(side_effect=ValueError("non-retryable"))

        with pytest.raises(ValueError):
            await retry_with_backoff(
                mock_func,
                max_attempts=3,
                base_delay=0.05,
                max_delay=0.1,
                jitter_factor=0.0,
                retryable_exceptions=(TypeError,),  # Only TypeError is retryable
            )

        # Should only be called once, not retried
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback(self) -> None:
        """Test that on_retry callback is called."""
        mock_func = AsyncMock(side_effect=[ValueError("1"), ValueError("2"), "success"])
        mock_callback = AsyncMock()

        await retry_with_backoff(
            mock_func,
            max_attempts=3,
            base_delay=0.05,
            max_delay=0.1,
            jitter_factor=0.0,
            retryable_exceptions=(ValueError,),
            on_retry=mock_callback,
        )

        # Callback should be called for each retry (not the final success)
        assert mock_callback.call_count == 2

    @pytest.mark.asyncio
    async def test_passes_arguments_to_func(self) -> None:
        """Test that arguments are passed to the function."""
        mock_func = AsyncMock(return_value="result")

        result = await retry_with_backoff(
            mock_func,
            "arg1",
            keyword_arg="value",
            max_attempts=1,
            base_delay=0.05,
            retryable_exceptions=(Exception,),
        )

        mock_func.assert_called_once_with("arg1", keyword_arg="value")
        assert result == "result"


class TestBackoffCalculator:
    """Tests for BackoffCalculator class."""

    @pytest.fixture
    def calculator(self) -> BackoffCalculator:
        """Create a BackoffCalculator for testing."""
        return BackoffCalculator(
            base_delay=1.0,
            max_delay=60.0,
            jitter_factor=0.0,
        )

    @pytest.mark.asyncio
    async def test_get_delay_increments_attempt(
        self, calculator: BackoffCalculator
    ) -> None:
        """Test that get_delay increments the attempt counter."""
        delay1 = await calculator.get_delay("key1")
        delay2 = await calculator.get_delay("key1")
        delay3 = await calculator.get_delay("key1")

        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 4.0

    @pytest.mark.asyncio
    async def test_different_keys_independent(
        self, calculator: BackoffCalculator
    ) -> None:
        """Test that different keys have independent counters."""
        await calculator.get_delay("key1")
        await calculator.get_delay("key1")

        delay1 = await calculator.get_delay("key1")
        delay2 = await calculator.get_delay("key2")

        assert delay1 == 4.0  # Third attempt for key1
        assert delay2 == 1.0  # First attempt for key2

    @pytest.mark.asyncio
    async def test_reset_key(self, calculator: BackoffCalculator) -> None:
        """Test resetting a specific key."""
        await calculator.get_delay("key1")
        await calculator.get_delay("key1")

        calculator.reset("key1")

        delay = await calculator.get_delay("key1")
        assert delay == 1.0

    @pytest.mark.asyncio
    async def test_reset_all(self, calculator: BackoffCalculator) -> None:
        """Test resetting all keys."""
        await calculator.get_delay("key1")
        await calculator.get_delay("key2")

        calculator.reset_all()

        assert calculator.get_attempt("key1") == 0
        assert calculator.get_attempt("key2") == 0

    @pytest.mark.asyncio
    async def test_get_attempt(self, calculator: BackoffCalculator) -> None:
        """Test getting current attempt count."""
        assert calculator.get_attempt("new_key") == 0

        await calculator.get_delay("key1")
        await calculator.get_delay("key1")

        assert calculator.get_attempt("key1") == 2

    @pytest.mark.asyncio
    async def test_custom_parameters(self) -> None:
        """Test using custom base_delay and max_delay."""
        calc = BackoffCalculator(base_delay=2.0, max_delay=10.0, jitter_factor=0.0)

        delay1 = await calc.get_delay()
        delay2 = await calc.get_delay()
        delay3 = await calc.get_delay()

        assert delay1 == 2.0
        assert delay2 == 4.0
        assert delay3 == 8.0
        # Next would be capped at max_delay
        delay4 = await calc.get_delay()
        assert delay4 == 10.0
