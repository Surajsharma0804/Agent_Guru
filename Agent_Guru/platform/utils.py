"""Canonical utility functions for the Agent Guru platform layer.

This module provides shared helpers used across platform controllers.

Symmetry guarantee:
    For any two strings ``a`` and ``b``,
    ``fuzzy_match(normalize(a), normalize(b)) == fuzzy_match(normalize(b), normalize(a))``.
    This holds because the implementation checks both ``q in c`` and ``c in q``,
    making the result identical regardless of argument order after normalization.
"""


def normalize(name: str) -> str:
    """Normalize a name for fuzzy matching."""
    return name.strip().lower()


def fuzzy_match(query: str, candidate: str) -> bool:
    """Return True if query matches candidate (case-insensitive partial).

    Symmetric: fuzzy_match(a, b) == fuzzy_match(b, a) for normalized inputs.
    """
    q = normalize(query)
    c = normalize(candidate)
    return q == c or q in c or c in q
