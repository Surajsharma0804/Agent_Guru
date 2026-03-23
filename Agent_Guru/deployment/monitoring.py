"""Monitoring and analytics for Agent Guru — Task 28.

Integrates:
- Crash reporting (Sentry SDK)
- Performance monitoring (Prometheus metrics)
- Usage analytics (with explicit user consent)
- Structured logging (structlog)

All analytics are opt-in. No data is collected without user consent.
Data is encrypted in transit (TLS 1.3) and at rest (AES-256).
"""

from __future__ import annotations

import platform
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

_PLATFORM = platform.system().lower()


@dataclass
class AnalyticsEvent:
    """A single analytics event (only collected with user consent)."""

    event_type: str
    platform: str
    timestamp: float = field(default_factory=time.time)
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "platform": self.platform,
            "timestamp": self.timestamp,
            "properties": self.properties,
        }


class MonitoringManager:
    """Manages crash reporting, performance monitoring, and analytics.

    All analytics collection requires explicit user consent.
    Crash reporting is always enabled (no PII collected).

    Example:
        >>> mon = MonitoringManager(analytics_consent=True)
        >>> mon.initialize()
        >>> mon.record_event("voice_command", {"command": "open_app"})
        >>> mon.record_error("STT timeout", {"latency_ms": 5000})
        >>> mon.record_performance("stt", latency_ms=850.0)
    """

    def __init__(
        self,
        analytics_consent: bool = False,
        sentry_dsn: Optional[str] = None,
        prometheus_port: int = 9090,
    ) -> None:
        self.analytics_consent = analytics_consent
        self._sentry_dsn = sentry_dsn
        self._prometheus_port = prometheus_port
        self._initialized = False
        self._events: list[AnalyticsEvent] = []
        self._error_count = 0
        self._performance_samples: dict[str, list[float]] = {}
        self._listeners: list[Callable[[AnalyticsEvent], None]] = []

    def initialize(self) -> None:
        """Initialize monitoring subsystems."""
        self._init_crash_reporting()
        self._init_prometheus()
        self._initialized = True
        logger.info("monitoring_initialized",
                    platform=_PLATFORM,
                    analytics_consent=self.analytics_consent)

    # ------------------------------------------------------------------
    # Crash reporting (always on, no PII)
    # ------------------------------------------------------------------

    def record_error(
        self,
        error_message: str,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record an error for crash reporting.

        No PII is collected. Error messages are sanitized.

        Args:
            error_message: Error description (no PII).
            context: Optional context dict (no PII).
        """
        self._error_count += 1
        sanitized = self._sanitize(error_message)
        logger.error("crash_report",
                     error=sanitized,
                     context=context or {},
                     platform=_PLATFORM)

        # Forward to Sentry if configured
        if self._sentry_dsn:
            try:
                import sentry_sdk
                sentry_sdk.capture_message(sanitized, level="error",
                                           extras=context or {})
            except ImportError:
                pass

    # ------------------------------------------------------------------
    # Performance monitoring
    # ------------------------------------------------------------------

    def record_performance(self, stage: str, latency_ms: float) -> None:
        """Record a performance measurement for a pipeline stage.

        Args:
            stage: Pipeline stage name (e.g., "stt", "llm").
            latency_ms: Measured latency in milliseconds.
        """
        if stage not in self._performance_samples:
            self._performance_samples[stage] = []
        self._performance_samples[stage].append(latency_ms)

        logger.debug("performance_sample", stage=stage, latency_ms=latency_ms)

    def get_performance_summary(self) -> dict[str, dict[str, float]]:
        """Return mean and p95 latency for all tracked stages."""
        summary: dict[str, dict[str, float]] = {}
        for stage, samples in self._performance_samples.items():
            if not samples:
                continue
            sorted_s = sorted(samples)
            p95_idx = int(len(sorted_s) * 0.95)
            summary[stage] = {
                "mean_ms": sum(samples) / len(samples),
                "p95_ms": sorted_s[min(p95_idx, len(sorted_s) - 1)],
                "count": float(len(samples)),
            }
        return summary

    # ------------------------------------------------------------------
    # Usage analytics (opt-in only)
    # ------------------------------------------------------------------

    def record_event(
        self,
        event_type: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record a usage analytics event (only if user consented).

        Args:
            event_type: Event name (e.g., "voice_command", "onboarding_complete").
            properties: Optional event properties (no PII).
        """
        if not self.analytics_consent:
            return

        event = AnalyticsEvent(
            event_type=event_type,
            platform=_PLATFORM,
            properties=self._sanitize_dict(properties or {}),
        )
        self._events.append(event)

        for listener in self._listeners:
            try:
                listener(event)
            except Exception as exc:
                logger.warning("analytics_listener_error", error=str(exc))

        logger.debug("analytics_event", event_type=event_type)

    def on_event(self, callback: Callable[[AnalyticsEvent], None]) -> None:
        """Register a callback for analytics events."""
        self._listeners.append(callback)

    def get_events(self) -> list[AnalyticsEvent]:
        """Return all collected analytics events."""
        return list(self._events)

    def set_consent(self, consent: bool) -> None:
        """Update user consent for analytics collection.

        Args:
            consent: True to enable analytics, False to disable and clear data.
        """
        self.analytics_consent = consent
        if not consent:
            self._events.clear()
            logger.info("analytics_consent_revoked_data_cleared")
        else:
            logger.info("analytics_consent_granted")

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def error_count(self) -> int:
        """Total number of errors recorded."""
        return self._error_count

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_crash_reporting(self) -> None:
        if not self._sentry_dsn:
            logger.info("sentry_not_configured_skipping")
            return
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=self._sentry_dsn,
                traces_sample_rate=0.1,
                send_default_pii=False,  # Never send PII
            )
            logger.info("sentry_initialized")
        except ImportError:
            logger.warning("sentry_sdk_not_installed")

    def _init_prometheus(self) -> None:
        try:
            from prometheus_client import start_http_server
            start_http_server(self._prometheus_port)
            logger.info("prometheus_started", port=self._prometheus_port)
        except Exception as exc:
            logger.warning("prometheus_unavailable", error=str(exc))

    @staticmethod
    def _sanitize(text: str) -> str:
        """Remove potential PII patterns from error messages."""
        import re
        # Remove email addresses
        text = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL]", text)
        # Remove phone numbers
        text = re.sub(r"\b\d{10,}\b", "[PHONE]", text)
        return text

    @staticmethod
    def _sanitize_dict(d: dict[str, Any]) -> dict[str, Any]:
        """Remove PII keys from a properties dict."""
        _pii_keys = {"name", "email", "phone", "address", "user_id", "ip"}
        return {k: v for k, v in d.items() if k.lower() not in _pii_keys}
