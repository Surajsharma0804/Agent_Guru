"""
Security features for the LLM Runtime.

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
from typing import Any, List, Pattern

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credential patterns to redact
# ---------------------------------------------------------------------------

_CREDENTIAL_PATTERNS: List[Pattern[str]] = [
    # Patterns with no capture group → entire match replaced with [REDACTED]
    re.compile(r"sk-[A-Za-z0-9]{20,}", re.IGNORECASE),          # OpenAI keys
    re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}", re.IGNORECASE),    # Anthropic keys
    re.compile(r"AIza[A-Za-z0-9\-_]{35}", re.IGNORECASE),       # Google API keys
    re.compile(r"ghp_[A-Za-z0-9]{36}", re.IGNORECASE),          # GitHub tokens
    # Patterns with a prefix capture group → prefix kept, value replaced
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),  # Bearer tokens
    re.compile(r"(token[\"'\s:=]+)[A-Za-z0-9\-._~+/]{10,}", re.IGNORECASE),
    re.compile(r"(api[_\-]?key[\"'\s:=]+)[A-Za-z0-9\-._~+/]{10,}", re.IGNORECASE),
    re.compile(r"(password[\"'\s:=]+)\S+", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# PII patterns to redact
# ---------------------------------------------------------------------------

_PII_PATTERNS: List[tuple[Pattern[str], str]] = [
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),  # US SSN
    (re.compile(r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"), "[CARD]"),  # Credit card
]


# ---------------------------------------------------------------------------
# Credential sanitization
# ---------------------------------------------------------------------------


def sanitize_credentials(text: str) -> str:
    """
    Redact API keys and authentication tokens from a string.

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
    """
    Redact personally identifiable information from a string.

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
    """
    Logging filter that redacts credentials and PII from log records.

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
                    sanitize_credentials(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )

        return True


# ---------------------------------------------------------------------------
# TLS validation helper
# ---------------------------------------------------------------------------


def create_secure_http_client() -> Any:
    """
    Create an httpx AsyncClient with TLS certificate validation enforced.

    Rejects self-signed and invalid certificates.

    Returns:
        httpx.AsyncClient configured for secure connections.
    """
    import httpx  # type: ignore[import]

    return httpx.AsyncClient(
        verify=True,  # Enforce TLS certificate validation
        timeout=httpx.Timeout(30.0),
    )
