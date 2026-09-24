"""Tests for GracefulShutdownManager.

This module had no tests, which is how it came to ship with the body of its
generic cleanup-exception handler merged into the TimeoutError handler. The
effect was that ANY non-timeout exception from a cleanup handler propagated
out of shutdown() and abandoned the rest of the LIFO chain - so one failing
handler stopped every earlier-registered handler from ever running, at exactly
the moment cleanup matters. That, and the shutdown-latency behaviour, are
pinned here.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from Agent_Guru.platform.integration.graceful_shutdown import (
    GracefulShutdownManager,
    ShutdownPhase,
)


class TestConfiguration:
    @pytest.mark.parametrize("bad", [0, -1.0])
    def test_rejects_non_positive_timeout(self, bad):
        with pytest.raises(ValueError, match="timeout"):
            GracefulShutdownManager(timeout=bad)

    @pytest.mark.parametrize("bad", [0, -1.0])
    def test_rejects_non_positive_handler_timeout(self, bad):
        with pytest.raises(ValueError, match="default_handler_timeout"):
            GracefulShutdownManager(default_handler_timeout=bad)

    def test_rejects_non_callable_handler(self):
        manager = GracefulShutdownManager()
        with pytest.raises(ValueError, match="callable"):
            manager.register_cleanup("not a callable")  # type: ignore[arg-type]


class TestCleanupChain:
    """Cleanup is best-effort: one bad handler must not stop the others."""

    @pytest.mark.asyncio
    async def test_handlers_run_in_lifo_order(self):
        manager = GracefulShutdownManager()
        order: list[str] = []

        for name in ("first", "second", "third"):

            async def handler(tag=name):
                order.append(tag)

            manager.register_cleanup(handler, name=name)

        await manager.shutdown("test")

        assert order == ["third", "second", "first"]  # nosec B101

    @pytest.mark.asyncio
    async def test_a_raising_handler_does_not_abort_the_chain(self):
        """The regression the missing handler allowed.

        `boom` is registered AFTER `saves_state`, so it runs first under LIFO.
        Before the fix its RuntimeError propagated out of shutdown() and
        `saves_state` never ran.
        """
        manager = GracefulShutdownManager()
        saved = False

        async def saves_state():
            nonlocal saved
            saved = True

        async def boom():
            msg = "handler exploded"
            raise RuntimeError(msg)

        manager.register_cleanup(saves_state, name="saves_state")
        manager.register_cleanup(boom, name="boom")

        await manager.shutdown("test")  # must not raise

        assert saved, "a failing cleanup handler aborted the rest of the chain"  # nosec B101
        assert manager.phase is ShutdownPhase.COMPLETE  # nosec B101

    @pytest.mark.asyncio
    async def test_a_raising_handler_is_recorded_once(self):
        manager = GracefulShutdownManager()

        async def boom():
            msg = "handler exploded"
            raise RuntimeError(msg)

        manager.register_cleanup(boom, name="boom")

        state = await manager.shutdown("test")

        errors = state.cleanup_errors
        assert len(errors) == 1, f"expected one recorded error, got {errors}"  # nosec B101
        assert "RuntimeError" in errors[0]  # nosec B101
        assert "handler exploded" in errors[0]  # nosec B101

    @pytest.mark.asyncio
    async def test_a_timed_out_handler_is_recorded_once_as_a_timeout(self):
        """A timeout used to be appended twice: once correctly, once as
        "raised TimeoutError" by the merged generic-handler body."""
        manager = GracefulShutdownManager(default_handler_timeout=0.05)

        async def hangs():
            await asyncio.sleep(5)

        manager.register_cleanup(hangs, name="hangs")

        state = await manager.shutdown("test")

        errors = state.cleanup_errors
        assert len(errors) == 1, f"a timeout was recorded {len(errors)} times"  # nosec B101
        assert "timed out" in errors[0]  # nosec B101

    @pytest.mark.asyncio
    async def test_shutdown_returns_its_state(self):
        """cleanup_errors used to be unreachable without a state_file."""
        manager = GracefulShutdownManager()

        async def ok():
            return None

        manager.register_cleanup(ok, name="ok")

        state = await manager.shutdown("because")

        assert state is not None  # nosec B101
        assert state.reason == "because"  # nosec B101
        assert state.cleanup_handlers_run == 1  # nosec B101
        assert state.cleanup_errors == []  # nosec B101
        assert state.duration_seconds >= 0.0  # nosec B101
        assert manager.last_shutdown_state is state  # nosec B101


class TestInFlightDrain:
    @pytest.mark.asyncio
    async def test_shutdown_returns_promptly_once_operations_drain(self):
        """Phase 1 must WAIT for the drain, not poll for it.

        The old loop slept 0.1s per iteration, so shutdown could linger up to
        100 ms after the last operation finished. Waiting on an event makes
        that delay effectively zero.
        """
        manager = GracefulShutdownManager(timeout=5.0)

        async def operation():
            async with manager.track_operation():
                await asyncio.sleep(0.05)

        op = asyncio.create_task(operation())
        await asyncio.sleep(0.01)  # let it register
        assert manager.in_flight_count == 1  # nosec B101

        started = time.perf_counter()
        await manager.shutdown("test")
        elapsed = time.perf_counter() - started
        await op

        assert manager.in_flight_count == 0  # nosec B101
        # The operation has ~40ms left; anything near 100ms means polling.
        assert elapsed < 0.09, f"shutdown lingered {elapsed * 1000:.0f}ms after the drain"  # nosec B101

    @pytest.mark.asyncio
    async def test_shutdown_gives_up_after_its_timeout(self):
        manager = GracefulShutdownManager(timeout=0.1)

        async def never_finishes():
            async with manager.track_operation():
                await asyncio.sleep(10)

        op = asyncio.create_task(never_finishes())
        await asyncio.sleep(0.01)

        started = time.perf_counter()
        await manager.shutdown("test")
        elapsed = time.perf_counter() - started

        op.cancel()
        with pytest.raises(asyncio.CancelledError):
            await op

        assert 0.09 <= elapsed < 1.0, f"timeout not honoured ({elapsed:.3f}s)"  # nosec B101
        assert manager.phase is ShutdownPhase.COMPLETE  # nosec B101

    @pytest.mark.asyncio
    async def test_no_wait_when_nothing_is_in_flight(self):
        manager = GracefulShutdownManager(timeout=5.0)

        started = time.perf_counter()
        await manager.shutdown("test")
        elapsed = time.perf_counter() - started

        assert elapsed < 0.05, f"waited {elapsed:.3f}s with nothing in flight"  # nosec B101


class TestPhases:
    @pytest.mark.asyncio
    async def test_starts_running_and_ends_complete(self):
        manager = GracefulShutdownManager()
        assert manager.phase is ShutdownPhase.RUNNING  # nosec B101
        assert manager.is_shutting_down is False  # nosec B101

        await manager.shutdown("test")

        assert manager.phase is ShutdownPhase.COMPLETE  # nosec B101

    @pytest.mark.asyncio
    async def test_second_shutdown_is_ignored(self):
        manager = GracefulShutdownManager()
        runs = 0

        async def handler():
            nonlocal runs
            runs += 1

        manager.register_cleanup(handler, name="handler")

        await manager.shutdown("first")
        await manager.shutdown("second")

        assert runs == 1, "cleanup ran twice"  # nosec B101

    @pytest.mark.asyncio
    async def test_wait_for_shutdown_unblocks(self):
        manager = GracefulShutdownManager()
        waiter = asyncio.create_task(manager.wait_for_shutdown())
        await asyncio.sleep(0)

        await manager.shutdown("test")
        await asyncio.wait_for(waiter, timeout=1.0)
