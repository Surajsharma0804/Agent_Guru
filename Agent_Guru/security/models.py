"""Shared data models for the security system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


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
    failure_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"AuthenticationResult.confidence must be in [0.0, 1.0], got {self.confidence}"
            )
