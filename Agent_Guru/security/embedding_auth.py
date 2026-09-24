"""Embedding authentication utilities for Agent Guru.

Provides a centralised ``verify_embedding`` helper that enforces cosine
similarity thresholds for both biometric authentication and general
retrieval use-cases.

Thresholds:
    BIOMETRIC_THRESHOLD = 0.97  - FAR < 0.1% for face/voice biometrics
    RETRIEVAL_THRESHOLD = 0.35  - general semantic retrieval

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
# Security note: embedding similarity is NEVER used as the sole authentication gate.
# Secondary verification is always required:
#   - Face auth: liveness detection (anti-spoofing) via FaceFeatureExtractor.is_live
#   - Voice auth: VAD + liveness score check in VoiceAuthenticator
#   - Multi-factor: face + voice fusion (BiometricAuthenticator.authenticate_multi_factor)
# This threshold (0.97) is chosen to achieve FAR < 0.1% per NIST FRVT guidelines.
# Minimum similarity for general semantic retrieval.
#
# CALIBRATION FIX: this was 0.85, and at that value semantic memory retrieval
# returned NOTHING. 0.85 is a biometric-grade number (see BIOMETRIC_THRESHOLD
# above, 0.97) that had been applied to semantic search, where raw cosine
# similarity between a short query and a stored sentence simply does not reach
# it. Measured against the real embedding model this project uses
# (all-mpnet-base-v2), over 12 genuine query/memory pairs and 72 non-matching
# pairs:
#
#     TRUE matches   min 0.281   p10 0.424   median 0.560   max 0.710
#     NON-matches    median 0.083   p90 0.148   p99 0.282   max 0.291
#
#     threshold 0.85: recall   0.0%   false-accept 0.0%   <-- the old value
#     threshold 0.50: recall  66.7%   false-accept 0.0%
#     threshold 0.40: recall  91.7%   false-accept 0.0%
#     threshold 0.35: recall  91.7%   false-accept 0.0%   <-- chosen
#     threshold 0.25: recall 100.0%   false-accept 2.8%
#
# Concretely, "timer" against "User set a timer for 5 minutes" scores 0.641 and
# was being discarded, while the unrelated "User played music" scores 0.177.
# The model discriminates perfectly well; only the cutoff was wrong. The
# assistant's long-term memory could recall a fact only if the user repeated it
# close to verbatim.
#
# 0.35 sits between the noise ceiling (0.291) and the bulk of true matches,
# taking every true match except the single hardest one while admitting no
# noise at all. Retrieval is still primarily top-k RANKED; this is a floor to
# reject junk, not the ranking mechanism.
#
# NOT a security relaxation: this constant is used only by semantic memory
# retrieval (reasoning/memory_retriever.py, reasoning/memory/embedding.py).
# Authentication uses BIOMETRIC_THRESHOLD, which is unchanged at 0.97.
RETRIEVAL_THRESHOLD: float = 0.35


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
        msg = f"threshold must be in [0.0, 1.0], got {threshold!r}"
        raise ValueError(msg)

    norm_q = float(np.linalg.norm(query))
    norm_s = float(np.linalg.norm(stored))

    if norm_q == 0.0 or norm_s == 0.0:
        return False

    score = float(np.dot(query, stored) / (norm_q * norm_s))
    return score >= threshold
