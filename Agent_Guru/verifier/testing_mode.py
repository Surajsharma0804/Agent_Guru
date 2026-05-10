"""Testing mode support for the Verifier System.

Enables injection of hallucinations and malformed outputs for
validation testing, with detection rate tracking.

Requirements: 15.1, 15.2, 15.3, 15.4, 15.5
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class InjectionRecord:
    injection_type: str  # "hallucination" | "malformed_output"
    content: str
    detected: bool = False


class TestingModeManager:
    """Manages testing mode: injection, detection tracking, diagnostics.

    In testing mode:
    - Hallucinations can be injected into text for detection validation
    - Malformed outputs can be injected for validation testing
    - Detection rates are tracked per injection type
    - Detailed diagnostics are emitted

    In production mode:
    - No injections accepted
    - No detection rate tracking overhead
    """

    def __init__(self) -> None:
        self._enabled = False
        self._injections: list[InjectionRecord] = []

    def enable(self) -> None:
        self._enabled = True
        logger.info("Verifier testing mode ENABLED")

    def disable(self) -> None:
        self._enabled = False
        logger.info("Verifier testing mode DISABLED")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def inject_hallucination(self, text: str) -> str:
        """Inject hallucination markers into text for testing detection.

        Appends uncertainty language that the detector should catch.
        Only works in testing mode.
        """
        if not self._enabled:
            msg = "Testing mode is not enabled"
            raise RuntimeError(msg)
        injected = (
            text + " I think maybe possibly according to a study I'm not sure about, "
            "the answer could be something I believe I assume."
        )
        self._injections.append(InjectionRecord(injection_type="hallucination", content=injected))
        logger.debug("Injected hallucination into text (len=%d)", len(injected))
        return injected

    def inject_malformed_output(self, expected_format: str = "json") -> str:
        """Inject malformed output for validation testing."""
        if not self._enabled:
            msg = "Testing mode is not enabled"
            raise RuntimeError(msg)
        malformed_map = {
            "json": "{invalid json: missing quotes}",
            "xml": "<root><unclosed>",
            "markdown": "",
        }
        content = malformed_map.get(expected_format, "{bad}")
        self._injections.append(InjectionRecord(injection_type="malformed_output", content=content))
        logger.debug("Injected malformed %s output", expected_format)
        return content

    def record_detection(self, injection_type: str, detected: bool) -> None:
        """Record whether an injection was detected."""
        # Find the most recent unrecorded injection of this type
        for record in reversed(self._injections):
            if record.injection_type == injection_type and not record.detected:
                record.detected = detected
                break

    def get_detection_rate(self, injection_type: str) -> float:
        """Get detection rate for a given injection type."""
        relevant = [r for r in self._injections if r.injection_type == injection_type]
        if not relevant:
            return 0.0
        detected = sum(1 for r in relevant if r.detected)
        return detected / len(relevant)

    def get_diagnostics(self) -> dict[str, object]:
        """Get detailed diagnostics for all injections."""
        return {
            "total_injections": len(self._injections),
            "hallucination_detection_rate": self.get_detection_rate("hallucination"),
            "malformed_output_detection_rate": self.get_detection_rate("malformed_output"),
            "injections": [
                {
                    "type": r.injection_type,
                    "detected": r.detected,
                    "content_length": len(r.content),
                }
                for r in self._injections
            ],
        }

    def reset(self) -> None:
        self._injections.clear()
