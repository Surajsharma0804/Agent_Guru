"""Regression tests for RetryStrategy.

RetryStrategy had no dedicated test module. The only coverage was a single
integration test in test_error_response.py, and it asserted on the RetryResult
without asserting that any retry had actually happened - which is why the
class silently shipped with no `except Exception` handler in either execute()
or execute_async(), retrying nothing and letting the first failure propagate.

These tests pin the behaviour that was missing: that a transient failure is
retried, that backoff actually delays, that the operation is called exactly
the configured number of times, and that interpreter-level control flow
(KeyboardInterrupt / SystemExit) and asyncio cancellation are never converted
into ordinary results.
"""

import asyncio
import time

import pytest

from Agent_Guru.platform.error_handling.retry_strategy import (
    RetryConfig,
    RetryDecision,
    RetryResult,
    RetryStrategy,
)


def _fast_config(**overrides) -> RetryConfig:
    """A config whose delays are small enough to run in a unit test."""
    params = {
        "max_attempts": 3,
        "base_delay": 0.01,
        "max_delay": 0.05,
        "jitter_factor": 0.0,
    }
    params.update(overrides)
    return RetryConfig(**params)


class TestRetryConfig:
    """Configuration validation."""

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("max_attempts", 0),
            ("base_delay", 0.0),
            ("jitter_factor", 1.5),
        ],
    )
    def test_rejects_invalid_values(self, field, value):
        params = {"max_attempts": 3, "base_delay": 1.0, "max_delay": 60.0}
        params[field] = value
        with pytest.raises(ValueError, match=field):
            RetryConfig(**params)

    def test_rejects_max_delay_below_base_delay(self):
        with pytest.raises(ValueError, match="max_delay"):
            RetryConfig(base_delay=10.0, max_delay=1.0)


class TestCalculateDelay:
    """Exponential backoff with jitter."""

    def test_exponential_growth_without_jitter(self):
        strategy = RetryStrategy(RetryConfig(base_delay=1.0, max_delay=100.0, jitter_factor=0.0))
        assert strategy.calculate_delay(0) == pytest.approx(1.0)  # nosec B101
        assert strategy.calculate_delay(1) == pytest.approx(2.0)  # nosec B101
        assert strategy.calculate_delay(2) == pytest.approx(4.0)  # nosec B101

    def test_capped_at_max_delay(self):
        strategy = RetryStrategy(RetryConfig(base_delay=1.0, max_delay=3.0, jitter_factor=0.0))
        assert strategy.calculate_delay(10) == pytest.approx(3.0)  # nosec B101

    def test_jitter_stays_within_band_and_non_negative(self):
        strategy = RetryStrategy(RetryConfig(base_delay=1.0, max_delay=100.0, jitter_factor=0.5))
        for _ in range(200):
            delay = strategy.calculate_delay(0)
            assert 0.0 <= delay <= 1.5  # nosec B101


class TestShouldRetry:
    """Retry classification."""

    def test_retries_below_max_attempts(self):
        strategy = RetryStrategy(_fast_config(max_attempts=3))
        assert strategy.should_retry(1, ConnectionError()) is RetryDecision.RETRY  # nosec B101

    def test_aborts_at_max_attempts(self):
        strategy = RetryStrategy(_fast_config(max_attempts=3))
        assert strategy.should_retry(3, ConnectionError()) is RetryDecision.ABORT  # nosec B101

    def test_aborts_on_interpreter_control_flow(self):
        strategy = RetryStrategy(_fast_config())
        assert strategy.should_retry(0, KeyboardInterrupt()) is RetryDecision.ABORT  # nosec B101
        assert strategy.should_retry(0, SystemExit()) is RetryDecision.ABORT  # nosec B101


class TestExecute:
    """Synchronous execution."""

    def test_success_on_first_attempt_does_not_sleep(self):
        strategy = RetryStrategy(_fast_config())
        calls = []

        def operation():
            calls.append(1)
            return "ok"

        result = strategy.execute(operation)

        assert isinstance(result, RetryResult)  # nosec B101
        assert result.success is True  # nosec B101
        assert result.value == "ok"  # nosec B101
        assert result.attempts == 1  # nosec B101
        assert result.total_delay == 0.0  # nosec B101
        assert len(calls) == 1  # nosec B101

    def test_transient_failure_is_retried_then_succeeds(self):
        """The behaviour the missing handler removed entirely."""
        strategy = RetryStrategy(_fast_config(max_attempts=3))
        calls = []

        def operation():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = strategy.execute(operation)

        assert result.success is True  # nosec B101
        assert result.value == "recovered"  # nosec B101
        assert result.attempts == 3  # nosec B101
        assert len(calls) == 3  # nosec B101
        assert result.total_delay > 0.0  # nosec B101

    def test_persistent_failure_exhausts_attempts_and_reports_the_error(self):
        strategy = RetryStrategy(_fast_config(max_attempts=3))
        calls = []

        def operation():
            calls.append(1)
            raise TimeoutError("Operation timed out")

        result = strategy.execute(operation)

        assert result.success is False  # nosec B101
        assert result.attempts == 3  # nosec B101
        assert len(calls) == 3, "operation must run exactly max_attempts times"  # nosec B101
        # "Unknown error" here would mean last_error was never captured.
        assert result.error == "TimeoutError: Operation timed out"  # nosec B101

    def test_no_delay_after_the_final_attempt(self):
        """Backoff must not be paid for a retry that will never happen."""
        strategy = RetryStrategy(
            RetryConfig(max_attempts=2, base_delay=0.2, max_delay=0.2, jitter_factor=0.0),
        )

        def operation():
            raise ConnectionError("always")

        started = time.perf_counter()
        result = strategy.execute(operation)
        elapsed = time.perf_counter() - started

        # One delay between attempt 1 and 2, and none after attempt 2.
        assert result.total_delay == pytest.approx(0.2, abs=0.01)  # nosec B101
        assert elapsed < 0.4, "a trailing sleep was paid after the last attempt"  # nosec B101

    def test_arguments_are_forwarded(self):
        strategy = RetryStrategy(_fast_config())

        def operation(a, b, *, c):
            return (a, b, c)

        result = strategy.execute(operation, 1, 2, c=3)
        assert result.value == (1, 2, 3)  # nosec B101

    @pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
    def test_interpreter_control_flow_propagates(self, interrupt):
        """Ctrl-C and sys.exit() must not become an ordinary RetryResult."""
        strategy = RetryStrategy(_fast_config())
        calls = []

        def operation():
            calls.append(1)
            raise interrupt

        with pytest.raises(interrupt):
            strategy.execute(operation)

        assert len(calls) == 1, "an interrupt must not be retried"  # nosec B101


class TestExecuteAsync:
    """Asynchronous execution."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        strategy = RetryStrategy(_fast_config())

        async def operation():
            return "ok"

        result = await strategy.execute_async(operation)
        assert result.success is True  # nosec B101
        assert result.value == "ok"  # nosec B101
        assert result.attempts == 1  # nosec B101

    @pytest.mark.asyncio
    async def test_transient_failure_is_retried_then_succeeds(self):
        strategy = RetryStrategy(_fast_config(max_attempts=3))
        calls = []

        async def operation():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = await strategy.execute_async(operation)

        assert result.success is True  # nosec B101
        assert result.attempts == 3  # nosec B101
        assert len(calls) == 3  # nosec B101

    @pytest.mark.asyncio
    async def test_persistent_failure_reports_the_last_error(self):
        strategy = RetryStrategy(_fast_config(max_attempts=2))

        async def operation():
            raise OSError("disk gone")

        result = await strategy.execute_async(operation)

        assert result.success is False  # nosec B101
        assert result.attempts == 2  # nosec B101
        assert result.error == "OSError: disk gone"  # nosec B101

    @pytest.mark.asyncio
    async def test_cancellation_propagates_and_is_not_retried(self):
        """CancelledError derives from BaseException and must pass through."""
        strategy = RetryStrategy(_fast_config(max_attempts=3))
        calls = []

        async def operation():
            calls.append(1)
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await strategy.execute_async(operation)

        assert len(calls) == 1, "cancellation must not be retried"  # nosec B101

    @pytest.mark.asyncio
    async def test_backoff_yields_to_the_event_loop(self):
        """The async path must not block the loop with time.sleep()."""
        strategy = RetryStrategy(
            RetryConfig(max_attempts=2, base_delay=0.05, max_delay=0.05, jitter_factor=0.0),
        )
        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.005)
                ticks += 1

        async def operation():
            raise ConnectionError("always")

        ticker_task = asyncio.create_task(ticker())
        try:
            await strategy.execute_async(operation)
        finally:
            ticker_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await ticker_task

        assert ticks > 0, "the event loop was blocked during backoff"  # nosec B101
