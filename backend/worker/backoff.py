"""Exponential backoff implementation for retry logic.

Provides configurable exponential backoff with jitter to prevent
thundering herd problems during retries.
"""

import asyncio
import random
import time
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


async def exponential_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_factor: float = 0.1,
) -> float:
    """
    Calculate exponential backoff delay with optional jitter.

    The delay formula is: min(base_delay * 2^attempt, max_delay) + jitter

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter_factor: Factor for random jitter (0.0 to 1.0)

    Returns:
        Calculated delay in seconds

    Examples:
        >>> # Basic usage
        >>> delay = await exponential_backoff(0)  # ~1 second
        >>> delay = await exponential_backoff(1)  # ~2 seconds
        >>> delay = await exponential_backoff(2)  # ~4 seconds

        >>> # With custom parameters
        >>> delay = await exponential_backoff(0, base_delay=2.0, max_delay=30.0)
    """
    # Calculate base exponential delay
    delay = min(base_delay * (2**attempt), max_delay)

    # Add jitter to prevent thundering herd
    if jitter_factor > 0:
        jitter = random.uniform(0, delay * jitter_factor)
        delay += jitter

    return delay


def exponential_backoff_sync(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_factor: float = 0.1,
) -> float:
    """
    Calculate exponential backoff delay with optional jitter (synchronous version).

    The delay formula is: min(base_delay * 2^attempt, max_delay) + jitter

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter_factor: Factor for random jitter (0.0 to 1.0)

    Returns:
        Calculated delay in seconds
    """
    # Calculate base exponential delay
    delay = min(base_delay * (2**attempt), max_delay)

    # Add jitter to prevent thundering herd
    if jitter_factor > 0:
        jitter = random.uniform(0, delay * jitter_factor)
        delay += jitter

    return delay


async def retry_with_backoff(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_factor: float = 0.1,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Callable[[int, Exception], None] | None = None,
    **kwargs: Any,
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for the function
        max_attempts: Maximum number of attempts (including first)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter_factor: Factor for random jitter (0.0 to 1.0)
        retryable_exceptions: Tuple of exceptions that trigger retry
        on_retry: Optional callback function called on each retry
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the successful function call

    Raises:
        The last exception if all retries are exhausted

    Examples:
        >>> # Basic retry
        >>> result = await retry_with_backoff(async_function, arg1, arg2)

        >>> # With custom retry logic
        >>> result = await retry_with_backoff(
        ...     func=async_function,
        ...     arg1,
        ...     max_attempts=5,
        ...     base_delay=2.0,
        ...     retryable_exceptions=(ConnectionError, TimeoutError),
        ...     on_retry=lambda attempt, exc: log_retry(attempt, exc),
        ... )
    """
    last_exception: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e

            if attempt < max_attempts - 1:
                # Calculate delay for next attempt
                delay = await exponential_backoff(
                    attempt,
                    base_delay=base_delay,
                    max_delay=max_delay,
                    jitter_factor=jitter_factor,
                )

                if on_retry:
                    on_retry(attempt + 1, e)

                # Sleep before next attempt
                await asyncio.sleep(delay)

    # All attempts exhausted
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic exhausted without exception")


def retry_with_backoff_sync(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter_factor: float = 0.1,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Callable[[int, Exception], None] | None = None,
    **kwargs: Any,
) -> T:
    """
    Retry a synchronous function with exponential backoff.

    Args:
        func: Synchronous function to retry
        *args: Positional arguments for the function
        max_attempts: Maximum number of attempts (including first)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap in seconds
        jitter_factor: Factor for random jitter (0.0 to 1.0)
        retryable_exceptions: Tuple of exceptions that trigger retry
        on_retry: Optional callback function called on each retry
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the successful function call

    Raises:
        The last exception if all retries are exhausted
    """
    last_exception: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e

            if attempt < max_attempts - 1:
                # Calculate delay for next attempt
                delay = exponential_backoff_sync(
                    attempt,
                    base_delay=base_delay,
                    max_delay=max_delay,
                    jitter_factor=jitter_factor,
                )

                if on_retry:
                    on_retry(attempt + 1, e)

                # Sleep before next attempt
                time.sleep(delay)

    # All attempts exhausted
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic exhausted without exception")


class BackoffCalculator:
    """
    Configurable backoff calculator with state tracking.

    Useful when you need to maintain backoff state across multiple
    operations or want more control over the backoff strategy.
    """

    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter_factor: float = 0.1,
    ) -> None:
        """Initialize backoff calculator.

        Args:
            base_delay: Base delay in seconds
            max_delay: Maximum delay cap in seconds
            jitter_factor: Factor for random jitter (0.0 to 1.0)
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor
        self._attempt_counts: dict[str, int] = {}

    async def get_delay(self, key: str = "default") -> float:
        """Get the delay for the next retry attempt.

        Args:
            key: Identifier for tracking attempts (allows multiple independent trackers)

        Returns:
            Calculated delay in seconds
        """
        attempt = self._attempt_counts.get(key, 0)
        delay = await exponential_backoff(
            attempt,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            jitter_factor=self.jitter_factor,
        )
        self._attempt_counts[key] = attempt + 1
        return delay

    def reset(self, key: str = "default") -> None:
        """Reset attempt counter for a key.

        Args:
            key: Identifier to reset
        """
        self._attempt_counts.pop(key, None)

    def reset_all(self) -> None:
        """Reset all attempt counters."""
        self._attempt_counts.clear()

    def get_attempt(self, key: str = "default") -> int:
        """Get current attempt count for a key.

        Args:
            key: Identifier to check

        Returns:
            Current attempt number (0 if not started)
        """
        return self._attempt_counts.get(key, 0)
