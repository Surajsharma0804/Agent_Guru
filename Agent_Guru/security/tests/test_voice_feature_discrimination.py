"""Voice biometrics must actually tell voices apart.

REGRESSION TEST for an authentication bypass.

VoiceFeatureExtractor.extract_features() concatenates 52 components measured
in wildly different units: MFCCs O(1-100), pitch and spectral values in HERTZ
(O(100-7000)), zero-crossing rate and RMS O(0.01). They used to be
concatenated raw, so two Hz-valued components dominated the vector completely
-- spectral-rolloff mean alone measured 6806, about 59% of the vector's total
L1 mass -- and those components barely move between speakers.

VoiceAuthenticator compares templates with COSINE similarity against a 0.97
biometric threshold. With the vector dominated by two near-constant terms,
every pair of voices scored ~0.9998 and the threshold separated nobody from
anybody: enrolling a 105 Hz speaker and then presenting a 210 Hz speaker --
an octave apart, unmistakably a different person -- authenticated with
similarity 0.999857.

Raising the threshold could not have fixed it; there was no margin left, and
the ordering was not reliable. The components are now scaled into comparable
units and the vector is L2-normalised, which lets the whole vector count.

These tests fail loudly if that ever regresses.
"""

from __future__ import annotations

import numpy as np
import pytest

from Agent_Guru.security.voice_auth import VoiceAuthenticator
from Agent_Guru.speech.biometric.voice_features import VoiceFeatureExtractor

SAMPLE_RATE = 16000


def voiced_tone(f0: float, seconds: float = 3.0, seed: int = 1) -> np.ndarray:
    """A voiced, syllable-modulated signal at a given fundamental frequency.

    Two clips differing only in f0 are the mildest possible "different
    speaker" -- if the representation cannot separate an octave of pitch, it
    cannot separate anything.
    """
    rng = np.random.default_rng(seed)
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    phase = 2 * np.pi * f0 * t
    signal = sum(
        amplitude * np.sin(k * phase)
        for k, amplitude in enumerate([1.0, 0.6, 0.45, 0.3, 0.22, 0.16, 0.12, 0.09], start=1)
    )
    envelope = np.clip(0.5 * (1 + np.sin(2 * np.pi * 4.0 * t - np.pi / 2)) ** 2, 0.02, None)
    signal = signal * envelope
    signal = signal + 0.22 * np.diff(np.concatenate([[0.0], rng.normal(0, 1, n)])) * envelope
    return (0.6 * signal / (np.max(np.abs(signal)) + 1e-9)).astype(np.float32)


@pytest.fixture
def extractor() -> VoiceFeatureExtractor:
    return VoiceFeatureExtractor()


@pytest.mark.asyncio
@pytest.mark.usefixtures("requires_librosa")
async def test_no_single_component_dominates_the_feature_vector(
    extractor: VoiceFeatureExtractor,
) -> None:
    """The failure mode was one component carrying most of the vector's mass."""
    features = await extractor.extract_features(voiced_tone(120.0), SAMPLE_RATE)
    vector = np.abs(np.asarray(features.feature_vector, dtype=np.float64))

    share = float(vector.max() / (vector.sum() + 1e-12))

    assert share < 0.25, (  # nosec B101
        f"One feature carries {share:.1%} of the vector's L1 mass. Cosine "
        "similarity is then decided by that component alone, which is how "
        "voice authentication stopped discriminating (it was 59%)."
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("requires_librosa")
async def test_impostor_is_rejected(extractor: VoiceFeatureExtractor) -> None:
    """An octave apart must not authenticate. This is the bypass itself."""
    authenticator = VoiceAuthenticator()
    authenticator.enroll_user("alice", await extractor.extract_features(voiced_tone(105.0), SAMPLE_RATE))

    impostor = await extractor.extract_features(voiced_tone(210.0), SAMPLE_RATE)
    authenticated, user_id, similarity = authenticator.authenticate(impostor, user_id="alice")

    assert authenticated is False, (  # nosec B101
        f"A 210 Hz speaker authenticated as a 105 Hz speaker "
        f"(similarity={similarity:.6f}, threshold="
        f"{authenticator.effective_similarity_threshold})."
    )
    assert similarity < authenticator.effective_similarity_threshold  # nosec B101


@pytest.mark.asyncio
@pytest.mark.usefixtures("requires_librosa")
async def test_genuine_speaker_still_authenticates(
    extractor: VoiceFeatureExtractor,
) -> None:
    """Rejecting everybody would be an equally broken way to pass the above."""
    authenticator = VoiceAuthenticator()
    authenticator.enroll_user(
        "alice",
        await extractor.extract_features(voiced_tone(105.0, seed=1), SAMPLE_RATE),
    )

    # Same voice, a different recording (different noise realisation).
    again = await extractor.extract_features(voiced_tone(105.0, seed=99), SAMPLE_RATE)
    authenticated, user_id, similarity = authenticator.authenticate(again, user_id="alice")

    assert authenticated is True, (  # nosec B101
        f"The enrolled speaker was rejected on a second recording "
        f"(similarity={similarity:.6f})."
    )
    assert user_id == "alice"  # nosec B101


@pytest.mark.asyncio
@pytest.mark.usefixtures("requires_librosa")
async def test_there_is_a_usable_margin(extractor: VoiceFeatureExtractor) -> None:
    """Genuine and impostor scores must be separated, not merely ordered.

    Before the fix, genuine and impostor both sat at ~0.9998 -- technically
    ordered, with no margin any threshold could exploit.
    """
    genuine_a = await extractor.extract_features(voiced_tone(105.0, seed=1), SAMPLE_RATE)
    genuine_b = await extractor.extract_features(voiced_tone(105.0, seed=99), SAMPLE_RATE)
    impostor = await extractor.extract_features(voiced_tone(210.0, seed=1), SAMPLE_RATE)

    def cosine(x: np.ndarray, y: np.ndarray) -> float:
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        return float(x @ y / (np.linalg.norm(x) * np.linalg.norm(y) + 1e-12))

    same = cosine(genuine_a.feature_vector, genuine_b.feature_vector)
    different = cosine(genuine_a.feature_vector, impostor.feature_vector)

    assert same - different > 0.1, (  # nosec B101
        f"Genuine similarity {same:.6f} and impostor similarity "
        f"{different:.6f} are {same - different:.6f} apart. No threshold can "
        "separate voices reliably with a margin that small."
    )
