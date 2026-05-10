"""Sensitive data redaction utilities.

Provides a `redact` helper that masks sensitive fields in dictionaries
before they are written to logs or returned in error responses.

CWE-200: Sensitive Data Redaction
"""

from typing import Any

_REDACT_KEYS: frozenset[str] = frozenset(
    {"password", "api_key", "token", "secret", "credential", "key"},
)

_REDACTED_VALUE = "***REDACTED***"


def redact(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *data* with sensitive fields replaced by a placeholder.

    A field is considered sensitive when its key (lowercased) is a member of
    ``_REDACT_KEYS``.  All other fields are preserved unchanged.

    Args:
        data: Dictionary that may contain sensitive key-value pairs.

    Returns:
        New dictionary with sensitive values replaced by ``"***REDACTED***"``.

    Example:
        >>> redact({"api_key": "secret123", "name": "test"})
        {'api_key': '***REDACTED***', 'name': 'test'}

    """
    return {k: _REDACTED_VALUE if k.lower() in _REDACT_KEYS else v for k, v in data.items()}
