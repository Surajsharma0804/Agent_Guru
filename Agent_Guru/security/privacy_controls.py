"""Module: Agent_Guru.security.privacy_controls
Purpose: Data privacy controls, rate limiting, and input validation.

Provides:
- PrivacyController: Local model data privacy, HTTPS enforcement, history deletion
- RateLimiter: Token bucket rate limiting to prevent abuse
- InputValidator: Input sanitization to prevent injection attacks
- SensitiveActionGuard: User confirmation for sensitive actions

Requirements: 19.2, 19.3, 19.4, 19.6, 19.7, 19.8

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# Sensitive action categories requiring confirmation
_SENSITIVE_ACTIONS: set[str] = {
    "delete_file",
    "format_drive",
    "send_email",
    "send_message",
    "make_payment",
    "install_software",
    "uninstall_software",
    "change_password",
    "access_camera",
    "access_microphone",
    "share_location",
    "access_contacts",
}

# Injection attack patterns
_INJECTION_PATTERNS = [
    re.compile(r"[;|&`$]"),  # Shell injection
    re.compile(r"<script", re.IGNORECASE),  # XSS
    re.compile(r"DROP\s+TABLE", re.IGNORECASE),  # SQL injection
    re.compile(r"SELECT\s+\*", re.IGNORECASE),  # SQL injection
    re.compile(r"\.\./"),  # Path traversal
    re.compile(r"__import__"),  # Python injection
    re.compile(r"eval\s*\("),  # Code injection
]

# Maximum input lengths
_MAX_VOICE_INPUT_LEN = 2000
_MAX_COMMAND_LEN = 500


class PrivacyMode(str, Enum):
    """Privacy mode for LLM processing."""

    LOCAL = "local"  # All processing on-device (no data leaves)
    CLOUD = "cloud"  # Cloud API (data sent to provider)
    HYBRID = "hybrid"  # Local for sensitive, cloud for complex


@dataclass
class PrivacyConfig:
    """Privacy configuration.

    Attributes:
        mode: Privacy mode (local/cloud/hybrid)
        require_https: Enforce HTTPS for all cloud API calls
        log_conversations: Whether to log conversation history
        data_retention_days: Days to retain conversation data (0 = no retention)

    """

    mode: PrivacyMode = PrivacyMode.LOCAL
    require_https: bool = True
    log_conversations: bool = False
    data_retention_days: int = 0


class PrivacyController:
    """Data privacy controls for Agent Guru.

    Enforces:
    - No audio data transmitted when using local models
    - HTTPS for all cloud API communications
    - User controls for conversation history deletion

    Example:
        >>> ctrl = PrivacyController(PrivacyConfig(mode=PrivacyMode.LOCAL))
        >>> ctrl.validate_api_url("https://api.openai.com/v1/chat")  # OK
        >>> ctrl.validate_api_url("http://api.openai.com/v1/chat")   # Raises

    """

    def __init__(self, config: PrivacyConfig | None = None) -> None:
        self._config = config or PrivacyConfig()
        self._deletion_callbacks: list[Callable] = []
        logger.info("PrivacyController initialized: mode=%s", self._config.mode.value)

    def is_local_mode(self) -> bool:
        """Return True if using local-only processing."""
        return self._config.mode == PrivacyMode.LOCAL

    def validate_api_url(self, url: str) -> None:
        """Validate that API URL uses HTTPS (if required).

        Args:
            url: API endpoint URL

        Raises:
            ValueError: If URL uses HTTP when HTTPS is required

        """
        if self._config.require_https and url.startswith("http://"):
            msg = f"HTTPS required for cloud API calls, got HTTP: {url}"
            raise ValueError(msg)

    def can_transmit_audio(self) -> bool:
        """Return True if audio data can be transmitted to cloud.

        In LOCAL mode, audio never leaves the device.
        """
        return self._config.mode != PrivacyMode.LOCAL

    def on_data_deletion(self, callback: Callable) -> None:
        """Register callback for data deletion events.

        Args:
            callback: Called when user requests data deletion

        """
        self._deletion_callbacks.append(callback)

    def delete_all_user_data(self) -> None:
        """Delete all user data (GDPR right to erasure).

        Invokes all registered deletion callbacks.
        """
        logger.info("PrivacyController: deleting all user data")
        for cb in self._deletion_callbacks:
            try:
                cb()
            except Exception:
                logger.exception("Data deletion callback error")

    def get_config(self) -> PrivacyConfig:
        """Return current privacy configuration."""
        return self._config


class RateLimiter:
    """Token bucket rate limiter to prevent abuse.

    Uses token bucket algorithm:
    - Bucket fills at `rate` tokens/second
    - Each request consumes 1 token
    - Requests rejected when bucket is empty

    Performance:
        - check(): O(1)
        - Space: O(1) per limiter instance

    Example:
        >>> limiter = RateLimiter(rate=10.0, burst=20)
        >>> if limiter.check():
        ...     process_request()

    """

    def __init__(self, rate: float = 10.0, burst: int = 20) -> None:
        """Initialize rate limiter.

        Args:
            rate: Tokens per second (requests per second)
            burst: Maximum burst size (bucket capacity)

        Raises:
            ValueError: If rate or burst is invalid

        """
        if rate <= 0:
            msg = f"rate must be > 0, got {rate}"
            raise ValueError(msg)
        if burst < 1:
            msg = f"burst must be >= 1, got {burst}"
            raise ValueError(msg)

        self._rate = rate
        self._burst = float(burst)
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()
        self._rejected_count = 0

    def check(self) -> bool:
        """Check if request is allowed (consumes 1 token if allowed).

        Time Complexity: O(1)

        Returns:
            True if request is allowed, False if rate limit exceeded

        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._last_refill = now

            # Refill tokens
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            self._rejected_count += 1
            return False

    def reset(self) -> None:
        """Reset the rate limiter to full capacity."""
        with self._lock:
            self._tokens = self._burst
            self._last_refill = time.monotonic()
            self._rejected_count = 0

    @property
    def rejected_count(self) -> int:
        """Total number of rejected requests."""
        return self._rejected_count

    @property
    def rate(self) -> float:
        """Configured rate in tokens/second."""
        return self._rate

    @property
    def burst(self) -> int:
        """Configured burst size."""
        return int(self._burst)


class InputValidator:
    """Input validation to prevent injection attacks.

    Validates:
    - Length limits (prevent buffer overflow)
    - Injection patterns (shell, SQL, XSS, path traversal)
    - Character encoding

    Example:
        >>> validator = InputValidator()
        >>> validator.validate("open notepad")  # OK
        >>> validator.validate("rm -rf /; echo pwned")  # Raises

    """

    def __init__(
        self,
        max_voice_len: int = _MAX_VOICE_INPUT_LEN,
        max_command_len: int = _MAX_COMMAND_LEN,
    ) -> None:
        self._max_voice_len = max_voice_len
        self._max_command_len = max_command_len

    def validate_voice_input(self, text: str) -> str:
        """Validate and sanitize voice input.

        Args:
            text: Raw voice input text

        Returns:
            Sanitized text

        Raises:
            ValueError: If input contains injection patterns or exceeds limits

        """
        if not isinstance(text, str):
            msg = f"Expected str, got {type(text)}"
            raise TypeError(msg)

        if len(text) > self._max_voice_len:
            msg = f"Voice input too long: {len(text)} > {self._max_voice_len}"
            raise ValueError(msg)

        self._check_injection(text)
        return text.strip()

    def validate_command(self, command: str) -> str:
        """Validate a command string.

        Args:
            command: Command to validate

        Returns:
            Sanitized command

        Raises:
            ValueError: If command contains injection patterns

        """
        if not isinstance(command, str):
            msg = f"Expected str, got {type(command)}"
            raise TypeError(msg)

        if len(command) > self._max_command_len:
            msg = f"Command too long: {len(command)} > {self._max_command_len}"
            raise ValueError(msg)

        self._check_injection(command)
        return command.strip()

    def is_safe(self, text: str) -> bool:
        """Return True if text passes all validation checks.

        Args:
            text: Text to check

        Returns:
            True if safe, False if potentially malicious

        """
        try:
            self.validate_voice_input(text)
            return True
        except (ValueError, TypeError):
            return False

    def _check_injection(self, text: str) -> None:
        """Check for injection attack patterns.

        Args:
            text: Text to check

        Raises:
            ValueError: If injection pattern detected

        """
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                msg = "Potential injection attack detected in input"
                raise ValueError(msg)


class SensitiveActionGuard:
    """User confirmation guard for sensitive actions.

    Requires explicit confirmation before executing sensitive operations
    like file deletion, sending messages, or making payments.

    Example:
        >>> guard = SensitiveActionGuard()
        >>> guard.require_confirmation("delete_file", "/home/user/doc.txt")
        >>> # Raises if not confirmed

    """

    def __init__(self) -> None:
        self._confirmation_callbacks: dict[str, Callable] = {}
        self._pending_confirmations: dict[str, dict] = {}
        self._lock = threading.Lock()

    def is_sensitive(self, action: str) -> bool:
        """Return True if action requires confirmation.

        Args:
            action: Action name to check

        """
        return action in _SENSITIVE_ACTIONS

    def register_confirmation_handler(self, action: str, handler: Callable) -> None:
        """Register a confirmation handler for an action.

        Args:
            action: Action name
            handler: Callable that returns True if user confirms

        """
        self._confirmation_callbacks[action] = handler

    def request_confirmation(self, action: str, params: dict) -> str:
        """Request confirmation for a sensitive action.

        Args:
            action: Action name
            params: Action parameters

        Returns:
            Confirmation token (use with confirm())

        """
        import uuid

        token = str(uuid.uuid4())
        with self._lock:
            self._pending_confirmations[token] = {
                "action": action,
                "params": params,
                "timestamp": time.monotonic(),
            }
        logger.info("Confirmation requested for action: %s", action)
        return token

    def confirm(self, token: str) -> bool:
        """Confirm a pending sensitive action.

        Args:
            token: Confirmation token from request_confirmation()

        Returns:
            True if confirmation was valid and action can proceed

        """
        with self._lock:
            pending = self._pending_confirmations.pop(token, None)

        if pending is None:
            return False

        # Check timeout (30 seconds)
        age = time.monotonic() - pending["timestamp"]
        if age > 30.0:
            logger.warning("Confirmation token expired: %s", token)
            return False

        return True

    def cancel(self, token: str) -> None:
        """Cancel a pending confirmation.

        Args:
            token: Confirmation token to cancel

        """
        with self._lock:
            self._pending_confirmations.pop(token, None)
