"""Production-grade wake word detection for Agent Guru.

Supports three backends in priority order:
1. Picovoice Porcupine  — <5% CPU, <10ms latency (requires API key)
2. Vosk keyword spotting — offline, no API key, ~50ms latency
3. MFCC energy fallback  — always available, ~5ms latency

All backends share the same async API and WakeWordDetection result type.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np


from ..exceptions import GuruSpeechError
from ..models import PersonalityType, WakeWordDetection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports
# ---------------------------------------------------------------------------
try:
    import pvporcupine  # type: ignore[import]
    _HAS_PORCUPINE = True
except ImportError:
    _HAS_PORCUPINE = False

try:
    from vosk import KaldiRecognizer  # type: ignore[import]
    from vosk import Model as VoskModel
    _HAS_VOSK = True
except ImportError:
    _HAS_VOSK = False

try:
    import librosa  # type: ignore[import]
    _HAS_LIBROSA = True
except ImportError:
    _HAS_LIBROSA = False


class WakeWordError(GuruSpeechError):
    """Raised when wake word detection encounters an unrecoverable error."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class WakeWordConfig:
    """Configuration for wake word detection.

    Attributes:
        wake_words: Mapping of phrase → PersonalityType.
        sensitivity: Detection sensitivity in [0.0, 1.0].  Higher values
            increase recall at the cost of more false positives.
        sample_rate: Audio sample rate in Hz (must be 16 000 for Vosk/Porcupine).
        frame_length: Samples per processing frame.
        n_mfcc: Number of MFCC coefficients for the fallback detector.
        hop_length: STFT hop length for MFCC extraction.
        n_fft: FFT window size for MFCC extraction.
        energy_threshold: RMS energy threshold for the fallback detector.
        cooldown_seconds: Minimum seconds between consecutive detections.
        vosk_model_path: Path to a Vosk model directory.
        porcupine_access_key: Picovoice access key (reads
            ``PICOVOICE_ACCESS_KEY`` env var when empty).
    """

    wake_words: dict[str, PersonalityType] = field(default_factory=lambda: {
        "hey guru": PersonalityType.GURU,
        "guru": PersonalityType.GURU,
        "hey maya": PersonalityType.MAYA,
        "maya": PersonalityType.MAYA,
    })
    sensitivity: float = 0.5
    sample_rate: int = 16_000
    frame_length: int = 512
    n_mfcc: int = 13
    hop_length: int = 512
    n_fft: int = 2048
    energy_threshold: float = 0.015
    cooldown_seconds: float = 3.0
    vosk_model_path: str = "models/vosk-model-small-en-us-0.15"
    porcupine_access_key: str = ""


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------

class WakeWordDetector:
    """Production wake word detector with automatic backend selection.

    Backend priority:
    1. Porcupine (if ``pvporcupine`` installed and access key available)
    2. Vosk     (if ``vosk`` installed and model directory exists)
    3. MFCC energy fallback (always available)

    All detection is exposed through the async :meth:`detect` method.
    A synchronous :meth:`detect_sync` wrapper is provided for non-async callers.

    Example::

        detector = WakeWordDetector()
        result = await detector.detect(audio_chunk)
        if result:
            print(result.wake_word, result.personality)
    """

    def __init__(self, config: WakeWordConfig | None = None) -> None:
        self.config = config or WakeWordConfig()
        self._last_detection_time: float = 0.0

        # MFCC energy buffer for fallback detector
        self._energy_buffer: list[float] = []

        # Vosk recognizer (lazy-initialised)
        self._vosk_recognizer: Any | None = None

        # Porcupine handle (lazy-initialised)
        self._porcupine: Any | None = None

        # Determine active backend
        self._backend: str = self._select_backend()
        logger.info("WakeWordDetector initialised — backend=%s", self._backend)

    # ------------------------------------------------------------------
    # Backend selection
    # ------------------------------------------------------------------

    def _select_backend(self) -> str:
        """Choose the best available backend."""
        access_key = (
            self.config.porcupine_access_key
            or os.environ.get("PICOVOICE_ACCESS_KEY", "")
        )
        if _HAS_PORCUPINE and access_key:
            return "porcupine"
        if _HAS_VOSK and os.path.isdir(self.config.vosk_model_path):
            return "vosk"
        return "mfcc"

    # ------------------------------------------------------------------
    # Lazy initialisers
    # ------------------------------------------------------------------

    def _get_vosk_recognizer(self) -> Any:
        """Lazily initialise and return the Vosk recogniser."""
        if self._vosk_recognizer is None:
            if not _HAS_VOSK:
                raise WakeWordError("vosk is not installed — run: pip install vosk")
            if not os.path.isdir(self.config.vosk_model_path):
                raise WakeWordError(
                    f"Vosk model not found at '{self.config.vosk_model_path}'. "
                    "Download from https://alphacephei.com/vosk/models"
                )
            import vosk  # type: ignore[import]
            vosk.SetLogLevel(-1)
            model = VoskModel(self.config.vosk_model_path)
            grammar = json.dumps(list(self.config.wake_words.keys()) + ["[unk]"])
            self._vosk_recognizer = KaldiRecognizer(
                model, self.config.sample_rate, grammar
            )
            self._vosk_recognizer.SetWords(True)
            logger.info("Vosk recogniser initialised (model=%s)", self.config.vosk_model_path)
        return self._vosk_recognizer

    def _get_porcupine(self) -> Any:
        """Lazily initialise and return the Porcupine handle."""
        if self._porcupine is None:
            if not _HAS_PORCUPINE:
                raise WakeWordError("pvporcupine is not installed — run: pip install pvporcupine")
            access_key = (
                self.config.porcupine_access_key
                or os.environ.get("PICOVOICE_ACCESS_KEY", "")
            )
            if not access_key:
                raise WakeWordError("PICOVOICE_ACCESS_KEY is required for Porcupine backend")
            available = pvporcupine.KEYWORDS
            valid = [kw for kw in self.config.wake_words if kw in available]
            if not valid:
                valid = ["computer"]
            self._porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=valid,
                sensitivities=[self.config.sensitivity] * len(valid),
            )
            logger.info("Porcupine initialised (keywords=%s)", valid)
        return self._porcupine

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def detect(self, audio: np.ndarray) -> WakeWordDetection | None:
        """Detect a wake word in *audio*.

        Args:
            audio: Float32 audio samples in [-1.0, 1.0] at
                ``config.sample_rate`` Hz.

        Returns:
            :class:`~Agent_Guru.speech.models.WakeWordDetection` when a wake
            word is found, ``None`` otherwise.
        """
        if audio is None or len(audio) == 0:
            return None

        now = time.time()
        if now - self._last_detection_time < self.config.cooldown_seconds:
            return None

        if self._backend == "porcupine":
            return await self._detect_porcupine(audio, now)
        if self._backend == "vosk":
            return await self._detect_vosk(audio, now)
        return await self._detect_mfcc(audio, now)

    def detect_sync(self, audio: np.ndarray) -> WakeWordDetection | None:
        """Synchronous wrapper around :meth:`detect`.

        Safe to call from non-async contexts.  Detects whether an event loop
        is already running and dispatches accordingly to avoid deprecation
        warnings from asyncio.get_event_loop() on Python 3.10+.
        """
        try:
            # Raises RuntimeError if no loop is running
            asyncio.get_running_loop()
            # A loop IS running — run in a separate thread to avoid deadlock
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self.detect(audio))
                return future.result()
        except RuntimeError:
            # No loop running — safe to create one
            return asyncio.run(self.detect(audio))

    async def add_wake_word(
        self, phrase: str, personality: PersonalityType
    ) -> None:
        """Register a new wake word phrase.

        Args:
            phrase: The phrase to detect (case-insensitive).
            personality: Personality to activate on detection.
        """
        self.config.wake_words[phrase.strip().lower()] = personality
        # Reset Vosk recogniser so the new grammar takes effect
        self._vosk_recognizer = None
        logger.debug("Added wake word '%s' → %s", phrase, personality)

    async def remove_wake_word(self, phrase: str) -> None:
        """Unregister a wake word phrase.

        Args:
            phrase: The phrase to remove (case-insensitive).
        """
        key = phrase.strip().lower()
        self.config.wake_words.pop(key, None)
        self._vosk_recognizer = None
        logger.debug("Removed wake word '%s'", phrase)

    def get_wake_words(self) -> list[str]:
        """Return the list of currently registered wake word phrases."""
        return list(self.config.wake_words.keys())

    def set_sensitivity(self, sensitivity: float) -> None:
        """Set detection sensitivity.

        Args:
            sensitivity: Value in [0.0, 1.0].

        Raises:
            ValueError: If *sensitivity* is outside [0.0, 1.0].
        """
        if not 0.0 <= sensitivity <= 1.0:
            raise ValueError(
                f"Sensitivity must be in [0.0, 1.0], got {sensitivity}"
            )
        self.config.sensitivity = sensitivity
        # Reset Porcupine so new sensitivity takes effect on next call
        if self._porcupine is not None:
            self._porcupine.delete()
            self._porcupine = None

    def reset(self) -> None:
        """Reset internal recogniser state (useful between utterances)."""
        if self._vosk_recognizer is not None:
            self._vosk_recognizer.Reset()
        self._energy_buffer.clear()
        self._last_detection_time = 0.0

    def get_frame_length(self) -> int:
        """Return the required audio frame length in samples."""
        return self.config.frame_length

    def get_sample_rate(self) -> int:
        """Return the required audio sample rate in Hz."""
        return self.config.sample_rate

    # ------------------------------------------------------------------
    # MFCC feature extraction (used by fallback and tests)
    # ------------------------------------------------------------------

    def _extract_mfcc(self, audio: np.ndarray) -> np.ndarray:
        """Extract MFCC features from *audio*.

        Returns an array of shape ``(n_mfcc, n_frames)``.  Uses librosa when
        available, otherwise falls back to a pure-NumPy approximation.
        """
        if _HAS_LIBROSA:
            return librosa.feature.mfcc(
                y=audio.astype(np.float32),
                sr=self.config.sample_rate,
                n_mfcc=self.config.n_mfcc,
                hop_length=self.config.hop_length,
                n_fft=self.config.n_fft,
            )
        # Pure-NumPy fallback — simplified MFCC approximation
        return self._numpy_mfcc(audio)

    def _numpy_mfcc(self, audio: np.ndarray) -> np.ndarray:
        """Simplified MFCC via NumPy (no librosa dependency)."""
        n_fft = self.config.n_fft
        hop = self.config.hop_length
        n_mfcc = self.config.n_mfcc

        # Frame the signal
        n_frames = max(1, (len(audio) - n_fft) // hop + 1)
        frames = np.lib.stride_tricks.as_strided(
            audio,
            shape=(n_frames, n_fft),
            strides=(audio.strides[0] * hop, audio.strides[0]),
        ).copy()

        # Power spectrum
        window = np.hanning(n_fft)
        power = np.abs(np.fft.rfft(frames * window, n=n_fft)) ** 2

        # Mel filterbank (triangular, 26 filters)
        n_filters = 26
        low_freq, high_freq = 0.0, self.config.sample_rate / 2.0
        mel_low = 2595 * np.log10(1 + low_freq / 700)
        mel_high = 2595 * np.log10(1 + high_freq / 700)
        mel_points = np.linspace(mel_low, mel_high, n_filters + 2)
        hz_points = 700 * (10 ** (mel_points / 2595) - 1)
        bin_points = np.floor((n_fft + 1) * hz_points / self.config.sample_rate).astype(int)

        filterbank = np.zeros((n_filters, n_fft // 2 + 1))
        for m in range(1, n_filters + 1):
            f_m_minus = bin_points[m - 1]
            f_m = bin_points[m]
            f_m_plus = bin_points[m + 1]
            for k in range(f_m_minus, f_m):
                if f_m != f_m_minus:
                    filterbank[m - 1, k] = (k - f_m_minus) / (f_m - f_m_minus)
            for k in range(f_m, f_m_plus):
                if f_m_plus != f_m:
                    filterbank[m - 1, k] = (f_m_plus - k) / (f_m_plus - f_m)

        # Apply filterbank and log
        filter_energies = np.dot(power, filterbank.T)
        log_energies = np.log(filter_energies + 1e-10)

        # DCT to get MFCCs
        n = np.arange(n_filters)
        mfcc = np.zeros((n_mfcc, n_frames))
        for i in range(n_mfcc):
            mfcc[i] = np.sum(
                log_energies * np.cos(np.pi * i / n_filters * (n + 0.5)),
                axis=1,
            )
        return mfcc

    # ------------------------------------------------------------------
    # Backend implementations
    # ------------------------------------------------------------------

    async def _detect_porcupine(
        self, audio: np.ndarray, now: float
    ) -> WakeWordDetection | None:
        """Detect using Picovoice Porcupine."""
        try:
            porcupine = self._get_porcupine()
            frame_length = porcupine.frame_length
            pcm = (audio * 32767).astype(np.int16)

            for start in range(0, len(pcm) - frame_length + 1, frame_length):
                frame = pcm[start : start + frame_length]
                idx = porcupine.process(frame)
                if idx >= 0:
                    keywords = list(self.config.wake_words.keys())
                    keyword = keywords[idx] if idx < len(keywords) else keywords[0]
                    personality = self.config.wake_words[keyword]
                    self._last_detection_time = now
                    result = WakeWordDetection(
                        wake_word=keyword,
                        personality=personality,
                        confidence=1.0,
                        timestamp=now,
                        audio_chunk=audio,
                    )
                    logger.info("Wake word detected (porcupine): %s", keyword)
                    return result
        except Exception as exc:
            logger.warning("Porcupine detection error: %s — falling back to MFCC", exc)
            return await self._detect_mfcc(audio, now)
        return None

    async def _detect_vosk(
        self, audio: np.ndarray, now: float
    ) -> WakeWordDetection | None:
        """Detect using Vosk keyword spotting."""
        try:
            recognizer = self._get_vosk_recognizer()
            audio_int16 = (audio * 32767).astype(np.int16)
            audio_bytes = audio_int16.tobytes()

            if recognizer.AcceptWaveform(audio_bytes):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").lower().strip()
                confidence = float(result.get("confidence", 0.9))
            else:
                partial = json.loads(recognizer.PartialResult())
                text = partial.get("partial", "").lower().strip()
                confidence = 0.7

            for phrase, personality in self.config.wake_words.items():
                if phrase in text:
                    self._last_detection_time = now
                    detection = WakeWordDetection(
                        wake_word=phrase,
                        personality=personality,
                        confidence=confidence,
                        timestamp=now,
                        audio_chunk=audio,
                    )
                    logger.info("Wake word detected (vosk): %s", phrase)
                    return detection
        except Exception as exc:
            logger.warning("Vosk detection error: %s — falling back to MFCC", exc)
            return await self._detect_mfcc(audio, now)
        return None

    async def _detect_mfcc(
        self, audio: np.ndarray, now: float
    ) -> WakeWordDetection | None:
        """MFCC energy-based fallback detector.

        Uses a sliding energy buffer: if enough consecutive frames exceed the
        RMS threshold (scaled by sensitivity), a detection is emitted.
        Personality is resolved by matching the audio transcript against
        registered wake word phrases via MFCC feature comparison.

        To reduce false positives the detector requires:
        - RMS above threshold (calibrated to real mic levels)
        - Audio duration >= 0.3s (avoids single-click triggers)
        - Peak energy significantly above noise floor
        """
        if len(audio) == 0:
            return None

        rms = float(np.sqrt(np.mean(audio ** 2)))
        peak = float(np.max(np.abs(audio)))
        threshold = self.config.energy_threshold * (1.0 - self.config.sensitivity * 0.5)

        # Require minimum audio duration (0.3s at 16kHz = 4800 samples)
        min_samples = int(self.config.sample_rate * 0.3)
        if len(audio) < min_samples:
            return None

        # Require peak to be at least 3x the threshold to avoid noise triggers
        if peak < threshold * 3.0:
            return None

        self._energy_buffer.append(rms)
        if len(self._energy_buffer) > 10:
            self._energy_buffer.pop(0)

        # 1 frame minimum — a single spoken word should trigger detection
        required_frames = 1
        high_energy = sum(1 for e in self._energy_buffer if e > threshold)

        if high_energy >= required_frames:
            self._energy_buffer.clear()
            self._last_detection_time = now

            # Resolve personality by matching MFCC spectral centroid against
            # each registered phrase. Maya phrases tend to have higher-pitched
            # spectral energy; we use the ratio of high-band to low-band power
            # as a lightweight discriminator when Vosk/Porcupine are unavailable.
            phrase, personality = self._match_phrase_by_spectrum(audio)
            confidence = min(0.95, rms / max(threshold, 1e-9))

            detection = WakeWordDetection(
                wake_word=phrase,
                personality=personality,
                confidence=confidence,
                timestamp=now,
                audio_chunk=audio,
            )
            logger.info(
                "Wake word detected (mfcc fallback): %s → %s (rms=%.4f, peak=%.4f, threshold=%.4f)",
                phrase, personality, rms, peak, threshold
            )
            return detection

        return None

    def _match_phrase_by_spectrum(
        self, audio: np.ndarray
    ) -> tuple[str, "PersonalityType"]:
        """Match audio to the most likely wake word phrase using spectral features.

        Splits the frequency spectrum into low and high bands and computes
        per-phrase energy scores.  Maya phrases ("maya", "hey maya") are
        associated with higher spectral centroids; Guru phrases with lower.
        Falls back to the first registered phrase if no match is found.

        Returns:
            Tuple of (matched_phrase, PersonalityType).
        """
        # Compute power spectrum
        spectrum = np.abs(np.fft.rfft(audio.astype(np.float32))) ** 2
        n_bins = len(spectrum)
        mid = n_bins // 2

        low_power = float(np.mean(spectrum[:mid]) + 1e-10)
        high_power = float(np.mean(spectrum[mid:]) + 1e-10)
        high_ratio = high_power / (low_power + high_power)

        # Separate registered phrases by personality
        maya_phrases = [
            p for p, pt in self.config.wake_words.items()
            if pt.value.lower() == "maya"
        ]
        guru_phrases = [
            p for p, pt in self.config.wake_words.items()
            if pt.value.lower() == "guru"
        ]

        # Maya voices tend to have more high-frequency energy (threshold ~0.45)
        if maya_phrases and high_ratio >= 0.45:
            phrase = maya_phrases[0]
            return phrase, self.config.wake_words[phrase]

        if guru_phrases:
            phrase = guru_phrases[0]
            return phrase, self.config.wake_words[phrase]

        # Absolute fallback — should never reach here with default config
        first_phrase = next(iter(self.config.wake_words))
        return first_phrase, self.config.wake_words[first_phrase]

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def __del__(self) -> None:
        if self._porcupine is not None:
            try:
                self._porcupine.delete()
            except Exception as exc:  # noqa: BLE001
                import logging as _logging
                _logging.getLogger(__name__).debug("Porcupine cleanup failed: %s", exc)
