"""Security features for the LLM Runtime.

Provides:
- Credential sanitization (API key redaction in logs)
- PII redaction (email, phone, address patterns)
- TLS certificate validation enforcement

Author: Agent Guru Team
Date: 2026-03-18
Version: 1.0.0
"""

from __future__ import annotations

import logging
import re
from re import Pattern
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credential patterns to redact
# ---------------------------------------------------------------------------

_CREDENTIAL_PATTERNS: list[Pattern[str]] = [
    # Patterns with no capture group → entire match replaced with [REDACTED]
    re.compile(r"sk-[A-Za-z0-9]{20,}", re.IGNORECASE),  # OpenAI keys
    re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}", re.IGNORECASE),  # Anthropic keys
    re.compile(r"AIza[A-Za-z0-9\-_]{35}", re.IGNORECASE),  # Google API keys
    re.compile(r"ghp_[A-Za-z0-9]{36}", re.IGNORECASE),  # GitHub tokens
    # Patterns with a prefix capture group → prefix kept, value replaced
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),  # Bearer tokens
    re.compile(r"(token[\"'\s:=]+)[A-Za-z0-9\-._~+/]{10,}", re.IGNORECASE),
    re.compile(r"(api[_\-]?key[\"'\s:=]+)[A-Za-z0-9\-._~+/]{10,}", re.IGNORECASE),
    re.compile(r"(password[\"'\s:=]+)\S+", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# PII patterns to redact
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[Pattern[str], str]] = [
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),  # US SSN
    (re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"), "[CARD]"),  # Credit card
    # IPv4 addresses (e.g., 192.168.1.1)
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP]"),
    # IPv6 addresses (abbreviated and full forms)
    (re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b"), "[IP]"),
]


# ---------------------------------------------------------------------------
# Credential sanitization
# ---------------------------------------------------------------------------


def sanitize_credentials(text: str) -> str:
    """Redact API keys and authentication tokens from a string.

    Args:
        text: Input string that may contain credentials.

    Returns:
        String with credentials replaced by [REDACTED].

    """
    result = text
    for pattern in _CREDENTIAL_PATTERNS:
        result = pattern.sub(lambda m: _redact_match(m), result)
    return result


def _redact_match(match: re.Match) -> str:  # type: ignore[type-arg]
    """Replace a credential match with [REDACTED], preserving prefix if captured."""
    groups = match.groups()
    if groups:
        # Keep the prefix (e.g., "Bearer ") and redact the value
        return groups[0] + "[REDACTED]"
    # No capture group — replace the entire match
    return "[REDACTED]"


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------


def redact_pii(text: str) -> str:
    """Redact personally identifiable information from a string.

    Replaces emails, phone numbers, SSNs, and credit card numbers
    with placeholder tokens.

    Args:
        text: Input string that may contain PII.

    Returns:
        String with PII replaced by placeholder tokens.

    """
    result = text
    for pattern, placeholder in _PII_PATTERNS:
        result = pattern.sub(placeholder, result)
    return result


# ---------------------------------------------------------------------------
# Logging filter
# ---------------------------------------------------------------------------


class CredentialFilter(logging.Filter):
    """Logging filter that redacts credentials and PII from log records.

    Install on any logger or handler to prevent sensitive data leakage:

        handler.addFilter(CredentialFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_credentials(record.msg)
            record.msg = redact_pii(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: sanitize_credentials(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    sanitize_credentials(str(a)) if isinstance(a, str) else a for a in record.args
                )

        return True


# ---------------------------------------------------------------------------
# TLS validation helper
# ---------------------------------------------------------------------------


def create_secure_http_client() -> Any:
    """Create an httpx AsyncClient with TLS certificate validation enforced.

    Rejects self-signed and invalid certificates.

    Returns:
        httpx.AsyncClient configured for secure connections.

    """
    import httpx  # type: ignore[import]

    return httpx.AsyncClient(
        verify=True,  # Enforce TLS certificate validation
        timeout=httpx.Timeout(30.0),
    )


# ---------------------------------------------------------------------------
# Prompt injection detection
# ---------------------------------------------------------------------------

# Patterns that indicate a prompt injection attempt
_INJECTION_PATTERNS: list[Pattern[str]] = [
    # System prompt override attempts
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?above\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?previous", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?previous", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    # Role-play override attempts
    re.compile(r"pretend\s+you\s+are\s+(a|an)?\s*(?!helpful)", re.IGNORECASE),
    re.compile(r"act\s+as\s+(a|an)?\s*(different|new|unrestricted)", re.IGNORECASE),
    # Jailbreak markers
    re.compile(r"\bDAN\b.*mode", re.IGNORECASE),
    re.compile(r"developer\s+mode", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
]


def detect_prompt_injection(text: str) -> bool:
    """Check if text contains prompt injection patterns.

    Args:
        text: User input to check.

    Returns:
        True if a prompt injection pattern is detected.

    """
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning("Prompt injection detected: pattern=%s", pattern.pattern)
            return True
    return False


def sanitize_user_input(text: str) -> str:
    """Sanitize user input by removing potential injection markers.

    Does NOT block the input — just strips obvious injection prefixes
    so the LLM sees clean input. Use detect_prompt_injection() for
    hard blocking decisions.

    Args:
        text: Raw user input.

    Returns:
        Sanitized input string.

    """
    # Remove markdown-style system prompt attempts
    sanitized = re.sub(
        r"```(?:system|instructions?)\s*\n.*?```",
        "[content removed]",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return sanitized.strip()
