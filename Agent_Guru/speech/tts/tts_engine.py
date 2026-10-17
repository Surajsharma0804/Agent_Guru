"""Production TTS engine - Kokoro ONNX (human-quality, multilingual).

Kokoro ONNX is the single TTS backend for the entire project.

Why Kokoro:
- Human-quality voices (not robotic) - indistinguishable from real speech
- Multilingual: English (en-us, en-gb), Hindi (hi), French (fr-fr),
  Japanese (ja), Korean (ko), Chinese (zh), Spanish (es), Portuguese (pt-br),
  Italian (it), German (de)
- Runs 100% locally - no cloud, no API keys, no cost
- Fast: <200ms on CPU, <50ms on GPU
- Small: ~86MB total (model + voices)
- Single dependency: kokoro-onnx

Voice assignments:
  Guru (male)  → am_michael  - deep, clear American male
  Maya (female)→ af_heart    - warm, natural American female

Model files are auto-downloaded to ~/.cache/agent_guru/kokoro/ on first use.

Fallback chain (if Kokoro unavailable):
  pyttsx3 → silence

Author: Agent Guru Team
Version: 2.0.0  (replaces Coqui VCTK implementation)
"""

from __future__ import annotations

import io
import logging
import os
import re
import sys
import threading
import wave
from pathlib import Path
from typing import Any

import numpy as np

from Agent_Guru.speech.exceptions import GuruSpeechError
from Agent_Guru.speech.models import EmotionType, PersonalityType
from Agent_Guru.utils.verified_files import PinnedFile

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

# The two files, pinned. The GitHub release has no published checksum (its
# assets predate GitHub's per-asset digests), so the anchor is a second,
# independent publication of the same files: Hugging Face's upload-time
# SHA-256 for fastrtc/kokoro-onnx at revision 8d07950c9b6c87ce6809e9bba7bd494336217c2a
# (same names, same byte sizes as the release). Copies fetched from the
# GitHub release on 2026-09-30 hash to the same values. Before, both hashes
# were None and any bytes that arrived were loaded.
KOKORO_PINS: tuple[PinnedFile, ...] = (
    PinnedFile("kokoro-v1.0.onnx", 325532387, "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5"),
    PinnedFile("voices-v1.0.bin", 28214398, "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d"),
)
_PINS_BY_NAME = {pin.name: pin for pin in KOKORO_PINS}

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
    "ru": "en-us",  # Russian - Kokoro fallback to English phonetics until native support added
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

def verify_kokoro_files(directory: Path | None = None) -> None:
    """Raise TTSError unless the two Kokoro files in *directory* are the pinned ones.

    A full hash runs the first time and after any change; otherwise the
    stamp from the last check is enough, so a normal start does not
    re-hash 354 MB and works offline.
    """
    from Agent_Guru.utils.verified_files import VerificationError, ensure_verified

    try:
        ensure_verified(directory or _CACHE_DIR, KOKORO_PINS)
    except VerificationError as exc:
        msg = f"Kokoro model files failed verification: {exc}"
        raise TTSError(msg, exc) from exc


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------

# Per-read socket timeout for model downloads. urllib has NO default socket
# timeout, so a connection that stalls mid-transfer blocks forever - and this
# download happens lazily on the FIRST synthesis, i.e. inside a user-facing
# voice turn. An assistant that goes silent indefinitely because a CDN stopped
# sending bytes is a worse failure than one that reports a download error.
_DOWNLOAD_TIMEOUT_S = 30.0
_DOWNLOAD_CHUNK = 1 << 20  # 1 MiB

# Set AGENT_GURU_NO_DOWNLOAD=1 to make a missing model an immediate, explicit
# error instead of an 83 MB fetch. Agent_Guru is an offline-first product, and
# this is also what keeps an automated test run from pulling model weights off
# the network on a machine that has never had them.
_NO_DOWNLOAD_ENV = "AGENT_GURU_NO_DOWNLOAD"


def _kokoro_package_installed() -> bool:
    """True if kokoro-onnx can be imported, checked without importing it."""
    import importlib.util
    import sys

    if "kokoro_onnx" in sys.modules:
        return sys.modules["kokoro_onnx"] is not None
    try:
        return importlib.util.find_spec("kokoro_onnx") is not None
    except (ImportError, ValueError):
        return False


def downloads_disabled() -> bool:
    """Return True when model auto-download has been switched off."""
    return os.environ.get(_NO_DOWNLOAD_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _download(url: str, dest: Path) -> None:
    """Download *url* to *dest*, verified against its pin before it gets its real name; raises TTSError."""
    from Agent_Guru.utils.verified_files import VerificationError, download

    if downloads_disabled():
        msg = (
            f"{dest.name} is missing and {_NO_DOWNLOAD_ENV} is set, so it will "
            f"not be downloaded. Fetch it once from {url} into {dest.parent} "
            f"or unset {_NO_DOWNLOAD_ENV}."
        )
        raise TTSError(msg)
    last = {"step": -1}

    def progress(name: str, done: int, size: int) -> None:
        step = done * 10 // size
        if step != last["step"]:
            last["step"] = step
            logger.info("Downloading %s: %d%%", name, step * 10)

    try:
        download(url, dest, _PINS_BY_NAME[dest.name], timeout=_DOWNLOAD_TIMEOUT_S, progress=progress)
    except VerificationError as exc:
        raise TTSError(str(exc), exc) from exc
    except OSError as exc:
        msg = f"Failed to download {dest.name}: {exc}"
        raise TTSError(msg, exc) from exc
    logger.info("Downloaded and verified %s", dest)


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
        #: Where synthesis actually runs, "cuda" or "cpu", known once the model
        #: is loaded. use_gpu is a request; this is what was granted.
        self.device: str | None = None

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
            speech_rate: Speed multiplier 0.5-2.0 (default 1.0).
            volume: Volume multiplier 0.0-1.0 (default 1.0).
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
            speech_rate: Speed multiplier 0.5-2.0.
            volume: Volume multiplier 0.0-1.0.
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

        # Fetch what is missing, replace what fails its pin (only ever with a
        # verified download), then load nothing that is not the pinned file.
        from Agent_Guru.utils.verified_files import problems, stamp_matches

        # The folder checked is the folder the files are loaded from. It was
        # _CACHE_DIR, so with the paths pointed elsewhere the real cache was
        # checked while other files were loaded, unverified.
        directory = _MODEL_PATH.parent
        if _VOICES_PATH.parent != directory:
            msg = f"Kokoro model and voices must be in one folder, not {directory} and {_VOICES_PATH.parent}"
            raise TTSError(msg)
        if not stamp_matches(directory, KOKORO_PINS):
            for url, path in ((_MODEL_URL, _MODEL_PATH), (_VOICES_URL, _VOICES_PATH)):
                found = problems(path, _PINS_BY_NAME[path.name])
                if found:
                    logger.warning("Kokoro: %s; fetching the pinned file", found)
                    _download(url, path)
        verify_kokoro_files(directory)

        try:
            from kokoro_onnx import Kokoro
        except ImportError as exc:
            msg = "kokoro-onnx not installed. Run: pip install kokoro-onnx"
            raise TTSError(msg, exc) from exc

        # The session is built here, with explicit providers, instead of by
        # Kokoro(model, voices). use_gpu used to be stored and never read, so
        # asking for the GPU did nothing; and Kokoro() on its own switches to
        # every provider onnxruntime offers whenever onnxruntime-gpu happens to
        # be installed, so use_gpu=False did not mean CPU either.
        import onnxruntime as ort

        session = ort.InferenceSession(str(_MODEL_PATH), providers=self._providers(ort))
        self._kokoro = Kokoro.from_session(session, str(_VOICES_PATH))
        self.device = "cuda" if session.get_providers()[0] == "CUDAExecutionProvider" else "cpu"
        self._loaded = True
        logger.info(
            "Kokoro TTS engine loaded on %s (voices: am_michael, af_heart)", self.device.upper(),
        )

    def _providers(self, ort: Any) -> list[str]:
        """ONNX Runtime providers for the Kokoro session.

        Measured on an RTX 2050 (4 GB) with gemma3:4b resident in Ollama:
        CUDA synthesised a short answer in 0.76 s against 1.43 s on the CPU,
        and 13.7 s of speech in 1.4 s against 6.0 s, with Ollama still fully
        on the GPU at the same speed. The session takes about 1.1 GB of VRAM,
        which left 170 MiB free on that card. DirectML could not run the
        model at all: its ConvTranspose node fails with "The parameter is
        incorrect".
        """
        if not self._use_gpu:
            return ["CPUExecutionProvider"]
        if "CUDAExecutionProvider" not in ort.get_available_providers():
            logger.warning(
                "GPU speech synthesis was requested, but the installed onnxruntime is "
                "the CPU-only build, so speech is synthesised on the CPU (measured about "
                "2x slower to start speaking on an RTX 2050). Replacing onnxruntime with "
                "onnxruntime-gpu[cuda,cudnn] (about 1.7 GB, NVIDIA only) enables it.",
            )
            return ["CPUExecutionProvider"]
        # onnxruntime-gpu[cuda,cudnn] installs CUDA and cuDNN as pip packages;
        # their DLLs are only found once they have been preloaded.
        preload = getattr(ort, "preload_dlls", None)
        if preload is not None:
            try:
                preload()
            except Exception:
                logger.warning("Could not preload the CUDA libraries", exc_info=True)
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]

# ---------------------------------------------------------------------------
# Pyttsx3 fallback engine
# ---------------------------------------------------------------------------

def _espeak_data_for_loaded_library(platform: str | None = None, maps: str | None = None) -> str | None:
    """espeakng-loader's data directory, when pyttsx3 is about to use its eSpeak library; else None.

    On Linux pyttsx3 speaks through eSpeak NG: it dlopens libespeak-ng.so.1
    and calls espeak_Initialize with no data path and no
    espeakINITIALIZE_DONT_EXIT. When Kokoro has run, its phonemizer has
    already loaded espeakng-loader's copy of that library, so dlopen returns
    it, and that copy looks for its data under the path it was built at
    (D:/a/espeakng-loader/... or the Linux equivalent). It does not find
    it, and eSpeak NG calls exit(1): the whole process ends with no
    traceback. That ended every CI test run at 95 % and would end the
    assistant whenever Kokoro failed and it fell back to pyttsx3.

    Only when that copy is already mapped into this process: a system eSpeak
    NG with its own data must not be pointed at another version's data.
    """
    platform = platform or sys.platform
    if not platform.startswith("linux") or os.environ.get("ESPEAK_DATA_PATH"):
        return None
    try:
        import espeakng_loader

        library = os.path.realpath(espeakng_loader.get_library_path())
        if maps is None:
            with open("/proc/self/maps", encoding="utf-8", errors="replace") as fh:
                maps = fh.read()
    except (ImportError, OSError):
        return None
    return espeakng_loader.get_data_path() if library in maps else None


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
            import pyttsx3

            data = _espeak_data_for_loaded_library()
            if data:
                os.environ["ESPEAK_DATA_PATH"] = data
            engine = pyttsx3.init()
            voices: list[Any] = engine.getProperty("voices") or []

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

        import subprocess  # nosec B404
        import sys
        import tempfile

        voice_id = (
            self._male_voice_id if personality == PersonalityType.GURU else self._female_voice_id
        )
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        # Each sentence is synthesised in a short-lived process. In-process,
        # pyttsx3 2.99's SAPI5 driver returned from save_to_file + runAndWait
        # once and then blocked for ever in startLoop on the next call
        # (reproduced on Windows 11: the second call never returned, with
        # the same engine, a new engine, stop() or endLoop()); the speaking
        # thread froze, and on CI pytest-timeout ended the whole run. A fresh
        # process per call finished 4 calls of 4 at about 0.6 s each, and a
        # stalled one is killed at its deadline instead of hanging.
        deadline = _PYTTSX3_BASE_TIMEOUT_S + len(text) / _PYTTSX3_CHARS_PER_S
        args = [sys.executable, "-c", _PYTTSX3_SCRIPT, tmp, voice_id or "", str(int(160 * speech_rate)), str(volume)]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            with self._lock:
                done = subprocess.run(  # nosec B603 - fixed script, no shell, text passed on stdin
                    args, input=text.encode("utf-8"), capture_output=True, timeout=deadline,
                    creationflags=flags, check=False,
                )
            if done.returncode != 0 or os.path.getsize(tmp) == 0:
                logger.warning("pyttsx3 synthesis failed (exit %s): %s", done.returncode,
                               done.stderr.decode("utf-8", "replace")[-300:])
                return _silence_wav(text)
            with open(tmp, "rb") as f:
                return f.read()
        except subprocess.TimeoutExpired:
            logger.warning("pyttsx3 synthesis gave no audio within %.0f s; the process was ended", deadline)
            return _silence_wav(text)
        except Exception as exc:
            logger.warning("pyttsx3 synthesis failed: %s", exc)
            return _silence_wav(text)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


#: The child process's whole job: read the text on stdin, write one WAV file.
_PYTTSX3_SCRIPT = """
import sys
import pyttsx3
path, voice, rate, volume = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
text = sys.stdin.buffer.read().decode("utf-8")
engine = pyttsx3.init()
if voice:
    engine.setProperty("voice", voice)
engine.setProperty("rate", rate)
engine.setProperty("volume", volume)
engine.save_to_file(text, path)
engine.runAndWait()
"""
#: A call is ended after this long plus one second per this many characters.
_PYTTSX3_BASE_TIMEOUT_S = 15.0
_PYTTSX3_CHARS_PER_S = 20.0

# ---------------------------------------------------------------------------
# Unified engine (used by the rest of the project)
# ---------------------------------------------------------------------------

class CoquiTTSEngine:
    """Unified TTS engine - Kokoro ONNX primary, pyttsx3 fallback.

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

    # Documented parameter ranges, enforced by _validate_request(). These are
    # the bounds the public docstrings already advertised while NOTHING in the
    # engine checked them: speech_rate=10.0 reached pyttsx3 as
    # setProperty("rate", 1600) and Kokoro as a 10x speed factor, and
    # volume=5.0 was passed straight through - both producing unusable audio
    # from a call that reported success.
    MIN_SPEECH_RATE = 0.5
    MAX_SPEECH_RATE = 2.0
    MIN_VOLUME = 0.0
    MAX_VOLUME = 1.0

    def __init__(self, use_gpu: bool = False) -> None:
        self._kokoro = KokoroTTSEngine(use_gpu=use_gpu)
        self._pyttsx3 = _Pyttsx3Engine()
        self._pyttsx3_ready = False
        self._use_kokoro = True  # set to False if Kokoro fails to load

    @property
    def active_backend(self) -> str:
        """Which synthesis backend will actually produce audio.

        Returns ``"kokoro"``, ``"pyttsx3"`` or ``"none"``. With ``"none"`` the
        engine still returns a well-formed WAV, but it is SILENCE from
        _silence_wav() - useful so a caller's audio pipeline keeps working on
        a machine with no TTS available, and important to be able to detect,
        because no assertion about audio CONTENT is meaningful in that state.
        """
        if self._use_kokoro and (
            getattr(self._kokoro, "_loaded", False)
            or (
                _kokoro_package_installed()
                and _MODEL_PATH.exists()
                and _VOICES_PATH.exists()
            )
        ):
            # Reports availability from what is already on disk - it must not
            # itself trigger the 326 MB model download. It used to look at the
            # model files only, so with kokoro-onnx not installed it still said
            # "kokoro" while every call fell back to pyttsx3 or silence, which
            # is exactly the degradation a caller asks this in order to detect.
            return "kokoro"
        if not self._pyttsx3_ready:
            self._pyttsx3_ready = self._pyttsx3.initialize()
        if getattr(self._pyttsx3, "_engine", None) is not None:
            return "pyttsx3"
        return "none"

    def _validate_request(self, text: str, speech_rate: float, volume: float) -> None:
        """Reject requests no backend could honour.

        Validation happens here, before any backend is consulted, so the
        failure is the same whether Kokoro, pyttsx3 or neither is installed.
        TTSError is what every public synthesis docstring already documents.
        """
        if not isinstance(text, str) or not text.strip():
            msg = "Cannot synthesize empty or whitespace-only text"
            raise TTSError(msg)
        if not self.MIN_SPEECH_RATE <= speech_rate <= self.MAX_SPEECH_RATE:
            msg = (
                f"speech_rate must be in "
                f"[{self.MIN_SPEECH_RATE}, {self.MAX_SPEECH_RATE}], got {speech_rate}"
            )
            raise TTSError(msg)
        if not self.MIN_VOLUME <= volume <= self.MAX_VOLUME:
            msg = f"volume must be in [{self.MIN_VOLUME}, {self.MAX_VOLUME}], got {volume}"
            raise TTSError(msg)

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
            speech_rate: Speed multiplier 0.5-2.0.
            pitch: Ignored (kept for API compatibility).
            volume: Volume multiplier 0.0-1.0.
            use_ssml: Ignored (kept for API compatibility).
            lang: BCP-47 language code (default ``"en-us"``).

        Returns:
            WAV audio bytes.

        Raises:
            TTSError: If *text* is blank, or speech_rate/volume are outside
                their documented ranges, or synthesis fails.

        """
        self._validate_request(text, speech_rate, volume)
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
        self._validate_request(text, speech_rate, volume)
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

# Pre-compiled once at import instead of on every _clean_text() call.
# _clean_text runs on the TTS hot path (every utterance) and used to do a
# function-level `import re` plus six re.sub() calls with literal patterns.
# re.sub caches compiled patterns, but only after hashing the pattern string
# and taking a lock on every call; the emoji pattern alone is ~200 characters.
# Compiling them once removes that per-utterance work entirely.
# Measured on a ~430-character utterance, 20k iterations: 46.46 us -> 41.53 us
# per call (1.12x), with the output asserted identical to the old function.
_EMOJI_RE = re.compile(
    "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251"
    "\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF\U00002700-\U000027BF]+",
    flags=re.UNICODE,
)
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC_RE = re.compile(r"\*(.+?)\*")
_MD_CODE_RE = re.compile(r"`(.+?)`")
_MD_HEADING_RE = re.compile(r"#{1,6}\s")
_URL_RE = re.compile(r"https?://\S+")
_WHITESPACE_RE = re.compile(r"\s+")


def _clean_text(text: str) -> str:
    """Strip emojis, markdown, and non-speakable characters from *text*."""
    text = _EMOJI_RE.sub("", text)
    # Remove markdown formatting
    text = _MD_BOLD_RE.sub(r"\1", text)
    text = _MD_ITALIC_RE.sub(r"\1", text)
    text = _MD_CODE_RE.sub(r"\1", text)
    text = _MD_HEADING_RE.sub("", text)
    # Replace URLs with "link"
    text = _URL_RE.sub("link", text)
    # Normalize whitespace
    return _WHITESPACE_RE.sub(" ", text).strip()

def _coerce_personality(p: PersonalityType | str) -> PersonalityType:
    """Convert string ``"guru"``/``"maya"`` to :class:`PersonalityType`."""
    if isinstance(p, PersonalityType):
        return p
    s = p.lower().strip()
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
