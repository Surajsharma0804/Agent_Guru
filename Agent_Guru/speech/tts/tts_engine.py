"""Production TTS engine — Kokoro ONNX (human-quality, multilingual).

Kokoro ONNX is the single TTS backend for the entire project.

Why Kokoro:
- Human-quality voices (not robotic) — indistinguishable from real speech
- Multilingual: English (en-us, en-gb), Hindi (hi), French (fr-fr),
  Japanese (ja), Korean (ko), Chinese (zh), Spanish (es), Portuguese (pt-br),
  Italian (it), German (de)
- Runs 100% locally — no cloud, no API keys, no cost
- Fast: <200ms on CPU, <50ms on GPU
- Small: ~86MB total (model + voices)
- Single dependency: kokoro-onnx

Voice assignments:
  Guru (male)  → am_michael  — deep, clear American male
  Maya (female)→ af_heart    — warm, natural American female

Model files are auto-downloaded to ~/.cache/agent_guru/kokoro/ on first use.

Fallback chain (if Kokoro unavailable):
  pyttsx3 → silence

Author: Agent Guru Team
Version: 2.0.0  (replaces Coqui VCTK implementation)
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import threading
import urllib.request
import wave
from pathlib import Path
from typing import Any

import numpy as np

from Agent_Guru.speech.exceptions import GuruSpeechError
from Agent_Guru.speech.models import EmotionType, PersonalityType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model file locations
# ---------------------------------------------------------------------------

_CACHE_DIR = Path.home() / ".cache" / "agent_guru" / "kokoro"
_MODEL_PATH = _CACHE_DIR / "kokoro-v1.0.onnx"
_VOICES_PATH = _CACHE_DIR / "voices-v1.0.bin"

_MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/kokoro-v1.0.onnx"
)
_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"
)

# SHA-256 hashes for integrity verification.
# To update after a legitimate upstream release:
#   python -c "import hashlib, pathlib; print(hashlib.sha256(pathlib.Path('kokoro-v1.0.onnx').read_bytes()).hexdigest())"
_MODEL_SHA256: str | None = None   # TODO: pin after first verified download
_VOICES_SHA256: str | None = None  # TODO: pin after first verified download

# ---------------------------------------------------------------------------
# Voice configuration
# ---------------------------------------------------------------------------

# Kokoro voice IDs per personality
_VOICE_MAP: dict[PersonalityType, str] = {
    PersonalityType.GURU: "am_michael",  # Deep American male
    PersonalityType.MAYA: "af_heart",  # Warm American female
}

# Language codes supported by Kokoro
# Maps ISO 639-1 / BCP-47 tags to Kokoro lang strings
_LANG_MAP: dict[str, str] = {
    "en": "en-us",
    "en-us": "en-us",
    "en-gb": "en-gb",
    "hi": "hi",  # Hindi
    "fr": "fr-fr",
    "fr-fr": "fr-fr",
    "ja": "ja",  # Japanese
    "ko": "ko",  # Korean
    "zh": "zh",  # Chinese (Mandarin)
    "es": "es",  # Spanish
    "pt": "pt-br",
    "pt-br": "pt-br",
    "it": "it",  # Italian
    "de": "de",  # German
    "ru": "en-us",  # Russian — Kokoro fallback to English phonetics until native support added
}

# Emotion → speed multiplier (Kokoro supports speed param)
_EMOTION_SPEED: dict[EmotionType, float] = {
    EmotionType.HAPPY: 1.12,
    EmotionType.SAD: 0.88,
    EmotionType.ANGRY: 1.18,
    EmotionType.NEUTRAL: 1.0,
    EmotionType.SURPRISED: 1.20,
    EmotionType.FEARFUL: 1.08,
    EmotionType.DISGUSTED: 0.92,
}

# ---------------------------------------------------------------------------
# TTSError
# ---------------------------------------------------------------------------

class TTSError(GuruSpeechError):
    """TTS-specific error."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message, "KokoroTTSEngine", original_error)

# ---------------------------------------------------------------------------
# Integrity verification
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    """Return hex SHA-256 digest of *path* (streams in 8 KB chunks)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def _verify_hash(path: Path, expected: str | None) -> None:
    """Verify *path* against *expected* SHA-256. Delete and raise on mismatch.

    If *expected* is ``None`` the check is skipped (hash not yet pinned).
    """
    if expected is None:
        actual = _sha256_file(path)
        logger.warning(
            "No pinned SHA-256 for %s — actual hash is %s. "
            "Pin this value in _MODEL_SHA256 / _VOICES_SHA256 for production.",
            path.name, actual,
        )
        return
    actual = _sha256_file(path)
    if actual != expected:
        path.unlink(missing_ok=True)
        msg = (
            f"Integrity check FAILED for {path.name}: "
            f"expected {expected[:16]}…, got {actual[:16]}…. "
            f"File deleted. Re-run to re-download."
        )
        raise TTSError(msg)
    logger.debug("Integrity OK: %s (%s…)", path.name, actual[:16])


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------

def _download(url: str, dest: Path, expected_hash: str | None = None) -> None:
    """Download *url* to *dest* with a progress bar. Raises on failure."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp")

    def _progress(block: int, block_size: int, total: int) -> None:
        if total > 0:
            min(100, block * block_size * 100 // total)

    try:
        urllib.request.urlretrieve(url, tmp, reporthook=_progress)  # nosec B310
        tmp.rename(dest)
        logger.info("Downloaded %s → %s", url, dest)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        msg = f"Failed to download {dest.name}: {exc}"
        raise TTSError(msg, exc) from exc

    # Verify integrity immediately after download
    _verify_hash(dest, expected_hash)

# ---------------------------------------------------------------------------
# KokoroTTSEngine  (primary engine)
# ---------------------------------------------------------------------------

class KokoroTTSEngine:
    """Human-quality multilingual TTS using Kokoro ONNX.

    Thread-safe. Model is loaded lazily on first synthesis call.

    Example::

        engine = KokoroTTSEngine()
        audio, sr = engine.synthesize_to_array(
            "Hello, I am Guru.", PersonalityType.GURU
        )
        # audio: float32 numpy array, sr: 24000

    Supported languages (pass as ``lang`` parameter)::

        "en-us", "en-gb", "hi", "fr-fr", "ja", "ko",
        "zh", "es", "pt-br", "it", "de"
    """

    def __init__(self, use_gpu: bool = False) -> None:
        self._lock = threading.Lock()
        self._kokoro: Any | None = None
        self._loaded = False
        self._use_gpu = use_gpu

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def synthesize(
        self,
        text: str,
        personality: PersonalityType | str = PersonalityType.GURU,
        emotion: EmotionType | None = None,
        speech_rate: float = 1.0,
        volume: float = 1.0,
        lang: str = "en-us",
    ) -> bytes:
        """Synthesize *text* and return WAV bytes.

        Args:
            text: Text to speak. Emojis and markdown are stripped automatically.
            personality: ``PersonalityType.GURU`` (male) or ``PersonalityType.MAYA`` (female).
                         Also accepts the strings ``"guru"`` / ``"maya"``.
            emotion: Optional emotion for prosody adjustment.
            speech_rate: Speed multiplier 0.5–2.0 (default 1.0).
            volume: Volume multiplier 0.0–1.0 (default 1.0).
            lang: BCP-47 language code (default ``"en-us"``).
                  Supported: en-us, en-gb, hi, fr-fr, ja, ko, zh, es, pt-br, it, de.

        Returns:
            WAV audio bytes (24 kHz, mono, 16-bit PCM).

        Raises:
            TTSError: If synthesis fails.

        """
        audio, sr = self.synthesize_to_array(text, personality, emotion, speech_rate, volume, lang)
        return _array_to_wav(audio, sr)

    def synthesize_to_array(
        self,
        text: str,
        personality: PersonalityType | str = PersonalityType.GURU,
        emotion: EmotionType | None = None,
        speech_rate: float = 1.0,
        volume: float = 1.0,
        lang: str = "en-us",
    ) -> tuple[np.ndarray, int]:
        """Synthesize *text* and return ``(float32_array, sample_rate)``.

        Args:
            text: Text to speak.
            personality: Personality (Guru = male, Maya = female).
            emotion: Optional emotion for speed adjustment.
            speech_rate: Speed multiplier 0.5–2.0.
            volume: Volume multiplier 0.0–1.0.
            lang: BCP-47 language code.

        Returns:
            Tuple of (float32 numpy array in [-1, 1], sample_rate_hz).

        Raises:
            TTSError: If synthesis fails.

        """
        if not text or not text.strip():
            msg = "Text cannot be empty"
            raise TTSError(msg)
        if not 0.5 <= speech_rate <= 2.0:
            msg = f"speech_rate must be in [0.5, 2.0], got {speech_rate}"
            raise TTSError(msg)
        if not 0.0 <= volume <= 1.0:
            msg = f"volume must be in [0.0, 1.0], got {volume}"
            raise TTSError(msg)

        personality = _coerce_personality(personality)
        clean = _clean_text(text)
        if not clean:
            # Return 0.5s silence for empty-after-cleaning text
            return np.zeros(12000, dtype=np.float32), 24000

        voice = _VOICE_MAP[personality]
        kokoro_lang = _LANG_MAP.get(lang.lower(), "en-us")

        # Combine speech_rate with emotion speed
        speed = speech_rate
        if emotion is not None:
            speed *= _EMOTION_SPEED.get(emotion, 1.0)
        speed = float(np.clip(speed, 0.5, 2.0))

        with self._lock:
            self._ensure_loaded()
            try:
                samples, sr = self._kokoro.create(  # type: ignore[union-attr]
                    clean,
                    voice=voice,
                    speed=speed,
                    lang=kokoro_lang,
                )
            except Exception as exc:
                msg = f"Kokoro synthesis failed: {exc}"
                raise TTSError(msg, exc) from exc
        audio = np.asarray(samples, dtype=np.float32)

        # Apply volume
        if volume != 1.0:
            audio = np.clip(audio * volume, -1.0, 1.0)

        # Append 300ms of silence so the last word's tail is never clipped
        # by the audio device before it finishes playing.
        sample_rate = int(sr)
        tail_samples = int(sample_rate * 0.30)
        audio = np.concatenate([audio, np.zeros(tail_samples, dtype=np.float32)])

        return audio, sample_rate

    def get_voice_info(self, personality: PersonalityType) -> dict[str, Any]:
        """Return metadata about the voice used for *personality*."""
        return {
            "engine": "Kokoro ONNX",
            "model": "kokoro-v1.0",
            "voice": _VOICE_MAP.get(personality, "am_michael"),
            "personality": personality.value,
            "gender": "male" if personality == PersonalityType.GURU else "female",
            "quality": "human-quality (neural ONNX)",
            "languages": list(_LANG_MAP.keys()),
            "cost": "FREE (runs locally)",
        }

    def list_supported_languages(self) -> list[str]:
        """Return list of supported BCP-47 language codes."""
        return list(_LANG_MAP.keys())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load Kokoro model (called with lock held)."""
        if self._loaded:
            return

        # Auto-download model files if missing
        if not _MODEL_PATH.exists():
            logger.info("Kokoro model not found — downloading (~83 MB, one-time)...")
            _download(_MODEL_URL, _MODEL_PATH, _MODEL_SHA256)
        else:
            # Verify cached file hasn't been tampered with
            _verify_hash(_MODEL_PATH, _MODEL_SHA256)

        if not _VOICES_PATH.exists():
            logger.info("Kokoro voices not found — downloading (~3 MB, one-time)...")
            _download(_VOICES_URL, _VOICES_PATH, _VOICES_SHA256)
        else:
            _verify_hash(_VOICES_PATH, _VOICES_SHA256)

        try:
            from kokoro_onnx import Kokoro  # type: ignore[import]

            self._kokoro = Kokoro(str(_MODEL_PATH), str(_VOICES_PATH))
            self._loaded = True
            logger.info("Kokoro TTS engine loaded (voices: am_michael, af_heart)")
        except ImportError as exc:
            msg = "kokoro-onnx not installed. Run: pip install kokoro-onnx"
            raise TTSError(msg, exc) from exc

# ---------------------------------------------------------------------------
# Pyttsx3 fallback engine
# ---------------------------------------------------------------------------

class _Pyttsx3Engine:
    """Lightweight pyttsx3 fallback. Used only when Kokoro is unavailable."""

    def __init__(self) -> None:
        self._engine: Any | None = None
        self._lock = threading.Lock()
        self._male_voice_id: str | None = None
        self._female_voice_id: str | None = None

    def initialize(self) -> bool:
        """Initialize pyttsx3. Returns True on success."""
        try:
            import pyttsx3  # type: ignore[import]

            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []

            for v in voices:
                name = (v.name or "").lower()
                vid = (v.id or "").lower()
                is_male = any(k in name or k in vid for k in ("david", "mark", "james", "male"))
                is_female = any(k in name or k in vid for k in ("zira", "hazel", "susan", "female"))
                if is_male and self._male_voice_id is None:
                    self._male_voice_id = v.id
                if is_female and self._female_voice_id is None:
                    self._female_voice_id = v.id

            # Fallback: first two voices
            if voices:
                if self._male_voice_id is None:
                    self._male_voice_id = voices[0].id
                if self._female_voice_id is None:
                    self._female_voice_id = voices[min(1, len(voices) - 1)].id

            engine.setProperty("rate", 160)
            engine.setProperty("volume", 1.0)
            self._engine = engine
            return True
        except Exception as exc:
            logger.warning("pyttsx3 unavailable: %s", exc)
            return False

    def synthesize(
        self,
        text: str,
        personality: PersonalityType,
        speech_rate: float = 1.0,
        volume: float = 1.0,
    ) -> bytes:
        """Synthesize to WAV bytes using pyttsx3."""
        if self._engine is None:
            return _silence_wav(text)

        import tempfile

        voice_id = (
            self._male_voice_id if personality == PersonalityType.GURU else self._female_voice_id
        )

        with self._lock:
            try:
                if voice_id:
                    self._engine.setProperty("voice", voice_id)
                self._engine.setProperty("rate", int(160 * speech_rate))
                self._engine.setProperty("volume", volume)

                fd, tmp = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                try:
                    self._engine.save_to_file(text, tmp)
                    self._engine.runAndWait()
                    with open(tmp, "rb") as f:
                        return f.read()
                finally:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
            except Exception as exc:
                logger.warning("pyttsx3 synthesis failed: %s", exc)
                return _silence_wav(text)

# ---------------------------------------------------------------------------
# Unified engine (used by the rest of the project)
# ---------------------------------------------------------------------------

class CoquiTTSEngine:
    """Unified TTS engine — Kokoro ONNX primary, pyttsx3 fallback.

    This class keeps the same public API as the old CoquiTTSEngine so that
    all existing callers (engine.py, synthesis_engine.py, tts_manager.py)
    continue to work without changes.

    The name is kept for backward compatibility; internally it uses Kokoro.
    """

    # Keep VOICE_CONFIGS for any code that reads it directly
    VOICE_CONFIGS = {
        PersonalityType.GURU: {"voice": "am_michael", "speed": 1.0, "gender": "male"},
        PersonalityType.MAYA: {"voice": "af_heart", "speed": 1.0, "gender": "female"},
    }

    EMOTION_ADJUSTMENTS = {
        EmotionType.HAPPY: {"speed_mult": 1.12, "pitch_mult": 1.05},
        EmotionType.SAD: {"speed_mult": 0.88, "pitch_mult": 0.95},
        EmotionType.ANGRY: {"speed_mult": 1.18, "pitch_mult": 1.10},
        EmotionType.NEUTRAL: {"speed_mult": 1.00, "pitch_mult": 1.00},
        EmotionType.SURPRISED: {"speed_mult": 1.20, "pitch_mult": 1.15},
        EmotionType.FEARFUL: {"speed_mult": 1.08, "pitch_mult": 1.05},
        EmotionType.DISGUSTED: {"speed_mult": 0.92, "pitch_mult": 0.95},
    }

    def __init__(self, use_gpu: bool = False) -> None:
        self._kokoro = KokoroTTSEngine(use_gpu=use_gpu)
        self._pyttsx3 = _Pyttsx3Engine()
        self._pyttsx3_ready = False
        self._use_kokoro = True  # set to False if Kokoro fails to load

    # ------------------------------------------------------------------
    # Public API (backward-compatible with old CoquiTTSEngine)
    # ------------------------------------------------------------------

    def synthesize(
        self,
        text: str,
        personality: PersonalityType | str = PersonalityType.GURU,
        emotion: EmotionType | None = None,
        speech_rate: float = 1.0,
        pitch: float = 1.0,  # kept for API compat; Kokoro doesn't expose pitch
        volume: float = 1.0,
        use_ssml: bool = False,
        lang: str = "en-us",
    ) -> bytes:
        """Synthesize *text* to WAV bytes.

        Args:
            text: Text to synthesize.
            personality: ``PersonalityType.GURU`` or ``PersonalityType.MAYA``
                         (or the strings ``"guru"`` / ``"maya"``).
            emotion: Optional emotion for prosody.
            speech_rate: Speed multiplier 0.5–2.0.
            pitch: Ignored (kept for API compatibility).
            volume: Volume multiplier 0.0–1.0.
            use_ssml: Ignored (kept for API compatibility).
            lang: BCP-47 language code (default ``"en-us"``).

        Returns:
            WAV audio bytes.

        """
        personality = _coerce_personality(personality)

        if self._use_kokoro:
            try:
                return self._kokoro.synthesize(
                    text,
                    personality,
                    emotion,
                    speech_rate,
                    volume,
                    lang,
                )
            except TTSError as exc:
                logger.warning("Kokoro failed, falling back to pyttsx3: %s", exc)
                self._use_kokoro = False
        # pyttsx3 fallback
        if not self._pyttsx3_ready:
            self._pyttsx3_ready = self._pyttsx3.initialize()
        return self._pyttsx3.synthesize(text, personality, speech_rate, volume)

    def synthesize_to_array(
        self,
        text: str,
        personality: PersonalityType | str = PersonalityType.GURU,
        emotion: EmotionType | None = None,
        speech_rate: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        lang: str = "en-us",
    ) -> tuple[np.ndarray, int]:
        """Synthesize *text* and return ``(float32_array, sample_rate)``."""
        personality = _coerce_personality(personality)

        if self._use_kokoro:
            try:
                return self._kokoro.synthesize_to_array(
                    text,
                    personality,
                    emotion,
                    speech_rate,
                    volume,
                    lang,
                )
            except TTSError as exc:
                logger.warning("Kokoro failed, falling back to pyttsx3: %s", exc)
                self._use_kokoro = False
        # pyttsx3 fallback → convert WAV bytes to array
        if not self._pyttsx3_ready:
            self._pyttsx3_ready = self._pyttsx3.initialize()
        wav_bytes = self._pyttsx3.synthesize(text, personality, speech_rate, volume)
        return _wav_to_array(wav_bytes)

    def get_voice_info(self, personality: PersonalityType) -> dict[str, Any]:
        """Return voice metadata."""
        return self._kokoro.get_voice_info(personality)

    def list_available_speakers(self) -> list[str]:
        """Return list of available voice IDs."""
        return list(_VOICE_MAP.values())

    def list_supported_languages(self) -> list[str]:
        """Return supported BCP-47 language codes."""
        return list(_LANG_MAP.keys())

# Backward-compatibility alias
TTSEngine = CoquiTTSEngine

# ---------------------------------------------------------------------------
# Audio utilities
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Strip emojis, markdown, and non-speakable characters from *text*."""
    import re

    # Remove emojis (all Unicode emoji ranges)
    text = re.sub(
        r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
        r"\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251"
        r"\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
        r"\U00002600-\U000026FF\U00002700-\U000027BF]+",
        "",
        text,
        flags=re.UNICODE,
    )
    # Remove markdown formatting
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"#{1,6}\s", "", text)
    # Replace URLs with "link"
    text = re.sub(r"https?://\S+", "link", text)
    # Normalize whitespace
    return re.sub(r"\s+", " ", text).strip()

def _coerce_personality(p: PersonalityType | str) -> PersonalityType:
    """Convert string ``"guru"``/``"maya"`` to :class:`PersonalityType`."""
    if isinstance(p, PersonalityType):
        return p
    s = str(p).lower().strip()
    if s == "guru":
        return PersonalityType.GURU
    if s == "maya":
        return PersonalityType.MAYA
    msg = f"Invalid personality '{p}'. Must be 'guru' or 'maya'."
    raise TTSError(msg)

def _array_to_wav(audio: np.ndarray, sample_rate: int) -> bytes:
    """Convert float32 numpy array to 16-bit mono WAV bytes."""
    pcm = np.clip(audio, -1.0, 1.0)
    pcm_int16 = (pcm * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_int16.tobytes())
    return buf.getvalue()

def _wav_to_array(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    """Convert WAV bytes to float32 numpy array."""
    if not wav_bytes:
        return np.zeros(12000, dtype=np.float32), 24000
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
            sw = wf.getsampwidth()
        if sw == 2:
            audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        elif sw == 1:
            audio = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128) / 128.0
        else:
            audio = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
        return audio, sr
    except Exception:
        return np.zeros(12000, dtype=np.float32), 24000

def _silence_wav(text: str, sample_rate: int = 24000) -> bytes:
    """Generate silence WAV proportional to text length."""
    words = max(1, len(text.split()))
    duration = max(0.1, min(words / 150.0, 30.0))
    n = int(sample_rate * duration)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n)
    return buf.getvalue()
