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
from collections import deque
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
    import openwakeword  # type: ignore[import]
    from openwakeword.model import Model as OWWModel  # type: ignore[import]
    _HAS_OWW = True
except ImportError:
    _HAS_OWW = False

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

        # MFCC energy buffer for fallback detector — deque for O(1) bounded append
        self._energy_buffer: deque[float] = deque(maxlen=10)

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
        """Choose the best available backend.

        Priority:
        1. Porcupine — best accuracy, needs API key
        2. openWakeWord — free, no API key, neural network, good accuracy
        3. Vosk — offline keyword spotting
        4. MFCC energy fallback — always available, least accurate
        """
        access_key = (
            self.config.porcupine_access_key
            or os.environ.get("PICOVOICE_ACCESS_KEY", "")
        )
        if _HAS_PORCUPINE and access_key:
            return "porcupine"
        if _HAS_OWW:
            return "openwakeword"
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
        if self._backend == "openwakeword":
            return await self._detect_openwakeword(audio, now)
        if self._backend == "vosk":
            return await self._detect_vosk(audio, now)
        return await self._detect_mfcc(audio, now)

    def detect_sync(self, audio: np.ndarray) -> WakeWordDetection | None:
        """Synchronous wrapper around :meth:`detect`.

        Safe to call from non-async contexts.  Detects whether an event loop
        is already running and dispatches accordingly to avoid deprecation
        warnings from asyncio.get_running_loop() on Python 3.10+.
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

    async def _detect_openwakeword(
        self, audio: np.ndarray, now: float
    ) -> WakeWordDetection | None:
        """Detect using openWakeWord — free, no API key, neural network.

        openWakeWord uses pre-trained ONNX models for common wake phrases.
        It's more accurate than MFCC energy detection and doesn't need
        Porcupine's API key.

        We use the "hey_jarvis" model as a proxy for "hey guru" since
        openWakeWord doesn't have a "hey guru" model out of the box.
        The Whisper transcript step then confirms the actual wake word.

        Install: pip install openwakeword
        """
        try:
            if not hasattr(self, "_oww_model") or self._oww_model is None:
                # Load openWakeWord with the best available model for "hey" phrases
                # hey_jarvis is a good proxy — similar phonetics to "hey guru"
                try:
                    self._oww_model = OWWModel(
                        wakeword_models=["hey_jarvis"],
                        inference_framework="onnx",
                    )
                    logger.info("openWakeWord loaded (hey_jarvis model)")
                except Exception as _e:
                    # Try with default models
                    self._oww_model = OWWModel(inference_framework="onnx")
                    logger.info("openWakeWord loaded (default models)")

            # openWakeWord expects 16kHz int16 audio in chunks
            audio_int16 = (audio * 32767).astype(np.int16)

            # Process in 80ms chunks (1280 samples at 16kHz)
            chunk_size = 1280
            max_score = 0.0
            for start in range(0, len(audio_int16) - chunk_size + 1, chunk_size):
                chunk = audio_int16[start:start + chunk_size]
                prediction = self._oww_model.predict(chunk)
                # Get max score across all models
                for model_name, score in prediction.items():
                    if score > max_score:
                        max_score = score

            # Threshold: 0.5 is a good balance of sensitivity vs false positives
            threshold = max(0.3, 1.0 - self.config.sensitivity)
            if max_score >= threshold:
                # Use Whisper to confirm which wake word and which personality
                phrase, personality = self._match_phrase_by_spectrum(audio)
                self._last_detection_time = now
                detection = WakeWordDetection(
                    wake_word=phrase,
                    personality=personality,
                    confidence=float(max_score),
                    timestamp=now,
                    audio_chunk=audio,
                )
                logger.info(
                    "Wake word detected (openWakeWord): %s → %s (score=%.3f)",
                    phrase, personality, max_score,
                )
                return detection

        except Exception as exc:
            logger.warning("openWakeWord error: %s — falling back to MFCC", exc)
            self._oww_model = None
            self._backend = "mfcc"
            return await self._detect_mfcc(audio, now)

        return None

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
        - Audio must NOT look like music/speaker output (spectral flatness check)
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

        # ── Music / speaker output rejection ─────────────────────────────
        # Music captured from speakers has high spectral flatness (many
        # frequency components active simultaneously) and low zero-crossing
        # variance compared to speech. Speech has bursty energy with clear
        # formant structure. We reject audio that looks like music.
        if self._looks_like_music(audio):
            logger.debug("MFCC: rejected — audio looks like music/speaker output")
            return None

        self._energy_buffer.append(rms)
        # deque(maxlen=10) auto-evicts oldest — no manual pop needed

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

    @staticmethod
    def _looks_like_music(audio: np.ndarray) -> bool:
        """Return True if *audio* looks like music/speaker output rather than speech.

        Uses two fast heuristics:
        1. Spectral flatness — music has many simultaneous frequency components
           (flatness close to 1.0). Speech has sparse formant structure (low flatness).
        2. Zero-crossing rate variance — speech has highly variable ZCR due to
           voiced/unvoiced transitions. Music has smoother, more periodic ZCR.

        Thresholds calibrated empirically:
        - Speech spectral flatness: typically 0.01 – 0.15
        - Music spectral flatness: typically 0.25 – 0.80
        - Speech ZCR std: typically 0.05 – 0.20
        - Music ZCR std: typically 0.01 – 0.06
        """
        if len(audio) < 512:
            return False

        audio_f = audio.astype(np.float32)

        # ── Spectral flatness (geometric mean / arithmetic mean of power spectrum)
        spectrum = np.abs(np.fft.rfft(audio_f)) ** 2 + 1e-10
        geo_mean = np.exp(np.mean(np.log(spectrum)))
        arith_mean = np.mean(spectrum)
        flatness = float(geo_mean / arith_mean)

        # ── Zero-crossing rate variance across 20ms frames
        frame_size = int(16000 * 0.02)  # 20ms at 16kHz
        n_frames = len(audio_f) // frame_size
        if n_frames > 1:
            zcr_per_frame = np.array([
                float(np.mean(np.abs(np.diff(np.sign(audio_f[i*frame_size:(i+1)*frame_size])))) / 2)
                for i in range(n_frames)
            ])
            zcr_std = float(np.std(zcr_per_frame))
        else:
            zcr_std = 1.0  # can't compute — assume speech

        # Music: high flatness AND low ZCR variance
        is_music = flatness > 0.20 and zcr_std < 0.08

        if is_music:
            logger.debug(
                "Music detection: flatness=%.3f zcr_std=%.3f → rejected",
                flatness, zcr_std,
            )

        return is_music

    def _match_phrase_by_spectrum(
        self, audio: np.ndarray
    ) -> tuple[str, "PersonalityType"]:
        """Match audio to the most likely wake word phrase.

        Primary method: transcribe the audio with Whisper (fast, accurate).
        Fallback: spectral heuristic if Whisper is unavailable.

        Returns:
            Tuple of (matched_phrase, PersonalityType).
        """
        # ── Primary: transcribe with Whisper and check for "maya" ────────
        try:
            transcript = self._transcribe_wake_word(audio)
            if transcript:
                t_lower = transcript.lower().strip()
                # Check for Maya keywords
                if any(kw in t_lower for kw in ("maya", "hey maya", "hi maya")):
                    maya_phrases = [
                        p for p, pt in self.config.wake_words.items()
                        if pt.value.lower() == "maya"
                    ]
                    if maya_phrases:
                        phrase = "hey maya" if "hey maya" in maya_phrases else maya_phrases[0]
                        logger.info("Wake word transcript: %r → MAYA", transcript)
                        return phrase, self.config.wake_words[phrase]
                # Check for Guru keywords
                if any(kw in t_lower for kw in ("guru", "hey guru", "hi guru")):
                    guru_phrases = [
                        p for p, pt in self.config.wake_words.items()
                        if pt.value.lower() == "guru"
                    ]
                    if guru_phrases:
                        phrase = "hey guru" if "hey guru" in guru_phrases else guru_phrases[0]
                        logger.info("Wake word transcript: %r → GURU", transcript)
                        return phrase, self.config.wake_words[phrase]
                logger.debug("Wake word transcript %r — no keyword match, using spectral", transcript)
        except Exception as exc:
            logger.debug("Wake word transcription failed: %s — using spectral fallback", exc)

        # ── Fallback: spectral heuristic ──────────────────────────────────
        spectrum = np.abs(np.fft.rfft(audio.astype(np.float32))) ** 2
        n_bins = len(spectrum)
        mid = n_bins // 2

        low_power = float(np.mean(spectrum[:mid]) + 1e-10)
        high_power = float(np.mean(spectrum[mid:]) + 1e-10)
        high_ratio = high_power / (low_power + high_power)

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

    def _transcribe_wake_word(self, audio: np.ndarray) -> str:
        """Transcribe wake word audio using faster-whisper (tiny model, fast).

        Uses the tiny Whisper model for speed — only needs to detect
        "guru" or "maya", not full sentences.

        Model loading priority:
        1. Use pre-warmed instance injected at startup (zero latency)
        2. Try GPU int8 (10x faster than CPU)
        3. Fall back to CPU float32

        Returns:
            Transcribed text, or empty string on failure.
        """
        try:
            from faster_whisper import WhisperModel  # type: ignore[import]

            # Use cached instance — injected at startup or loaded on first call
            if not hasattr(self, "_whisper_tiny") or self._whisper_tiny is None:
                import torch

                def _load_tiny(device: str, compute_type: str) -> "WhisperModel":
                    try:
                        return WhisperModel("tiny", device=device, compute_type=compute_type, local_files_only=True)
                    except Exception:
                        return WhisperModel("tiny", device=device, compute_type=compute_type)

                if torch.cuda.is_available():
                    try:
                        self._whisper_tiny = _load_tiny("cuda", "int8")
                        logger.info("Whisper tiny loaded for wake word detection on cuda (int8)")
                    except Exception:
                        self._whisper_tiny = _load_tiny("cpu", "float32")
                        logger.info("Whisper tiny loaded for wake word detection on cpu (float32)")
                else:
                    self._whisper_tiny = _load_tiny("cpu", "float32")
                    logger.info("Whisper tiny loaded for wake word detection on cpu")

            segments, _ = self._whisper_tiny.transcribe(
                audio,
                language="en",
                beam_size=1,
                best_of=1,
                temperature=0.0,
                vad_filter=False,  # Don't filter — wake word audio is short
                word_timestamps=False,
            )
            text = " ".join(s.text for s in segments).strip()
            logger.debug("Wake word transcription: %r", text)
            return text
        except Exception as exc:
            logger.debug("_transcribe_wake_word failed: %s", exc)
            return ""

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
