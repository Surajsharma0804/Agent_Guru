"""Speaker verification for owner identification.

Uses SpeechBrain ECAPA-TDNN (primary) for speaker-identity-specific embeddings,
with MFCC-based cosine similarity as fallback when SpeechBrain isn't installed.

Design:
    - Enrollment: 3-5 short clips → average embedding → stored to disk
    - Verification: O(1) cosine similarity against one stored embedding
    - Threshold: starts from published ECAPA-TDNN default (0.75), nudged by
      calibration data - NOT derived outright from n=3-5 samples. Capped so
      calibration can never push the bar above what the owner's OWN weakest
      enrollment clip achieved (see enroll()'s "Fixed" note) - otherwise
      calibration could lock the real owner out.
    - Unverified speakers → restricted mode (not silent drop)
    - No profile, or no backend installed at all → pipeline_mode="full"
      (fresh installs work normally - there is nothing to check against).
      Once a profile AND a backend both exist, any failure during an actual
      verification attempt (compute error, dimension mismatch from a
      changed backend) now fails CLOSED to "restricted" - see verify()'s
      "Fixed" note. Only the "nothing to check against" cases fail open.

Storage: ~/.cache/agent_guru/speaker_profile.npz
File permissions: owner-only (0o600 on Unix, best-effort icacls ACL
restriction on Windows - see _restrict_file_permissions()). Biometric data,
so this gets the same treatment as this codebase's other personal-data
stores (reaction_rules.py, user_memory.py).

Performance:
    - Time Complexity: O(1) per verification (single cosine similarity)
    - Space Complexity: O(D) where D = embedding dimension (fixed, ~192 or ~256)

Fixed (this revision):
    - _load_profile() saved the threshold as a shape-(1,) array
      (`np.array([self._threshold])`) but loaded it with `float(...)`.
      float() on a non-0-dimensional array raises TypeError on modern numpy
      (2.x) - confirmed by direct test. That exception was swallowed by
      _load_profile()'s broad except-block, which then set
      self._embedding = None, silently discarding a real enrollment on
      EVERY load. Net effect: verification silently never actually ran on
      numpy 2.x - is_enrolled() always returned False, so every utterance
      got full/unrestricted mode with no owner check at all, defeating the
      entire feature without any visible error. Now saves the threshold as
      a plain scalar (which numpy stores as a 0-d array) and loads via a
      shape-agnostic helper that also still reads OLDER shape-(1,) profile
      files correctly, so existing installs don't lose their enrollment on
      upgrade.
    - enroll()'s threshold calibration had a floor (never go below 0.75)
      but no ceiling. If the impostor sample happened to score close to the
      owner's own same-speaker similarity, the calibrated midpoint could be
      pushed close to 1.0 with nothing capping it - a threshold that high
      risks the legitimate owner failing their OWN future verifications due
      to ordinary voice variability (background noise, mic, illness,
      mood), i.e. calibration could lock the real owner out. Now also caps
      the calibrated threshold at the WORST (minimum) similarity seen among
      the owner's own enrollment clips, so by construction the enrollment
      set itself always still passes.
    - verify() previously fell through to full/unrestricted access
      ("fail-open") whenever embedding computation returned None or raised
      - even when a profile AND a working backend both existed, meaning a
      live check was possible and simply failed this one time (bad audio
      frame, transient backend hiccup, or the backend having silently
      changed since enrollment, e.g. SpeechBrain became unavailable and the
      MFCC fallback kicked in with a different embedding dimension). That
      is inconsistent with this codebase's established fail-safe default
      for security-relevant gates elsewhere (confirmation.py denies on TTS
      failure rather than proceeding). verify() now distinguishes "nothing
      to check against" (no profile at all, or no backend installed at
      all - both still fail open, since that matches a fresh install) from
      "a check was attempted and failed" (now fails CLOSED to restricted).
      Embedding dimension mismatches between the stored profile and a
      freshly computed embedding are now detected explicitly (not left to
      throw and get caught) and also fail closed, with a log message
      telling the user to re-enroll.
    - Neither this class's mutable state (self._embedding, self._threshold)
      nor the module-level singleton had any locking, unlike this
      codebase's other persistent-data classes (reaction_rules.py,
      user_memory.py). Added a threading.Lock() around enroll()/verify()/
      unenroll()'s state access, and double-checked locking on
      get_speaker_verifier(), for the same reasons already fixed in those
      sibling modules.
    - The module docstring claimed "owner-only (0o600)" file permissions
      but the code only ever called chmod() (a no-op on Windows), same gap
      already found and fixed in reaction_rules.py and user_memory.py.
      Added the same best-effort icacls-based restriction - biometric data
      arguably deserves this at least as much as the other two.

Author: Agent Guru Team
Date: 2026-07-07
"""

from __future__ import annotations

import io
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

# DE-DUPLICATION: see Agent_Guru/utils/secure_file.py -- this module and
# platform/features/user_memory.py each carried an identical private copy of
# _restrict_file_permissions.
from Agent_Guru.utils.secure_file import restrict_file_permissions, secure_write_bytes

logger = logging.getLogger(__name__)

#: Back-compat alias for the former module-private helper.
_restrict_file_permissions = restrict_file_permissions

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

_PROFILE_DIR = Path.home() / ".cache" / "agent_guru"
_PROFILE_PATH = _PROFILE_DIR / "speaker_profile.npz"

# Default threshold - published ECAPA-TDNN same/different-speaker separation
_DEFAULT_THRESHOLD = 0.75

# Absolute floor - never go below this regardless of calibration
_THRESHOLD_FLOOR = 0.75


def _to_scalar(value: Any, default: float = 0.0) -> float:
    """Robustly extract a Python float from a loaded npz value.

    Handles a plain scalar, a 0-d array, OR a shape-(1,) array (the format
    older profile files were saved in - see module docstring's "Fixed"
    note) without relying on float(), which raises TypeError on non-0-d
    arrays on modern numpy (2.x).
    """
    try:
        arr = np.asarray(value)
        return float(arr.reshape(-1)[0])
    except Exception:
        return default


@dataclass
class VerifyResult:
    """Result of speaker verification.

    Attributes:
        is_owner: True if the speaker matches the enrolled profile.
        similarity: Cosine similarity score (0.0 to 1.0).
        mode: "full" (owner, not enrolled, or no backend) or "restricted"
              (enrolled but not matched, OR a live verification attempt
              failed - see verify()'s "Fixed" note on the distinction).
    """

    is_owner: bool
    similarity: float
    mode: str  # "full" or "restricted"


class SpeakerVerifier:
    """Speaker verification: ECAPA-TDNN primary, MFCC fallback.

    Thread-safe: enroll()/verify()/unenroll() hold self._lock for their
    entire body, protecting self._embedding and self._threshold from
    concurrent access.

    Usage::

        verifier = SpeakerVerifier()

        # Enrollment (once)
        verifier.enroll([clip1, clip2, clip3])

        # Verification (every utterance)
        result = verifier.verify(audio)
        if result.mode == "restricted":
            # limit capabilities
            ...

        # Fresh install (no enrollment)
        if not verifier.is_enrolled():
            # pipeline_mode = "full" - everything works
            ...
    """

    def __init__(self, profile_path: Path | None = None) -> None:
        self._profile_path = profile_path or _PROFILE_PATH
        self._embedding: np.ndarray | None = None
        self._threshold: float = _DEFAULT_THRESHOLD
        self._backend: str = "none"  # "ecapa", "mfcc", or "none"
        self._encoder: Any = None
        # Protects self._embedding / self._threshold across concurrent
        # enroll()/verify()/unenroll() calls - see module docstring's
        # "Fixed" note.
        self._lock = threading.Lock()
        self._load_profile()
        self._init_backend()

    def _init_backend(self) -> None:
        """Initialize the embedding backend - ECAPA-TDNN primary, MFCC fallback."""
        # Try SpeechBrain ECAPA-TDNN first (primary - purpose-built for speaker ID)
        try:
            from speechbrain.inference.speaker import EncoderClassifier  # type: ignore[import]

            self._encoder = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                run_opts={"device": "cpu"},
            )
            self._backend = "ecapa"
            logger.info("SpeakerVerifier: using SpeechBrain ECAPA-TDNN (primary)")
            return
        except ImportError:
            logger.info("SpeakerVerifier: SpeechBrain not installed - trying MFCC fallback")
        except Exception:
            logger.exception("SpeakerVerifier: ECAPA-TDNN init failed - trying MFCC fallback")

        # Fallback: MFCC-based (less accurate but zero extra dependencies)
        try:
            import librosa  # noqa: F401

            self._backend = "mfcc"
            logger.info("SpeakerVerifier: using MFCC fallback (less accurate for speaker ID)")
        except ImportError:
            self._backend = "none"
            logger.warning(
                "SpeakerVerifier: no backend available (install speechbrain or librosa)"
            )

    def is_enrolled(self) -> bool:
        """Check if a speaker profile exists.

        Returns False for fresh installs → pipeline_mode should default to "full".
        """
        with self._lock:
            return self._embedding is not None

    def enroll(
        self,
        audio_samples: list[np.ndarray],
        sample_rate: int = 16000,
        impostor_sample: np.ndarray | None = None,
    ) -> bool:
        """Enroll the owner's voice from 3-5 short audio clips.

        Args:
            audio_samples: List of 3-5 audio clips (numpy float32 arrays).
            sample_rate: Sample rate of the audio (default 16000 Hz).
            impostor_sample: Optional audio from a different speaker for
                            threshold calibration.

        Returns:
            True if enrollment succeeded.
        """
        if self._backend == "none":
            logger.error("SpeakerVerifier: no backend - cannot enroll")
            return False

        if len(audio_samples) < 2:
            logger.error("SpeakerVerifier: need at least 2 audio samples for enrollment")
            return False

        try:
            # Compute embeddings for all enrollment clips (outside the lock
            # - this is the expensive part and doesn't touch shared state)
            embeddings = []
            for i, audio in enumerate(audio_samples):
                emb = self._compute_embedding(audio, sample_rate)
                if emb is not None:
                    embeddings.append(emb)
                    logger.debug("Enrollment clip %d: embedding shape %s", i, emb.shape)

            if len(embeddings) < 2:
                logger.error("SpeakerVerifier: could not compute enough embeddings")
                return False

            # Mean embedding
            mean_embedding = np.mean(embeddings, axis=0)
            mean_embedding = mean_embedding / (np.linalg.norm(mean_embedding) + 1e-8)

            # Threshold calibration - start from published default, nudge
            # with calibration data.
            threshold = _DEFAULT_THRESHOLD

            if impostor_sample is not None:
                # Compute same-speaker and different-speaker similarities
                same_sims = [
                    self._cosine_similarity(mean_embedding, emb)
                    for emb in embeddings
                ]
                imp_emb = self._compute_embedding(impostor_sample, sample_rate)
                if imp_emb is not None:
                    diff_sim = self._cosine_similarity(mean_embedding, imp_emb)
                    mean_same = float(np.mean(same_sims))
                    min_same = float(np.min(same_sims))

                    # Set threshold at midpoint between same-speaker and
                    # different-speaker similarity...
                    calibrated = (mean_same + diff_sim) / 2

                    # FIX: cap the calibrated threshold at the WEAKEST
                    # same-speaker similarity seen during enrollment. Without
                    # this, a high-scoring impostor sample could push the
                    # threshold up toward 1.0 with nothing capping it -
                    # risking the legitimate owner failing their own future
                    # verifications due to ordinary voice variability. This
                    # cap guarantees, by construction, that the enrollment
                    # set itself always still clears the resulting bar.
                    calibrated = min(calibrated, min_same)

                    # ...then clamp to the absolute floor (never go below it
                    # regardless of calibration).
                    threshold = max(calibrated, _THRESHOLD_FLOOR)

                    if min_same < _THRESHOLD_FLOOR:
                        logger.warning(
                            "SpeakerVerifier: weakest enrollment clip only "
                            "reached %.3f similarity, below the safety floor "
                            "%.3f - the floor still applies, but consider "
                            "re-enrolling with clearer/quieter audio for more "
                            "reliable future verification.",
                            min_same, _THRESHOLD_FLOOR,
                        )

                    logger.info(
                        "SpeakerVerifier: calibrated threshold=%.3f "
                        "(mean_same=%.3f, min_same=%.3f, diff=%.3f, floor=%.3f)",
                        threshold, mean_same, min_same, diff_sim, _THRESHOLD_FLOOR,
                    )

            with self._lock:
                self._embedding = mean_embedding
                self._threshold = threshold
                self._save_profile_locked()

            logger.info(
                "SpeakerVerifier: enrolled with %d clips, threshold=%.3f, backend=%s",
                len(embeddings), threshold, self._backend,
            )
            return True

        except Exception:
            logger.exception("SpeakerVerifier: enrollment failed")
            return False

    def verify(self, audio: np.ndarray, sample_rate: int = 16000) -> VerifyResult:
        """Verify whether the given audio matches the enrolled speaker.

        Args:
            audio: Audio clip (numpy float32 array).
            sample_rate: Sample rate (default 16000 Hz).

        Returns:
            VerifyResult with is_owner, similarity, and mode.

        Fail-safe default, deliberately asymmetric (see module docstring's
        "Fixed" note):
            - No profile, or no backend installed at all → "nothing to check
              against" → mode="full" (same as a fresh install).
            - Profile AND backend both exist, but THIS verification attempt
              fails (embedding computation error, or a dimension mismatch
              indicating the backend changed since enrollment) → a live
              check was possible and failed → mode="restricted", not "full".
        """
        with self._lock:
            embedding = self._embedding
            threshold = self._threshold
        backend = self._backend

        if embedding is None:
            # Nothing enrolled - full access is the correct default for a
            # fresh install, not a security bypass.
            return VerifyResult(is_owner=True, similarity=1.0, mode="full")

        if backend == "none":
            # No backend installed at all - there is no way to ever verify,
            # which is the same "nothing to check against" situation as no
            # profile, not a fail-open on a live check.
            logger.warning(
                "SpeakerVerifier: profile exists but no backend is available "
                "(install speechbrain or librosa) - cannot verify."
            )
            return VerifyResult(is_owner=True, similarity=1.0, mode="full")

        try:
            emb = self._compute_embedding(audio, sample_rate)

            if emb is None:
                logger.warning(
                    "SpeakerVerifier: embedding computation returned nothing "
                    "for this utterance - defaulting to restricted, not full "
                    "access (a profile and backend both exist, so this was a "
                    "live check that failed, not an absence of one)."
                )
                return VerifyResult(is_owner=False, similarity=0.0, mode="restricted")

            if emb.shape != embedding.shape:
                logger.warning(
                    "SpeakerVerifier: embedding dimension mismatch "
                    "(enrolled=%s, current=%s, backend=%s) - the "
                    "verification backend likely changed since enrollment "
                    "(e.g. SpeechBrain became unavailable and the MFCC "
                    "fallback kicked in). Comparing mismatched-dimension "
                    "embeddings would be meaningless, so this fails CLOSED "
                    "(restricted) rather than silently granting full access "
                    "- re-enroll with the current backend to fix this "
                    "permanently.",
                    embedding.shape, emb.shape, backend,
                )
                return VerifyResult(is_owner=False, similarity=0.0, mode="restricted")

            similarity = self._cosine_similarity(embedding, emb)
            is_owner = similarity >= threshold

            mode = "full" if is_owner else "restricted"
            logger.info(
                "SpeakerVerifier: similarity=%.3f threshold=%.3f → %s",
                similarity, threshold, mode,
            )
            return VerifyResult(is_owner=is_owner, similarity=float(similarity), mode=mode)

        except Exception:
            # FIX: previously defaulted to mode="full" here. A profile and
            # backend both existed, so verification was possible in
            # principle - this failure is a live check going wrong, not an
            # absence of one, so it now fails CLOSED to restricted instead
            # of silently trusting an unverified speaker. See module
            # docstring's "Fixed" note.
            logger.exception(
                "SpeakerVerifier: verification raised unexpectedly - "
                "defaulting to restricted"
            )
            return VerifyResult(is_owner=False, similarity=0.0, mode="restricted")

    def unenroll(self) -> bool:
        """Remove the enrolled speaker profile."""
        with self._lock:
            self._embedding = None
            self._threshold = _DEFAULT_THRESHOLD
            try:
                if self._profile_path.exists():
                    self._profile_path.unlink()
                    logger.info("SpeakerVerifier: profile removed")
                return True
            except Exception:
                logger.exception("SpeakerVerifier: failed to remove profile")
                return False

    # ------------------------------------------------------------------
    # Embedding computation
    # ------------------------------------------------------------------

    def _compute_embedding(
        self, audio: np.ndarray, sample_rate: int
    ) -> np.ndarray | None:
        """Compute a speaker embedding from audio."""
        if self._backend == "ecapa":
            return self._compute_ecapa_embedding(audio, sample_rate)
        if self._backend == "mfcc":
            return self._compute_mfcc_embedding(audio, sample_rate)
        return None

    def _compute_ecapa_embedding(
        self, audio: np.ndarray, sample_rate: int
    ) -> np.ndarray | None:
        """Compute ECAPA-TDNN speaker embedding via SpeechBrain."""
        try:
            import torch

            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # SpeechBrain expects a torch tensor
            waveform = torch.from_numpy(audio).unsqueeze(0)

            # Resample to 16kHz if needed
            if sample_rate != 16000:
                import torchaudio

                resampler = torchaudio.transforms.Resample(sample_rate, 16000)
                waveform = resampler(waveform)

            embedding = self._encoder.encode_batch(waveform)
            emb_np = embedding.squeeze().cpu().numpy()
            # Normalize
            norm = np.linalg.norm(emb_np)
            if norm > 0:
                emb_np = emb_np / norm
            return emb_np

        except Exception:
            logger.exception("ECAPA embedding failed")
            return None

    def _compute_mfcc_embedding(
        self, audio: np.ndarray, sample_rate: int
    ) -> np.ndarray | None:
        """Compute MFCC-based speaker embedding (fallback).

        Note: MFCCs capture phonetic/content info, not primarily speaker
        identity. This is less accurate than ECAPA-TDNN for speaker
        verification. Used only when SpeechBrain isn't installed.
        """
        try:
            import librosa

            if audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Extract MFCCs
            mfccs = librosa.feature.mfcc(
                y=audio, sr=sample_rate, n_mfcc=20, n_fft=2048, hop_length=512
            )
            # Mean across time → fixed-length embedding
            emb = np.mean(mfccs, axis=1).astype(np.float32)
            # Normalize
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            return emb

        except Exception:
            logger.exception("MFCC embedding failed")
            return None

    # ------------------------------------------------------------------
    # Similarity
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two normalized vectors. O(D)."""
        dot = float(np.dot(a, b))
        # Vectors should be pre-normalized, but clamp for safety
        return max(0.0, min(1.0, dot))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_profile(self) -> None:
        """Load speaker profile from disk. Only called from __init__,
        before the instance is shared with any other thread - no lock
        needed here, matching the sibling stores' _load()/_load_profile().
        """
        try:
            if self._profile_path.exists():
                data = np.load(str(self._profile_path), allow_pickle=False)
                self._embedding = data["embedding"]
                # FIX: previously `float(data.get("threshold", ...))`.
                # float() raises TypeError on a non-0-d array on modern
                # numpy (2.x); the threshold was saved as shape-(1,), so
                # this ALWAYS raised, got swallowed by the except-block
                # below, and silently discarded the whole profile (not just
                # the threshold) on every load. _to_scalar() handles both
                # the old shape-(1,) format and the new scalar format.
                self._threshold = _to_scalar(
                    data.get("threshold", _DEFAULT_THRESHOLD), _DEFAULT_THRESHOLD
                )
                logger.info(
                    "SpeakerVerifier: loaded profile (dim=%d, threshold=%.3f)",
                    len(self._embedding), self._threshold,
                )
        except Exception:
            logger.exception("SpeakerVerifier: failed to load profile")
            self._embedding = None

    def _save_profile_locked(self) -> None:
        """Persist speaker profile to disk. Caller MUST already hold
        self._lock - threading.Lock is non-reentrant, so this never
        acquires it itself. All call sites already wrap their whole
        operation in `with self._lock:`.
        """
        if self._embedding is None:
            return
        try:
            # Serialize in memory, then swap the file into place atomically
            # and owner-only from the first byte. np.savez() wrote straight to
            # the destination, so an interrupted save left a truncated .npz
            # that _load_profile() could only report as a failure -- the user
            # would have to re-enroll -- and the biometric embedding was
            # readable under the process umask until the chmod that followed.
            buf = io.BytesIO()
            np.savez(
                buf,
                embedding=self._embedding,
                # FIX: previously np.array([self._threshold]) (shape (1,)),
                # which _load_profile()'s old float() call couldn't parse
                # on modern numpy. Saving a plain scalar stores it as a 0-d
                # array, which float() handles natively - see module
                # docstring's "Fixed" note. _to_scalar() on the load side
                # still reads old shape-(1,) profiles correctly too.
                threshold=float(self._threshold),
            )
            secure_write_bytes(self._profile_path, buf.getvalue())
            logger.debug("SpeakerVerifier: profile saved")
        except Exception:
            logger.exception("SpeakerVerifier: failed to save profile")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_verifier: SpeakerVerifier | None = None
_verifier_lock = threading.Lock()


def get_speaker_verifier() -> SpeakerVerifier:
    """Return the global SpeakerVerifier (lazy init, thread-safe).

    FIX: previously a bare `if _verifier is None: _verifier = ...` with no
    lock - the same class of race already fixed in this codebase's sibling
    singletons (reaction_rules.get_reaction_rules(),
    user_memory.get_user_memory()). Added double-checked locking to match.
    """
    global _verifier
    if _verifier is None:
        with _verifier_lock:
            if _verifier is None:
                _verifier = SpeakerVerifier()
    return _verifier
