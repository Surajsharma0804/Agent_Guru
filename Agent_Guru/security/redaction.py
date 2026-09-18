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

    A field is considered sensitive when its key (lowercased) *contains* one
    of the ``_REDACT_KEYS`` substrings — so ``api_key``, ``user_api_key``,
    ``session_token``, and ``credentials`` are all caught, not just an exact
    key of ``"api_key"``/``"token"``/``"credential"``. Nested dicts and
    lists/tuples of dicts are redacted recursively, so a secret nested under
    a non-sensitive key (e.g. ``{"auth": {"password": "..."}}`` or
    ``{"items": [{"api_key": "..."}]}``) is caught too, not just top-level
    fields.

    BUG FIX (Round 24): both of the above were gaps in the previous
    implementation — it only matched a key *exactly equal* to one of
    ``_REDACT_KEYS`` (so ``api_key`` was redacted but ``user_api_key`` or
    ``credentials`` were not, since neither equals a set member verbatim),
    and it only ever looked at top-level values (a secret one level deeper
    passed straight through unredacted). This module's own module docstring
    cites CWE-200 (sensitive data exposure) as exactly the risk this
    function exists to prevent, so a shallow, exact-match-only
    implementation was providing meaningfully less protection than its own
    purpose calls for. This mirrors the identical substring-match +
    recursive fix already applied to AuditLogger._sanitize_details() in
    Round 23.

    Args:
        data: Dictionary that may contain sensitive key-value pairs, at any
            nesting depth.

    Returns:
        New dictionary with sensitive values replaced by ``"***REDACTED***"``.

    Example:
        >>> redact({"api_key": "secret123", "name": "test"})
        {'api_key': '***REDACTED***', 'name': 'test'}
        >>> redact({"auth": {"user_api_key": "secret123"}})
        {'auth': {'user_api_key': '***REDACTED***'}}

    """
    return {
        k: _REDACTED_VALUE
        if any(sensitive in k.lower() for sensitive in _REDACT_KEYS)
        else _redact_value(v)
        for k, v in data.items()
    }


def _redact_value(value: Any) -> Any:
    """Recurse into dicts and lists/tuples so nested secrets are caught too."""
    if isinstance(value, dict):
        return redact(value)
    if isinstance(value, (list, tuple)):
        return [_redact_value(v) for v in value]
    return value
