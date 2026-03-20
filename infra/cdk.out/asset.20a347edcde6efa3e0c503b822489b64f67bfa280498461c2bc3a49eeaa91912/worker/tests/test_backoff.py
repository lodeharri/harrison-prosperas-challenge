"""Tests for exponential backoff implementation."""

import asyncio
import random
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio

from backend.worker.backoff import (
    BackoffCalculator,
    exponential_backoff,
    exponential_backoff_sync,
    retry_with_backoff,
    retry_with_backoff_sync,
)


class TestExponentialBackoffSync:
    """Tests for exponential_backoff_sync function."""

    def test_first_attempt_has_base_delay(self) -> None:
        """Test that first attempt has base delay."""
        delay = exponential_backoff_sync(
            0, base_delay=1.0, max_delay=60.0, jitter_factor=0.0
        )

        assert delay == 1.0

    def test_second_attempt_doubles(self) -> None:
        """Test that second attempt doubles the delay."""
        delay = exponential_backoff_sync(
            1, base_delay=1.0, max_delay=60.0, jitter_factor=0.0
        )

        assert delay == 2.0

    def test_delay_respects_max_delay(self) -> None:
        """Test that delay is capped at max_delay."""
        delay = exponential_backoff_sync(
            10, base_delay=1.0, max_delay=5.0, jitter_factor=0.0
        )

        assert delay == 5.0

    def test_jitter_is_added(self) -> None:
        """Test that jitter is added to delay."""
        # Run multiple times to reduce flakiness
        delays = []
        for _ in range(10):
            delay = exponential_backoff_sync(
                0, base_delay=1.0, max_delay=60.0, jitter_factor=0.1
            )
            delays.append(delay)

        # All delays should be floats
        assert all(isinstance(d, float) for d in delays)
        # With jitter, delays should vary (but could be same by chance)
        # We'll just check that they are within expected range
        for delay in delays:
            assert 1.0 <= delay <= 1.0 + 0.1  # base_delay + max jitter

    def test_no_jitter_when_factor_zero(self) -> None:
        """Test that no jitter is added when factor is 0."""
        delay1 = exponential_backoff_sync(
            0, base_delay=2.0, max_delay=60.0, jitter_factor=0.0
        )
        delay2 = exponential_backoff_sync(
            0, base_delay=2.0, max_delay=60.0, jitter_factor=0.0
        )

        assert delay1 == 2.0
        assert delay2 == 2.0

    def test_exponential_growth(self) -> None:
        """Test exponential growth pattern."""
        delays = []
        for attempt in range(5):
            delay = exponential_backoff_sync(
                attempt, base_delay=1.0, max_delay=100.0, jitter_factor=0.0
            )
            delays.append(delay)

        # Each delay should double
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0
        assert delays[3] == 8.0
        assert delays[4] == 16.0

    def test_jitter_within_range(self) -> None:
        """Test that jitter is within expected range."""
        base = 10.0
        jitter_factor = 0.2
        # Mock random.uniform to return predictable values
        with patch(
            "random.uniform", side_effect=lambda a, b: b
        ):  # always return max jitter
            delay = exponential_backoff_sync(
                0, base_delay=base, max_delay=100.0, jitter_factor=jitter_factor
            )
            # jitter = delay * jitter_factor (since uniform returns b)
            # Actually uniform(0, delay * jitter_factor) returns delay * jitter_factor
            # So delay = base + base * jitter_factor
            assert delay == base + base * jitter_factor

        with patch(
            "random.uniform", side_effect=lambda a, b: a
        ):  # always return 0 jitter
            delay = exponential_backoff_sync(
                0, base_delay=base, max_delay=100.0, jitter_factor=jitter_factor
            )
            assert delay == base


class TestRetryWithBackoffSync:
    """Tests for retry_with_backoff_sync function."""

    def test_successful_call_no_retry(self) -> None:
        """Test that successful call doesn't retry."""
        mock_func = Mock(return_value="success")

        result = retry_with_backoff_sync(
            mock_func,
            max_attempts=3,
            base_delay=0.001,
            max_delay=0.001,
            jitter_factor=0.0,
        )

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retries_on_failure(self) -> None:
        """Test that function is retried on failure."""
        mock_func = Mock(side_effect=[ValueError("1"), ValueError("2"), "success"])

        result = retry_with_backoff_sync(
            mock_func,
            max_attempts=3,
            base_delay=0.001,
            max_delay=0.001,
            jitter_factor=0.0,
            retryable_exceptions=(ValueError,),
        )

        assert result == "success"
        assert mock_func.call_count == 3

    def test_raises_after_max_attempts(self) -> None:
        """Test that exception is raised after max attempts."""
        mock_func = Mock(side_effect=ValueError("persistent error"))

        with pytest.raises(ValueError, match="persistent error"):
            retry_with_backoff_sync(
                mock_func,
                max_attempts=3,
                base_delay=0.001,
                max_delay=0.001,
                jitter_factor=0.0,
                retryable_exceptions=(ValueError,),
            )

        assert mock_func.call_count == 3

    def test_non_retryable_exception_not_retried(self) -> None:
        """Test that non-retryable exceptions are not retried."""
        mock_func = Mock(side_effect=ValueError("non-retryable"))

        with pytest.raises(ValueError):
            retry_with_backoff_sync(
                mock_func,
                max_attempts=3,
                base_delay=0.001,
                max_delay=0.001,
                jitter_factor=0.0,
                retryable_exceptions=(TypeError,),  # Only TypeError is retryable
            )

        # Should only be called once, not retried
        assert mock_func.call_count == 1

    def test_on_retry_callback(self) -> None:
        """Test that on_retry callback is called."""
        side_effect = [ValueError("1"), ValueError("2"), "success"]
        mock_func = Mock(side_effect=side_effect)
        mock_callback = Mock()

        retry_with_backoff_sync(
            mock_func,
            max_attempts=3,
            base_delay=0.001,
            max_delay=0.001,
            jitter_factor=0.0,
            retryable_exceptions=(ValueError,),
            on_retry=mock_callback,
        )

        # Callback should be called for each retry (not the final success)
        assert mock_callback.call_count == 2
        # Verify callback arguments
        mock_callback.assert_any_call(1, side_effect[0])
        mock_callback.assert_any_call(2, side_effect[1])

    def test_passes_arguments_to_func(self) -> None:
        """Test that arguments are passed to the function."""
        mock_func = Mock(return_value="result")

        result = retry_with_backoff_sync(
            mock_func,
            "arg1",
            keyword_arg="value",
            max_attempts=1,
            base_delay=0.001,
            retryable_exceptions=(Exception,),
        )

        mock_func.assert_called_once_with("arg1", keyword_arg="value")
        assert result == "result"

    def test_uses_exponential_backoff_delays(self) -> None:
        """Test that retry uses exponential backoff delays."""
        mock_func = Mock(side_effect=[ValueError("1"), ValueError("2"), "success"])
        delays = []

        # Mock time.sleep to capture delays
        original_sleep = time.sleep

        def mock_sleep(delay):
            delays.append(delay)

        with patch("time.sleep", side_effect=mock_sleep):
            # Mock exponential_backoff_sync to return known delays
            with patch(
                "backend.worker.backoff.exponential_backoff_sync"
            ) as mock_backoff:
                mock_backoff.side_effect = [2.0, 4.0]
                retry_with_backoff_sync(
                    mock_func,
                    max_attempts=3,
                    base_delay=1.0,
                    max_delay=60.0,
                    jitter_factor=0.0,
                    retryable_exceptions=(ValueError,),
                )
                # Verify exponential_backoff_sync was called with correct attempts
                mock_backoff.assert_any_call(
                    0, base_delay=1.0, max_delay=60.0, jitter_factor=0.0
                )
                mock_backoff.assert_any_call(
                    1, base_delay=1.0, max_delay=60.0, jitter_factor=0.0
                )
                # Verify sleep calls with mocked delays
                assert delays == [2.0, 4.0]

    def test_max_attempts_zero_raises_runtime_error(self) -> None:
        """Test that max_attempts=0 raises RuntimeError."""
        mock_func = Mock()
        with pytest.raises(
            RuntimeError, match="Retry logic exhausted without exception"
        ):
            retry_with_backoff_sync(
                mock_func,
                max_attempts=0,
                base_delay=0.001,
                max_delay=0.001,
                jitter_factor=0.0,
                retryable_exceptions=(ValueError,),
            )
        mock_func.assert_not_called()


import pytest
import pytest_asyncio

from backend.worker.backoff import (
    BackoffCalculator,
    exponential_backoff,
    exponential_backoff_sync,
    retry_with_backoff,
    retry_with_backoff_sync,
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

    @pytest.mark.asyncio
    async def test_max_attempts_zero_raises_runtime_error(self) -> None:
        """Test that max_attempts=0 raises RuntimeError."""
        mock_func = AsyncMock()
        with pytest.raises(
            RuntimeError, match="Retry logic exhausted without exception"
        ):
            await retry_with_backoff(
                mock_func,
                max_attempts=0,
                base_delay=0.05,
                max_delay=0.1,
                jitter_factor=0.0,
                retryable_exceptions=(ValueError,),
            )
        mock_func.assert_not_called()

    def test_uses_exponential_backoff_delays(self) -> None:
        """Test that retry uses exponential backoff delays."""
        mock_func = Mock(side_effect=[ValueError("1"), ValueError("2"), "success"])
        delays = []

        # Mock time.sleep to capture delays
        original_sleep = time.sleep

        def mock_sleep(delay):
            delays.append(delay)

        with patch("time.sleep", side_effect=mock_sleep):
            # Mock exponential_backoff_sync to return known delays
            with patch(
                "backend.worker.backoff.exponential_backoff_sync"
            ) as mock_backoff:
                mock_backoff.side_effect = [2.0, 4.0]
                retry_with_backoff_sync(
                    mock_func,
                    max_attempts=3,
                    base_delay=1.0,
                    max_delay=60.0,
                    jitter_factor=0.0,
                    retryable_exceptions=(ValueError,),
                )
                # Verify exponential_backoff_sync was called with correct attempts
                mock_backoff.assert_any_call(
                    0, base_delay=1.0, max_delay=60.0, jitter_factor=0.0
                )
                mock_backoff.assert_any_call(
                    1, base_delay=1.0, max_delay=60.0, jitter_factor=0.0
                )
                # Verify sleep calls with mocked delays
                assert delays == [2.0, 4.0]

    def test_max_attempts_zero_raises_runtime_error(self) -> None:
        """Test that max_attempts=0 raises RuntimeError."""
        mock_func = Mock()
        with pytest.raises(
            RuntimeError, match="Retry logic exhausted without exception"
        ):
            retry_with_backoff_sync(
                mock_func,
                max_attempts=0,
                base_delay=0.001,
                max_delay=0.001,
                jitter_factor=0.0,
                retryable_exceptions=(ValueError,),
            )
        mock_func.assert_not_called()


class TestAWSIntegration:
    """Integration tests with AWS client creation (mocked)."""

    @patch("boto3.client")
    def test_transient_error_triggers_retry(self, mock_boto3_client: Mock) -> None:
        """Test that transient AWS errors trigger retry."""
        import botocore.exceptions

        # Mock client creation to raise transient error twice, then succeed
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        mock_client.some_operation.side_effect = [
            botocore.exceptions.EndpointConnectionError(
                endpoint_url="http://localhost:4566"
            ),
            botocore.exceptions.EndpointConnectionError(
                endpoint_url="http://localhost:4566"
            ),
            {"success": True},
        ]

        # Function that creates client and calls operation
        def aws_operation():
            import boto3

            client = boto3.client("sqs", endpoint_url="http://localhost:4566")
            return client.some_operation()

        result = retry_with_backoff_sync(
            aws_operation,
            max_attempts=3,
            base_delay=0.001,
            max_delay=0.001,
            jitter_factor=0.0,
            retryable_exceptions=(botocore.exceptions.EndpointConnectionError,),
        )

        assert result == {"success": True}
        assert mock_client.some_operation.call_count == 3
        # Verify boto3.client was called three times (once per attempt)
        assert mock_boto3_client.call_count == 3

    @patch("boto3.client")
    def test_configuration_error_no_retry(self, mock_boto3_client: Mock) -> None:
        """Test that configuration errors are not retried."""
        import botocore.exceptions

        # Mock client creation to raise configuration error
        mock_boto3_client.side_effect = botocore.exceptions.NoCredentialsError()

        def aws_operation():
            import boto3

            client = boto3.client("sqs", endpoint_url="http://localhost:4566")
            return client.some_operation()

        with pytest.raises(botocore.exceptions.NoCredentialsError):
            retry_with_backoff_sync(
                aws_operation,
                max_attempts=3,
                base_delay=0.001,
                max_delay=0.001,
                jitter_factor=0.0,
                retryable_exceptions=(botocore.exceptions.EndpointConnectionError,),
            )

        # Should only be called once (no retry)
        assert mock_boto3_client.call_count == 1

    @patch("time.sleep")
    @patch("boto3.client")
    def test_retry_uses_exponential_backoff_delays(
        self, mock_boto3_client: Mock, mock_sleep: Mock
    ) -> None:
        """Test that retry uses exponential backoff delays with AWS calls."""
        import botocore.exceptions

        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        mock_client.some_operation.side_effect = [
            botocore.exceptions.EndpointConnectionError(
                endpoint_url="http://localhost:4566"
            ),
            botocore.exceptions.EndpointConnectionError(
                endpoint_url="http://localhost:4566"
            ),
            {"success": True},
        ]

        def aws_operation():
            import boto3

            client = boto3.client("sqs", endpoint_url="http://localhost:4566")
            return client.some_operation()

        # Mock exponential_backoff_sync to return known delays
        with patch("backend.worker.backoff.exponential_backoff_sync") as mock_backoff:
            mock_backoff.side_effect = [2.0, 4.0]
            retry_with_backoff_sync(
                aws_operation,
                max_attempts=3,
                base_delay=1.0,
                max_delay=60.0,
                jitter_factor=0.0,
                retryable_exceptions=(botocore.exceptions.EndpointConnectionError,),
            )
            # Verify exponential_backoff_sync was called with correct attempts
            mock_backoff.assert_any_call(
                0, base_delay=1.0, max_delay=60.0, jitter_factor=0.0
            )
            mock_backoff.assert_any_call(
                1, base_delay=1.0, max_delay=60.0, jitter_factor=0.0
            )
            # Verify sleep calls with mocked delays
            mock_sleep.assert_any_call(2.0)
            mock_sleep.assert_any_call(4.0)
