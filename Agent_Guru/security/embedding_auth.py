"""Embedding authentication utilities for Agent Guru.

Provides a centralised ``verify_embedding`` helper that enforces cosine
similarity thresholds for both biometric authentication and general
retrieval use-cases.

Thresholds:
    BIOMETRIC_THRESHOLD = 0.97  — FAR < 0.1% for face/voice biometrics
    RETRIEVAL_THRESHOLD = 0.85  — general semantic retrieval

Usage::

    from Agent_Guru.security.embedding_auth import verify_embedding, BIOMETRIC_THRESHOLD, RETRIEVAL_THRESHOLD

    if verify_embedding(query_emb, stored_emb, BIOMETRIC_THRESHOLD):
        grant_access()
"""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Public threshold constants
# ---------------------------------------------------------------------------

BIOMETRIC_THRESHOLD: float = 0.97  # FAR < 0.1% for biometric authentication
RETRIEVAL_THRESHOLD: float = 0.85  # Minimum similarity for general retrieval


def verify_embedding(
    query: np.ndarray,
    stored: np.ndarray,
    threshold: float = BIOMETRIC_THRESHOLD,
) -> bool:
    """Verify that two embeddings are similar enough to be considered a match.

    Computes the cosine similarity between *query* and *stored* and returns
    ``True`` iff the score is greater than or equal to *threshold*.

    Args:
        query: Query embedding vector (any non-zero norm).
        stored: Stored/reference embedding vector (any non-zero norm).
        threshold: Minimum cosine similarity required for a positive match.
            Use :data:`BIOMETRIC_THRESHOLD` (0.97) for face/voice biometrics
            and :data:`RETRIEVAL_THRESHOLD` (0.85) for general retrieval.

    Returns:
        ``True`` if cosine similarity >= *threshold*, ``False`` otherwise.
        Returns ``False`` when either vector has zero norm (degenerate case).

    Raises:
        ValueError: If *threshold* is not in [0.0, 1.0].

    Example::

        >>> import numpy as np
        >>> from Agent_Guru.security.embedding_auth import verify_embedding, BIOMETRIC_THRESHOLD
        >>> a = np.array([1.0, 0.0, 0.0])
        >>> b = np.array([1.0, 0.0, 0.0])
        >>> verify_embedding(a, b, BIOMETRIC_THRESHOLD)
        True
        >>> c = np.array([0.0, 1.0, 0.0])
        >>> verify_embedding(a, c, BIOMETRIC_THRESHOLD)
        False
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold must be in [0.0, 1.0], got {threshold!r}")

    norm_q = float(np.linalg.norm(query))
    norm_s = float(np.linalg.norm(stored))

    if norm_q == 0.0 or norm_s == 0.0:
        return False

    score = float(np.dot(query, stored) / (norm_q * norm_s))
    return score >= threshold
