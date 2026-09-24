"""Retry strategy with exponential backoff and jitter.

This module implements a production-grade retry strategy for handling transient
failures in platform operations. It uses exponential backoff with jitter to
prevent thundering herd problems.

Performance Characteristics:
    - Time Complexity: O(1) per retry decision
    - Space Complexity: O(1) (no state accumulation)
    - Delay Calculation: <1ms
    - Jitter: ±20% randomization

Design Decisions:
    - Exponential backoff: delay = base_delay * (2 ** attempt)
    - Jitter: Randomize ±20% to prevent synchronized retries
    - Configurable limits: max_attempts, base_delay, max_delay
    - Type-safe with dataclasses and type hints

Usage Example:
    >>> from Agent_Guru.platform.error_handling import RetryStrategy, RetryConfig
    >>>
    >>> # Configure retry strategy
    >>> config = RetryConfig(
    ...     max_attempts=3,
    ...     base_delay=1.0,
    ...     max_delay=60.0
    ... )
    >>> strategy = RetryStrategy(config)
    >>>
    >>> # Execute operation with retries
    >>> result = strategy.execute(risky_operation, arg1, arg2)
    >>> if result.success:
    ...     print(f"Success after {result.attempts} attempts")
    ... else:
    ...     print(f"Failed: {result.error}")

Author: Agent Guru Team
Date: 2026-02-26
Version: 1.0.0
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

class RetryDecision(Enum):
    """Retry decision outcomes."""

    RETRY = "retry"
    ABORT = "abort"
    SUCCESS = "success"

@dataclass
class RetryConfig:
    """Configuration for retry strategy.

    Attributes:
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        jitter_factor: Jitter randomization factor (default: 0.2 for ±20%)

    """

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter_factor: float = 0.2

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.max_attempts < 1:
            msg = f"max_attempts must be >= 1, got {self.max_attempts}"
            raise ValueError(msg)
        if self.base_delay <= 0:
            msg = f"base_delay must be > 0, got {self.base_delay}"
            raise ValueError(msg)
        if self.max_delay < self.base_delay:
            msg = f"max_delay ({self.max_delay}) must be >= base_delay ({self.base_delay})"
            raise ValueError(
                msg,
            )
        if not 0 <= self.jitter_factor <= 1:
            msg = f"jitter_factor must be in [0, 1], got {self.jitter_factor}"
            raise ValueError(msg)

@dataclass
class RetryResult:
    """Result of retry operation.

    Attributes:
        success: Whether operation succeeded
        value: Return value if successful
        error: Error message if failed
        attempts: Number of attempts made
        total_delay: Total delay time in seconds

    """

    success: bool
    value: Any | None = None
    error: str | None = None
    attempts: int = 0
    total_delay: float = 0.0

class RetryStrategy:
    """Retry strategy with exponential backoff and jitter.

    This class implements a robust retry mechanism for handling transient failures.
    It uses exponential backoff with jitter to prevent thundering herd problems
    when multiple clients retry simultaneously.

    Time Complexity: O(1) per retry decision
    Space Complexity: O(1) (stateless)

    Example:
        >>> strategy = RetryStrategy(RetryConfig(max_attempts=3))
        >>> result = strategy.execute(lambda: risky_operation())
        >>> print(f"Success: {result.success}, Attempts: {result.attempts}")

    """

    def __init__(self, config: RetryConfig) -> None:
        """Initialize retry strategy.

        Args:
            config: Retry configuration

        Raises:
            ValueError: If config parameters are invalid

        """
        self.config = config

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt with exponential backoff and jitter.

        Time Complexity: O(1)
        Space Complexity: O(1)

        The delay is calculated as:
        1. Base exponential backoff: base_delay * (2 ** attempt)
        2. Cap at max_delay
        3. Add jitter: randomize ±jitter_factor

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds with jitter applied

        Example:
            >>> strategy = RetryStrategy(RetryConfig(base_delay=1.0))
            >>> delay = strategy.calculate_delay(0)  # First retry
            >>> print(f"Delay: {delay:.2f}s")  # ~1.0s ± 20%

        """
        # Exponential backoff: base_delay * (2 ** attempt)
        exponential_delay = self.config.base_delay * (2**attempt)

        # Cap at max_delay
        capped_delay = min(exponential_delay, self.config.max_delay)

        # Apply jitter: randomize ±jitter_factor
        jitter_range = capped_delay * self.config.jitter_factor
        jitter = random.uniform(-jitter_range, jitter_range)  # nosec B311
        final_delay = capped_delay + jitter

        # Ensure non-negative delay
        return max(0.0, final_delay)

    def should_retry(self, attempt: int, error: Exception) -> RetryDecision:
        """Determine if operation should be retried.

        Time Complexity: O(1)
        Space Complexity: O(1)

        Args:
            attempt: Current attempt number (0-indexed)
            error: Exception that occurred

        Returns:
            RetryDecision indicating whether to retry or abort

        Example:
            >>> strategy = RetryStrategy(RetryConfig(max_attempts=3))
            >>> decision = strategy.should_retry(0, ConnectionError())
            >>> print(decision)  # RetryDecision.RETRY

        """
        # Check if max attempts reached
        if attempt >= self.config.max_attempts:
            logger.warning("Max retry attempts (%d) reached", self.config.max_attempts)
            return RetryDecision.ABORT

        # Check for non-retryable errors
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            logger.info("Non-retryable error encountered, aborting")
            return RetryDecision.ABORT

        # Retry for transient errors
        logger.info(
            "Retryable error on attempt %d/%d: %s: %s",
            attempt + 1,
            self.config.max_attempts,
            type(error).__name__,
            error,
        )
        return RetryDecision.RETRY

    def execute(self, operation: Callable[..., T], *args: Any, **kwargs: Any) -> RetryResult:
        """Execute operation with retry logic.

        Time Complexity: O(max_attempts) worst case
        Space Complexity: O(1)

        Args:
            operation: Callable to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation

        Returns:
            RetryResult with operation outcome

        Example:
            >>> def flaky_operation():
            ...     if secrets.SystemRandom().random() < 0.5:
            ...         raise ConnectionError("Transient failure")
            ...     return "success"
            >>>
            >>> strategy = RetryStrategy(RetryConfig())
            >>> result = strategy.execute(flaky_operation)
            >>> if result.success:
            ...     print(f"Result: {result.value}")

        """
        attempt = 0
        total_delay = 0.0
        last_error: Exception | None = None

        for attempt in range(self.config.max_attempts):
            try:
                # Execute operation
                logger.debug("Executing operation (attempt %s)", attempt + 1)
                value = operation(*args, **kwargs)

                # Success
                logger.info(
                    "Operation succeeded on attempt %d (total delay: %.2fs)",
                    attempt + 1,
                    total_delay,
                )
                return RetryResult(
                    success=True,
                    value=value,
                    attempts=attempt + 1,
                    total_delay=total_delay,
                )

            except (KeyboardInterrupt, SystemExit):
                # Interpreter-level control flow, not an operation failure.
                # This used to be swallowed into a RetryResult, so a Ctrl-C or
                # a sys.exit() raised inside the operation was converted into
                # an ordinary failed result and the process kept running.
                logger.info("Non-retryable interrupt encountered, aborting")
                raise

            except Exception as e:  # noqa: BLE001 - classified by should_retry()
                # BUG FIX: this handler did not exist. The two orphaned
                # comments that used to sit here - "# Check if should retry"
                # and "# Calculate delay and wait (only if not the last
                # attempt)" - were all that remained of it.
                #
                # Consequences, all confirmed by running the code:
                #   * any real exception propagated out of execute() on the
                #     FIRST attempt, so RetryStrategy never retried anything.
                #     The class, its config (max_attempts, base_delay,
                #     max_delay, jitter_factor) and both helper methods were
                #     inert;
                #   * should_retry() and calculate_delay() were dead code;
                #   * `last_error` was never assigned, so the "All retries
                #     exhausted" branch below could only ever have produced
                #     the literal string "Unknown error" - if it had been
                #     reachable at all.
                last_error = e
                attempts_made = attempt + 1

                if self.should_retry(attempts_made, e) is RetryDecision.ABORT:
                    break

                delay = self.calculate_delay(attempt)
                logger.debug("Retrying in %.2fs", delay)
                time.sleep(delay)
                total_delay += delay

        # All retries exhausted
        error_msg = f"{type(last_error).__name__}: {last_error}" if last_error else "Unknown error"
        logger.error(
            "Operation failed after %d attempts (total delay: %.2fs): %s",
            self.config.max_attempts,
            total_delay,
            error_msg,
        )
        return RetryResult(
            success=False,
            error=error_msg,
            attempts=attempt + 1,
            total_delay=total_delay,
        )

    async def execute_async(
        self,
        operation: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> RetryResult:
        """Execute async operation with retry logic.

        Time Complexity: O(max_attempts) worst case
        Space Complexity: O(1)

        Args:
            operation: Async callable to execute
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation

        Returns:
            RetryResult with operation outcome

        Example:
            >>> import asyncio
            >>>
            >>> async def async_operation():
            ...     await asyncio.sleep(0.1)
            ...     return "success"
            >>>
            >>> strategy = RetryStrategy(RetryConfig())
            >>> result = asyncio.run(strategy.execute_async(async_operation))

        """

        attempt = 0
        total_delay = 0.0
        last_error: Exception | None = None

        for attempt in range(self.config.max_attempts):
            try:
                # Execute async operation
                logger.debug("Executing async operation (attempt %s)", attempt + 1)
                value = await operation(*args, **kwargs)

                # Success
                logger.info(
                    "Async operation succeeded on attempt %d (total delay: %.2fs)",
                    attempt + 1,
                    total_delay,
                )
                return RetryResult(
                    success=True,
                    value=value,
                    attempts=attempt + 1,
                    total_delay=total_delay,
                )

            except (KeyboardInterrupt, SystemExit):
                # See execute(): interpreter control flow must propagate.
                logger.info("Non-retryable interrupt encountered, aborting")
                raise

            except Exception as e:  # noqa: BLE001 - classified by should_retry()
                # Same missing handler as in execute(); see the explanation
                # there. asyncio.CancelledError derives from BaseException on
                # Python 3.8+, so it is NOT caught here and cancellation still
                # propagates to the caller instead of being retried.
                last_error = e
                attempts_made = attempt + 1

                if self.should_retry(attempts_made, e) is RetryDecision.ABORT:
                    break

                delay = self.calculate_delay(attempt)
                logger.debug("Retrying in %.2fs", delay)
                await asyncio.sleep(delay)
                total_delay += delay

        # All retries exhausted
        error_msg = f"{type(last_error).__name__}: {last_error}" if last_error else "Unknown error"
        logger.error(
            "Async operation failed after %d attempts (total delay: %.2fs): %s",
            self.config.max_attempts,
            total_delay,
            error_msg,
        )
        return RetryResult(
            success=False,
            error=error_msg,
            attempts=attempt + 1,
            total_delay=total_delay,
        )
