"""Energy monitoring and reporting for IoT devices.

Requirements: 16.6
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class EnergyReading:
    """A single energy reading from a smart plug."""

    device_id: str
    watts: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class EnergyReport:
    """Aggregated energy report."""

    period: str  # "daily" or "weekly"
    total_kwh: float
    by_device: dict[str, float]
    peak_device: str | None
    alert_triggered: bool = False
    alert_message: str | None = None


class EnergyMonitor:
    """Monitors smart plug energy consumption and generates reports."""

    def __init__(self, alert_threshold_kwh: float = 10.0) -> None:
        self._readings: list[EnergyReading] = []
        self._alert_threshold_kwh = alert_threshold_kwh

    def record(self, device_id: str, watts: float) -> None:
        self._readings.append(EnergyReading(device_id=device_id, watts=watts))

    def get_energy_report(self, period: str = "daily") -> EnergyReport:
        """Aggregate energy data for the given period."""
        now = time.time()
        cutoff = now - 86400 if period == "daily" else now - 604800

        relevant = [r for r in self._readings if r.timestamp >= cutoff]
        by_device: dict[str, float] = {}
        for reading in relevant:
            # Convert watts to kWh (assuming 1-second intervals)
            kwh = reading.watts / 3_600_000
            by_device[reading.device_id] = by_device.get(reading.device_id, 0.0) + kwh

        total_kwh = sum(by_device.values())
        peak_device = max(by_device, key=lambda k: by_device[k]) if by_device else None

        alert = total_kwh > self._alert_threshold_kwh
        return EnergyReport(
            period=period,
            total_kwh=round(total_kwh, 4),
            by_device={k: round(v, 4) for k, v in by_device.items()},
            peak_device=peak_device,
            alert_triggered=alert,
            alert_message=f"Energy usage {total_kwh:.2f} kWh exceeds threshold" if alert else None,
        )
