"""Real-Time Ambient Context Engine."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from Agent_Guru.context.activity import ActivityClassifier
from Agent_Guru.utils.path_utils import safe_path

logger = logging.getLogger(__name__)

SNAPSHOT_LATENCY_MS = 10
POLL_INTERVAL_S = 30
AMBIENT_POLL_INTERVAL_S = 60
LOW_CONFIDENCE_THRESHOLD = 0.60

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


@dataclass
class SensorSignals:
    """Raw sensor signals for context inference."""

    hour: int = 12
    motion_level: float = 0.0
    location_type: str = "home"  # home/work/public/transit
    calendar_event: str | None = None
    battery_level: float = 1.0
    ambient_noise_db: float = 40.0


@dataclass
class ContextSnapshot:
    """Current ambient context snapshot."""

    activity: str = "idle"
    activity_confidence: float = 0.5
    location_type: str = "home"
    output_mode: str = "voice"  # voice/text
    timestamp: float = field(default_factory=time.time)
    signals: SensorSignals = field(default_factory=SensorSignals)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "activity": self.activity,
            "activity_confidence": self.activity_confidence,
            "location_type": self.location_type,
            "output_mode": self.output_mode,
            "timestamp": self.timestamp,
        }


class ContextEngine:
    """Provides real-time ambient context with ≤10ms snapshot response."""

    def __init__(
        self,
        ambient_mode: bool = False,
        sensor_provider: Callable[[], SensorSignals] | None = None,
    ) -> None:
        """Initialize the context engine.

        Args:
            ambient_mode: Use the slower ambient poll interval.
            sensor_provider: Callable returning the current SensorSignals.
                start_polling() calls it once per interval and feeds the
                result to update(). Without it there is nothing to poll and
                start_polling() says so instead of spinning - see there.

        """
        self._classifier = ActivityClassifier()
        self._snapshot: ContextSnapshot = ContextSnapshot()
        self._ambient_mode = ambient_mode
        self._sensor_provider = sensor_provider
        self._running = False
        self._prev_activity: str | None = None
        self._stop_event: asyncio.Event | None = None

    def get_snapshot(self) -> ContextSnapshot:
        """Return current context snapshot in ≤10ms."""
        return self._snapshot

    def update(self, signals: SensorSignals) -> ContextSnapshot:
        """Update context from new sensor signals."""
        activity, confidence = self._classifier.classify(
            {
                "hour": signals.hour,
                "motion_level": signals.motion_level,
                "calendar_event": signals.calendar_event,
            },
        )

        # Retain previous activity when confidence < 60%
        if confidence < LOW_CONFIDENCE_THRESHOLD and self._prev_activity:
            activity = self._prev_activity
            confidence = self._snapshot.activity_confidence

        # Auto-switch to text output in public locations
        output_mode = "text" if signals.location_type == "public" else "voice"

        self._prev_activity = activity
        self._snapshot = ContextSnapshot(
            activity=activity,
            activity_confidence=confidence,
            location_type=signals.location_type,
            output_mode=output_mode,
            signals=signals,
        )
        return self._snapshot

    async def start_polling(self) -> None:
        """Poll the sensor provider until stop_polling() is called.

        BUG FIX: the body of this loop used to be nothing but
        ``await asyncio.sleep(interval)``. It polled NOTHING - the snapshot
        was never refreshed, so "real-time ambient context" was a coroutine
        that slept forever and get_snapshot() kept returning whatever the last
        external update() call had left behind, or the all-defaults snapshot
        if there had never been one.

        Two further problems came with it: stop_polling() only flipped a flag,
        so the task kept sleeping for up to AMBIENT_POLL_INTERVAL_S (60 s)
        before noticing - a minute added to shutdown - and a failing sensor
        read would have taken the whole loop down.

        Raises:
            ValueError: If no sensor_provider was supplied. Spinning forever
                over a provider that does not exist is not a useful default;
                the caller is told at once.

        """
        if self._sensor_provider is None:
            msg = (
                "start_polling() needs a sensor_provider; construct "
                "ContextEngine(sensor_provider=...) or push signals with "
                "update() instead."
            )
            raise ValueError(msg)

        self._running = True
        self._stop_event = asyncio.Event()
        interval = AMBIENT_POLL_INTERVAL_S if self._ambient_mode else POLL_INTERVAL_S

        while self._running:
            try:
                signals = self._sensor_provider()
                self.update(signals)
            except Exception:
                # One bad sensor read must not end ambient context for the
                # rest of the session.
                logger.exception("Context sensor poll failed; keeping last snapshot")

            # Wait on the stop event rather than sleeping blindly, so
            # stop_polling() takes effect immediately instead of up to one
            # full interval later.
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
            except TimeoutError:
                continue
            else:
                break

    def stop_polling(self) -> None:
        """Ask start_polling() to stop; it returns on its next scheduling."""
        self._running = False
        if self._stop_event is not None:
            self._stop_event.set()

    def persist(self, path: str = "~/.agent_guru/context.enc") -> None:
        """Persist encrypted context snapshot."""
        _base = Path("~/.agent_guru").expanduser().resolve()
        _resolved = Path(path).expanduser().resolve()
        p = safe_path(_base, _resolved.relative_to(_base))
        p.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(self._snapshot.to_dict()).encode()
        if _CRYPTO_AVAILABLE:
            key = os.urandom(32)
            nonce = os.urandom(12)
            aesgcm = AESGCM(key)
            ct = aesgcm.encrypt(nonce, data, None)
            import base64

            payload = json.dumps(
                {
                    "key": base64.b64encode(key).decode(),
                    "nonce": base64.b64encode(nonce).decode(),
                    "ct": base64.b64encode(ct).decode(),
                },
            )
            p.write_text(payload)
        else:
            p.write_bytes(data)

    def restore(self, path: str = "~/.agent_guru/context.enc") -> bool:
        """Restore context from encrypted snapshot."""
        _base = Path("~/.agent_guru").expanduser().resolve()
        _resolved = Path(path).expanduser().resolve()
        p = safe_path(_base, _resolved.relative_to(_base))
        if not p.exists():
            return False
        try:
            raw = p.read_text()
            if _CRYPTO_AVAILABLE:
                import base64

                obj = json.loads(raw)
                key = base64.b64decode(obj["key"])
                nonce = base64.b64decode(obj["nonce"])
                ct = base64.b64decode(obj["ct"])
                aesgcm = AESGCM(key)
                data = aesgcm.decrypt(nonce, ct, None)
            else:
                data = raw.encode()
            d = json.loads(data)
            self._snapshot.activity = d.get("activity", "idle")
            self._snapshot.activity_confidence = d.get("activity_confidence", 0.5)
            return True
        except Exception:
            logger.exception("Failed to restore context")
            return False
