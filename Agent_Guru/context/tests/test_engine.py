"""Tests for ContextEngine.

This module had no tests, which is how `start_polling()` came to ship as a
loop whose entire body was `await asyncio.sleep(interval)` - it polled
nothing, so the snapshot was never refreshed and "real-time ambient context"
was a coroutine that slept forever.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from Agent_Guru.context.engine import (
    LOW_CONFIDENCE_THRESHOLD,
    ContextEngine,
    ContextSnapshot,
    SensorSignals,
)


class TestSnapshot:
    def test_starts_with_a_default_snapshot(self):
        engine = ContextEngine()
        snapshot = engine.get_snapshot()

        assert isinstance(snapshot, ContextSnapshot)  # nosec B101
        assert snapshot.output_mode == "voice"  # nosec B101

    def test_get_snapshot_is_fast(self):
        """The class docstring promises a <=10 ms snapshot."""
        engine = ContextEngine()
        engine.update(SensorSignals(hour=9, motion_level=0.5))

        started = time.perf_counter()
        for _ in range(1000):
            engine.get_snapshot()
        per_call_ms = (time.perf_counter() - started) / 1000 * 1000

        assert per_call_ms < 10.0, f"{per_call_ms:.3f} ms per snapshot"  # nosec B101

    def test_public_location_switches_output_to_text(self):
        engine = ContextEngine()
        snapshot = engine.update(SensorSignals(location_type="public"))
        assert snapshot.output_mode == "text"  # nosec B101

    def test_non_public_location_keeps_voice_output(self):
        engine = ContextEngine()
        for location in ("home", "work", "transit"):
            assert engine.update(SensorSignals(location_type=location)).output_mode == "voice", location  # nosec B101

    def test_low_confidence_retains_the_previous_activity(self):
        """Documented behaviour: below the threshold, do not thrash."""
        engine = ContextEngine()

        # Seed a confident activity first.
        engine._classifier.classify = lambda _signals: ("working", 0.95)
        first = engine.update(SensorSignals())
        assert first.activity == "working"  # nosec B101

        # Now a low-confidence reading must not replace it.
        engine._classifier.classify = lambda _signals: ("sleeping", LOW_CONFIDENCE_THRESHOLD - 0.1)
        second = engine.update(SensorSignals())

        assert second.activity == "working"  # nosec B101
        assert second.activity_confidence == pytest.approx(0.95)  # nosec B101


class TestPolling:
    @pytest.mark.asyncio
    async def test_polling_actually_refreshes_the_snapshot(self):
        """The regression the missing tests allowed."""
        readings = [
            SensorSignals(hour=9, motion_level=0.9, location_type="work"),
            SensorSignals(hour=22, motion_level=0.0, location_type="home"),
        ]
        calls = 0

        def provider() -> SensorSignals:
            nonlocal calls
            reading = readings[min(calls, len(readings) - 1)]
            calls += 1
            return reading

        engine = ContextEngine(sensor_provider=provider)
        # Poll fast so the test does not wait 30s.
        import Agent_Guru.context.engine as engine_module

        original = engine_module.POLL_INTERVAL_S
        engine_module.POLL_INTERVAL_S = 0.01
        try:
            task = asyncio.create_task(engine.start_polling())
            await asyncio.sleep(0.05)
            engine.stop_polling()
            await asyncio.wait_for(task, timeout=1.0)
        finally:
            engine_module.POLL_INTERVAL_S = original

        assert calls >= 2, f"the sensor was polled {calls} times"  # nosec B101
        assert engine.get_snapshot().location_type == "home"  # nosec B101

    @pytest.mark.asyncio
    async def test_stop_polling_returns_immediately(self):
        """stop_polling() used to leave the task sleeping a whole interval."""

        def provider() -> SensorSignals:
            return SensorSignals()

        engine = ContextEngine(ambient_mode=True, sensor_provider=provider)

        task = asyncio.create_task(engine.start_polling())
        await asyncio.sleep(0.01)

        started = time.perf_counter()
        engine.stop_polling()
        await asyncio.wait_for(task, timeout=2.0)
        elapsed = time.perf_counter() - started

        # The ambient interval is 60s; anything near that means it slept it out.
        assert elapsed < 0.5, f"stop_polling took {elapsed:.2f}s to take effect"  # nosec B101

    @pytest.mark.asyncio
    async def test_a_failing_sensor_does_not_end_polling(self):
        calls = 0

        def flaky() -> SensorSignals:
            nonlocal calls
            calls += 1
            if calls == 1:
                msg = "sensor unavailable"
                raise RuntimeError(msg)
            return SensorSignals(location_type="public")

        engine = ContextEngine(sensor_provider=flaky)
        import Agent_Guru.context.engine as engine_module

        original = engine_module.POLL_INTERVAL_S
        engine_module.POLL_INTERVAL_S = 0.01
        try:
            task = asyncio.create_task(engine.start_polling())
            await asyncio.sleep(0.05)
            engine.stop_polling()
            await asyncio.wait_for(task, timeout=1.0)
        finally:
            engine_module.POLL_INTERVAL_S = original

        assert calls >= 2, "polling stopped after the first sensor failure"  # nosec B101
        assert engine.get_snapshot().output_mode == "text"  # nosec B101

    @pytest.mark.asyncio
    async def test_polling_without_a_provider_is_refused(self):
        """Spinning forever over a provider that does not exist is not a default."""
        engine = ContextEngine()

        with pytest.raises(ValueError, match="sensor_provider"):
            await engine.start_polling()
