"""Wake word detection for Agent Guru.

Backends in priority order, each used only when it can hear the configured
wake words themselves:
1. Picovoice Porcupine - an access key and one of the wake words among its
   built-in keywords
2. openWakeWord - a model file per wake word in the wake model folder
3. Vosk keyword spotting - a Vosk model directory
4. MFCC energy fallback - always available; a loudness gate, not a detector

All backends share the same async API and WakeWordDetection result type.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from Agent_Guru.speech.exceptions import GuruSpeechError
from Agent_Guru.speech.models import PersonalityType, WakeWordDetection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports
# ---------------------------------------------------------------------------
try:
    import pvporcupine

    _HAS_PORCUPINE = True
except ImportError:
    _HAS_PORCUPINE = False

try:
    from vosk import KaldiRecognizer
    from vosk import Model as VoskModel

    _HAS_VOSK = True
except ImportError:
    _HAS_VOSK = False

try:
    import openwakeword  # noqa: F401
    from openwakeword.model import Model as OWWModel

    _HAS_OWW = True
except ImportError:
    _HAS_OWW = False

try:
    import librosa

    _HAS_LIBROSA = True
except ImportError:
    _HAS_LIBROSA = False


class WakeWordError(GuruSpeechError):
    """Raised when wake word detection encounters an unrecoverable error."""


# openWakeWord requires 80ms chunks (1280 samples @ 16kHz) per inference
# call -- a fixed property of the model, not configurable via
# WakeWordConfig.frame_length. See get_frame_length()'s docstring.
_OWW_CHUNK_SIZE = 1280


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
        oww_model_dir: Folder of openWakeWord models, one per wake word,
            named after it (``hey_guru.onnx``). Empty means the
            ``wake_models`` folder in the app data directory.

    """

    wake_words: dict[str, PersonalityType] = field(
        default_factory=lambda: {
            "hey guru": PersonalityType.GURU,
            "guru": PersonalityType.GURU,
            "hey maya": PersonalityType.MAYA,
            "maya": PersonalityType.MAYA,
        },
    )
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
    oww_model_dir: str = ""


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------


class WakeWordDetector:
    """Production wake word detector with automatic backend selection.

    Backend priority: see the module docstring. The choice and the reason
    for it are logged when the detector is created.

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

        # MFCC energy buffer for fallback detector - deque for O(1) bounded append
        self._energy_buffer: deque[float] = deque(maxlen=10)

        # Vosk recognizer (lazy-initialised)
        self._vosk_recognizer: Any | None = None

        # Porcupine handle (lazy-initialised)
        self._porcupine: Any | None = None

        # openWakeWord model, loaded when the backend is chosen, and the
        # phrase each of its model names stands for
        self._oww_model: Any | None = None
        self._oww_phrases: dict[str, str] = {}

        # Whisper tiny model (lazy-initialised)
        self._whisper_tiny: Any | None = None

        # Determine active backend
        self._backend_reason: str = ""
        self._backend: str = self._select_backend()
        logger.info("WakeWordDetector initialised - backend=%s: %s", self._backend, self._backend_reason)

    # ------------------------------------------------------------------
    # Backend selection
    # ------------------------------------------------------------------

    def _select_backend(self) -> str:
        """Choose the best backend that can hear the configured wake words.

        openWakeWord used to be chosen whenever the package was installed. It
        ships no model for "hey guru" or "hey maya", so it loaded the stock
        hey_jarvis model as a stand-in, which caught 0 of 28 recorded wake
        phrases: installing the package made the assistant deaf, and nothing
        said why. Porcupine did the same with its built-in "computer". Each
        backend is now taken only when it has something for these phrases,
        and every step down the chain says why in _backend_reason.
        """
        reasons: list[str] = []
        access_key = self.config.porcupine_access_key or os.environ.get("PICOVOICE_ACCESS_KEY", "")
        if not _HAS_PORCUPINE:
            reasons.append("porcupine not installed")
        elif not access_key:
            reasons.append("porcupine has no access key")
        elif not [kw for kw in self.config.wake_words if kw in pvporcupine.KEYWORDS]:
            reasons.append("porcupine has no built-in keyword for these wake words")
        else:
            self._backend_reason = "Picovoice key set and a built-in keyword matches"
            return "porcupine"

        oww = self._load_openwakeword(reasons)
        if oww:
            self._backend_reason = oww
            return "openwakeword"

        if not _HAS_VOSK:
            reasons.append("vosk not installed")
        elif not os.path.isdir(self.config.vosk_model_path):  # noqa: PTH112
            reasons.append(f"no Vosk model at {self.config.vosk_model_path}")
        else:
            self._backend_reason = f"Vosk model at {self.config.vosk_model_path}"
            return "vosk"

        self._backend_reason = (
            "; ".join(reasons)
            + ". The MFCC fallback wakes on any loud sound, not only the wake words"
        )
        return "mfcc"

    def _oww_model_dir(self) -> Path:
        if self.config.oww_model_dir:
            return Path(self.config.oww_model_dir)
        from Agent_Guru.utils.path_utils import app_data_dir

        return app_data_dir("wake_models", create=False)

    def _load_openwakeword(self, reasons: list[str]) -> str:
        """Load a model for each wake word that has one; the reason it was chosen, or "".

        Loaded here rather than on the first chunk so a missing feature model
        or a damaged file shows up in the startup log as the reason for the
        fallback, not as an error on the first sound the microphone hears.
        """
        if not _HAS_OWW:
            reasons.append("openwakeword not installed")
            return ""
        folder = self._oww_model_dir()
        files = {
            phrase: folder / f"{phrase.replace(' ', '_')}.onnx" for phrase in self.config.wake_words
        }
        found = {phrase: path for phrase, path in files.items() if path.is_file()}
        if not found:
            names = ", ".join(path.name for path in files.values())
            reasons.append(f"openwakeword has no model for these wake words (looked for {names} in {folder})")
            return ""
        try:
            self._oww_model = OWWModel(
                wakeword_models=[str(path) for path in found.values()],
                inference_framework="onnx",
            )
        except Exception as exc:
            reasons.append(f"openwakeword could not load {', '.join(p.name for p in found.values())}: {exc}")
            return ""
        self._oww_phrases = {path.stem: phrase for phrase, path in found.items()}
        missing = [phrase for phrase in self.config.wake_words if phrase not in found]
        reason = f"models for {', '.join(found)} in {folder}"
        if missing:
            reason += f" (none for {', '.join(missing)}, which cannot wake it)"
        return reason

    # ------------------------------------------------------------------
    # Lazy initialisers
    # ------------------------------------------------------------------

    def _get_vosk_recognizer(self) -> Any:
        """Lazily initialise and return the Vosk recogniser."""
        if self._vosk_recognizer is None:
            if not _HAS_VOSK:
                msg = "vosk is not installed - run: pip install vosk"
                raise WakeWordError(msg)
            if not os.path.isdir(self.config.vosk_model_path):  # noqa: PTH112
                msg = (
                    f"Vosk model not found at '{self.config.vosk_model_path}'. "
                    "Download from https://alphacephei.com/vosk/models"
                )
                raise WakeWordError(
                    msg,
                )
            import vosk

            vosk.SetLogLevel(-1)
            model = VoskModel(self.config.vosk_model_path)
            grammar = json.dumps([*list(self.config.wake_words.keys()), "[unk]"])
            self._vosk_recognizer = KaldiRecognizer(model, self.config.sample_rate, grammar)
            self._vosk_recognizer.SetWords(True)
            logger.info("Vosk recogniser initialised (model=%s)", self.config.vosk_model_path)
        return self._vosk_recognizer

    def _get_porcupine(self) -> Any:
        """Lazily initialise and return the Porcupine handle."""
        if self._porcupine is None:
            if not _HAS_PORCUPINE:
                msg = "pvporcupine is not installed - run: pip install pvporcupine"
                raise WakeWordError(msg)
            access_key = self.config.porcupine_access_key or os.environ.get(
                "PICOVOICE_ACCESS_KEY",
                "",
            )
            if not access_key:
                msg = "PICOVOICE_ACCESS_KEY is required for Porcupine backend"
                raise WakeWordError(msg)
            available = pvporcupine.KEYWORDS
            valid = [kw for kw in self.config.wake_words if kw in available]
            if not valid:
                # Was a silent switch to "computer", a word the owner never
                # chose, so the assistant answered to it and not to its name.
                msg = "Porcupine has no built-in keyword for any configured wake word"
                raise WakeWordError(msg)
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
            # A loop IS running - run in a separate thread to avoid deadlock
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self.detect(audio))
                return future.result()
        except RuntimeError:
            # No loop running - safe to create one
            return asyncio.run(self.detect(audio))

    async def add_wake_word(self, phrase: str, personality: PersonalityType) -> None:
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
            msg = f"Sensitivity must be in [0.0, 1.0], got {sensitivity}"
            raise ValueError(msg)
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

    def start_cooldown(self) -> None:
        """Start the cooldown again now, when the turn a wake word started has ended.

        The cooldown used to count only from the moment of detection. A turn
        takes longer than the 3 s cooldown, so it had always run out by the
        time the listen loop read the microphone again, and the first chunk
        after a turn could wake it at once. That chunk is often stale: the
        stream holds 2 to 2.5 s of audio that arrived during the turn, the
        end of the spoken reply included.
        """
        self._last_detection_time = time.time()

    def get_frame_length(self) -> int:
        """Return the required audio frame length in samples.

        BUG FIX (Round 15): this used to always return
        `config.frame_length` (512 samples / 32ms @ 16kHz) regardless of
        which backend is active. The openwakeword backend, however,
        internally requires an 80ms (1280-sample) chunk per inference
        call -- an inherent requirement of that model, unrelated to
        config.frame_length. A caller that (reasonably) sizes its capture
        buffer to whatever this method returns would, on the openwakeword
        backend, hand `_detect_openwakeword()` a buffer shorter than its
        required chunk size; `range(0, len(audio) - chunk_size + 1,
        chunk_size)` is then empty, the model is never invoked, and
        `detect()` silently returns None on every single call forever --
        wake-word detection permanently and silently disabled, with
        nothing logged to explain why. This is a realistic failure mode:
        openwakeword is the second-priority backend (selected whenever
        it's installed and no Porcupine access key is configured -- a very
        plausible offline-first default), and a sibling module
        (speech/audio/pipeline.py) hardcodes a 512-sample ring-buffer frame
        size that would trigger exactly this. Fixed by making this
        backend-aware so callers who follow the documented contract get a
        size the active backend can actually use. See also the defensive
        warning log added in `_detect_openwakeword()` for callers that
        don't call this getter at all.
        """
        if self._backend == "openwakeword":
            return _OWW_CHUNK_SIZE
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
        # Pure-NumPy fallback - simplified MFCC approximation
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

    async def _detect_openwakeword(self, audio: np.ndarray, now: float) -> WakeWordDetection | None:
        """Detect with the openWakeWord models loaded for the wake words.

        Each model is named after its phrase, so the model that fired says
        which wake word was spoken; the Whisper guess at Guru or Maya that
        the MFCC fallback needs is not used here.
        """
        try:
            if self._oww_model is None:
                msg = "openWakeWord model not loaded"
                raise WakeWordError(msg)

            # openWakeWord expects 16kHz int16 audio in chunks
            audio_int16 = (audio * 32767).astype(np.int16)

            # Process in 80ms chunks (1280 samples at 16kHz)
            chunk_size = _OWW_CHUNK_SIZE
            best_name, max_score = "", 0.0
            n_chunks = 0
            for start in range(0, len(audio_int16) - chunk_size + 1, chunk_size):
                chunk = audio_int16[start : start + chunk_size]
                prediction = self._oww_model.predict(chunk)
                n_chunks += 1
                for name, score in prediction.items():
                    if score > max_score:
                        best_name, max_score = name, float(score)

            # BUG FIX (Round 15): if the caller handed us fewer samples than
            # one openWakeWord chunk, the loop above never executes and this
            # method silently returns None -- indistinguishable from "no
            # wake word present." That used to happen on every call whenever
            # a caller sized its buffers from get_frame_length()'s old,
            # backend-unaware value (or from a hardcoded 512-sample buffer
            # elsewhere, e.g. speech/audio/pipeline.py's ring buffer). Now
            # that get_frame_length() is backend-aware this should no
            # longer happen in practice, but this warning stays as a
            # diagnostic safety net for any caller that doesn't use it.
            if n_chunks == 0:
                logger.warning(
                    "openWakeWord: got %d samples but need >= %d (80ms @ %dHz) per "
                    "inference call -- no inference performed this call. Ensure the "
                    "caller sizes its audio buffer using get_frame_length(), which "
                    "now returns the openwakeword-specific chunk size while this "
                    "backend is active.",
                    len(audio_int16),
                    chunk_size,
                    self.config.sample_rate,
                )

            # Threshold: 0.5 is a good balance of sensitivity vs false positives
            threshold = max(0.3, 1.0 - self.config.sensitivity)
            phrase = self._oww_phrases.get(best_name)
            if phrase is not None and max_score >= threshold:
                personality = self.config.wake_words[phrase]
                self._last_detection_time = now
                detection = WakeWordDetection(
                    wake_word=phrase,
                    personality=personality,
                    confidence=max_score,
                    timestamp=now,
                    audio_chunk=audio,
                )
                logger.info(
                    "Wake word detected (openWakeWord): %s → %s (score=%.3f)",
                    phrase,
                    personality,
                    max_score,
                )
                return detection

        except Exception:
            logger.exception("openWakeWord error - falling back to MFCC")
            self._oww_model = None
            self._backend = "mfcc"
            return await self._detect_mfcc(audio, now)

        return None

    async def _detect_porcupine(self, audio: np.ndarray, now: float) -> WakeWordDetection | None:
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
        except Exception:
            logger.exception("Porcupine detection error - falling back to MFCC")
            return await self._detect_mfcc(audio, now)
        return None

    async def _detect_vosk(self, audio: np.ndarray, now: float) -> WakeWordDetection | None:
        """Detect using Vosk keyword spotting.

        BUG FIX (Round 15): the wake-word match used to be plain substring
        containment (`if phrase in text`) against the live Vosk transcript.
        With the default wake words being bare dictionary words ("guru",
        "maya" -- "maya" especially is a common name), this false-triggers
        on any utterance that merely *contains* the substring as part of a
        longer word or phrase (e.g. "gurudwara", "Maya's house", "the
        figure out"), not just the wake phrase itself spoken on its own.
        Fixed by matching on whole-word/phrase boundaries via regex
        (`\\b...\\b`), so a wake phrase must appear as its own word(s) in
        the transcript, not as a substring of an unrelated word.
        """
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
                if re.search(rf"\b{re.escape(phrase)}\b", text):
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
        except Exception:
            logger.exception("Vosk detection error - falling back to MFCC")
            return await self._detect_mfcc(audio, now)
        return None

    async def _detect_mfcc(self, audio: np.ndarray, now: float) -> WakeWordDetection | None:
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

        rms = float(np.sqrt(np.mean(audio**2)))
        peak = float(np.max(np.abs(audio)))
        threshold = self.config.energy_threshold * (1.0 - self.config.sensitivity * 0.5)

        # Periodic audio level logging - shows whether the mic is actually
        # capturing real audio.  Fires every ~30 frames (~45s at 1.5s chunks).
        if not hasattr(self, "_mfcc_frame_counter"):
            self._mfcc_frame_counter = 0
        self._mfcc_frame_counter += 1
        if self._mfcc_frame_counter % 30 == 1:
            logger.info(
                "Audio levels: rms=%.5f  peak=%.5f  threshold=%.4f  (peak_gate=%.4f)",
                rms, peak, threshold, threshold * 2.0,
            )

        # Require minimum audio duration (0.3s at 16kHz = 4800 samples)
        min_samples = int(self.config.sample_rate * 0.3)
        if len(audio) < min_samples:
            return None

        # Require peak to be at least 2x the threshold to avoid noise triggers
        # (music rejection provides additional false-positive protection)
        if peak < threshold * 2.0:
            return None

        # ── Music / speaker output rejection ─────────────────────────────
        # Music captured from speakers has high spectral flatness (many
        # frequency components active simultaneously) and low zero-crossing
        # variance compared to speech. Speech has bursty energy with clear
        # formant structure. We reject audio that looks like music.
        if self._looks_like_music(audio):
            logger.info("MFCC: rejected - audio looks like music/speaker output (rms=%.4f, peak=%.4f)", rms, peak)
            return None

        self._energy_buffer.append(rms)
        # deque(maxlen=10) auto-evicts oldest - no manual pop needed

        # 1 frame minimum - a single spoken word should trigger detection
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
                "Wake word detected (mfcc fallback): %s -> %s (rms=%.4f, peak=%.4f, threshold=%.4f)",
                phrase,
                personality,
                rms,
                peak,
                threshold,
            )
            return detection

        return None

    @staticmethod
    def _looks_like_music(audio: np.ndarray) -> bool:
        """Return True if *audio* looks like music/speaker output rather than speech.

        Uses two fast heuristics:
        1. Spectral flatness - music has many simultaneous frequency components
           (flatness close to 1.0). Speech has sparse formant structure (low flatness).
        2. Zero-crossing rate variance - speech has highly variable ZCR due to
           voiced/unvoiced transitions. Music has smoother, more periodic ZCR.

        Thresholds calibrated empirically:
        - Speech spectral flatness: typically 0.01 - 0.15
        - Music spectral flatness: typically 0.25 - 0.80
        - Speech ZCR std: typically 0.05 - 0.20
        - Music ZCR std: typically 0.01 - 0.06
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
            zcr_per_frame = np.array(
                [
                    float(
                        np.mean(
                            np.abs(
                                np.diff(np.sign(audio_f[i * frame_size : (i + 1) * frame_size])),
                            ),
                        )
                        / 2,
                    )
                    for i in range(n_frames)
                ],
            )
            zcr_std = float(np.std(zcr_per_frame))
        else:
            zcr_std = 1.0  # can't compute - assume speech

        # Music: high flatness AND low ZCR variance
        is_music = flatness > 0.20 and zcr_std < 0.08

        if is_music:
            logger.debug(
                "Music detection: flatness=%.3f zcr_std=%.3f → rejected",
                flatness,
                zcr_std,
            )

        return is_music

    def _match_phrase_by_spectrum(self, audio: np.ndarray) -> tuple[str, PersonalityType]:
        """Match audio to the most likely wake word phrase.

        Primary method: transcribe the audio with Whisper (fast, accurate).
        Fallback: spectral heuristic if Whisper is unavailable.

        Returns:
            Tuple of (matched_phrase, PersonalityType).

        """
        # ── Primary: transcribe with Whisper and check for keywords ──────
        try:
            transcript = self._transcribe_wake_word(audio)
            if transcript:
                result = self._match_transcript(transcript)
                if result is not None:
                    return result
                logger.debug(
                    "Wake word transcript %r - no keyword match, using spectral",
                    transcript,
                )
        except Exception as exc:
            logger.debug("Wake word transcription failed: %s - using spectral fallback", exc)

        # ── Fallback: spectral heuristic ──────────────────────────────────
        return self._match_spectral_fallback(audio)

    def _match_transcript(self, transcript: str) -> tuple[str, PersonalityType] | None:
        """Check transcript for wake word keywords."""
        t_lower = transcript.lower().strip()

        for personality_name, keywords in (
            ("maya", ("maya", "hey maya", "hi maya")),
            ("guru", ("guru", "hey guru", "hi guru")),
        ):
            if not any(kw in t_lower for kw in keywords):
                continue
            phrases = [
                p for p, pt in self.config.wake_words.items()
                if pt.value.lower() == personality_name
            ]
            if phrases:
                canonical = f"hey {personality_name}"
                phrase = canonical if canonical in phrases else phrases[0]
                logger.info("Wake word transcript: %r → %s", transcript, personality_name.upper())
                return phrase, self.config.wake_words[phrase]

        return None

    def _match_spectral_fallback(self, audio: np.ndarray) -> tuple[str, PersonalityType]:
        """Spectral heuristic fallback for wake word matching."""
        spectrum = np.abs(np.fft.rfft(audio.astype(np.float32))) ** 2
        n_bins = len(spectrum)
        mid = n_bins // 2

        low_power = float(np.mean(spectrum[:mid]) + 1e-10)
        high_power = float(np.mean(spectrum[mid:]) + 1e-10)
        high_ratio = high_power / (low_power + high_power)

        maya_phrases = [p for p, pt in self.config.wake_words.items() if pt.value.lower() == "maya"]
        guru_phrases = [p for p, pt in self.config.wake_words.items() if pt.value.lower() == "guru"]

        # Maya voices tend to have more high-frequency energy (threshold ~0.45)
        if maya_phrases and high_ratio >= 0.45:
            phrase = maya_phrases[0]
            return phrase, self.config.wake_words[phrase]

        if guru_phrases:
            phrase = guru_phrases[0]
            return phrase, self.config.wake_words[phrase]

        # Absolute fallback - should never reach here with default config
        first_phrase = next(iter(self.config.wake_words))
        return first_phrase, self.config.wake_words[first_phrase]

    def _transcribe_wake_word(self, audio: np.ndarray) -> str:
        """Transcribe wake word audio using faster-whisper (tiny model, fast).

        Uses the tiny Whisper model for speed - only needs to detect
        "guru" or "maya", not full sentences.

        Model loading priority:
        1. Use pre-warmed instance injected at startup (zero latency)
        2. Try GPU int8 (10x faster than CPU)
        3. Fall back to CPU float32

        Returns:
            Transcribed text, or empty string on failure.

        """
        try:
            from faster_whisper import WhisperModel

            # Use cached instance - injected at startup or loaded on first call
            if not hasattr(self, "_whisper_tiny") or self._whisper_tiny is None:
                from Agent_Guru.speech.stt.whisper_stt import cuda_trial, prepare_cuda_runtime

                def _load_tiny(device: str, compute_type: str) -> "WhisperModel":
                    try:
                        return WhisperModel("tiny", device=device, compute_type=compute_type, local_files_only=True)
                    except Exception:
                        return WhisperModel("tiny", device=device, compute_type=compute_type)

                # Was gated on torch.cuda.is_available() and trusted the CUDA
                # load. With a CUDA torch build but no CUDA 12 libraries (the
                # README's cu118 install), the load succeeded, and after any
                # earlier failed CUDA attempt in the process the first wake
                # transcription hung inside CTranslate2's encode(), measured.
                # It now goes through the same guard as every CUDA attempt: at
                # most one failure per process, proven by a trial transcription.
                if prepare_cuda_runtime():
                    try:
                        with cuda_trial():
                            model = _load_tiny("cuda", "int8")
                            silence = np.zeros(self.config.sample_rate // 2, dtype=np.float32)
                            list(model.transcribe(silence, language="en", beam_size=1)[0])
                        self._whisper_tiny = model
                        logger.info("Whisper tiny loaded for wake word detection on cuda (int8)")
                    except Exception as exc:
                        logger.info("Whisper tiny for wake words stays on the CPU: %s", exc)
                if getattr(self, "_whisper_tiny", None) is None:
                    self._whisper_tiny = _load_tiny("cpu", "float32")
                    logger.info("Whisper tiny loaded for wake word detection on cpu (float32)")

            segments, _ = self._whisper_tiny.transcribe(
                audio,
                language="en",
                beam_size=1,
                best_of=1,
                temperature=0.0,
                vad_filter=False,  # Don't filter - wake word audio is short
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
        """Release the Porcupine handle.

        Deliberately does no logging: a finalizer can run during interpreter
        shutdown, where the `import logging` this used to do raises
        ``ImportError: sys.meta_path is None``, turning a best-effort cleanup
        into noise on stderr at every exit.
        """
        porcupine = getattr(self, "_porcupine", None)
        if porcupine is None:
            return
        self._porcupine = None
        # contextlib.suppress rather than try/except/pass: a finalizer
        # must never raise, and this form says so without an inline
        # scanner suppression.
        with contextlib.suppress(Exception):
            porcupine.delete()
