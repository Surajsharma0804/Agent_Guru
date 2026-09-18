"""Shared data models for the security system."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuthenticationResult:
    """Result of a biometric authentication attempt.

    Attributes:
        authenticated: Whether the authentication succeeded.
        confidence: Similarity/confidence score in [0.0, 1.0].
        modality: Biometric modality used (e.g. "face", "voice", "multi").
        user_id: The claimed or identified user ID.
        failure_reason: Human-readable reason when authenticated is False.

    """

    authenticated: bool
    confidence: float
    modality: str
    user_id: str
    failure_reason: str | None = None
    # Added (Round 24): BiometricAuthenticator.authenticate_multi_factor() used to
    # detect a liveness (anti-spoofing) rejection by substring-matching "liveness"
    # inside failure_reason -- fragile, since it silently stops triggering the
    # documented "immediate rejection on liveness failure" path (Req 6.5) the
    # moment that wording changes anywhere it's set, with no test or type error to
    # catch the drift. This field lets authenticate_face()/authenticate_voice() set
    # a real, structured, unambiguous flag instead of a string caller code has to
    # pattern-match. Defaults to False so every existing construction of this
    # dataclass (this file has no other fields with defaults before it) remains
    # valid unchanged.
    liveness_failed: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            msg = f"AuthenticationResult.confidence must be in [0.0, 1.0], got {self.confidence}"
            raise ValueError(
                msg,
            )
