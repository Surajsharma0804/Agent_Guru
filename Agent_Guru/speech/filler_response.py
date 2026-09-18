"""Pre-cached filler audio for instant acknowledgement on wake-word detection.

Plays a short filler ("haan bol", "yeah?", etc.) in the natural pause after
the user says the wake word, before they start their actual command. This is
the same slot where Alexa/Google put their listening chime — it makes the
assistant feel present instead of laggy.

Design:
    - Fillers are pre-synthesized once (Kokoro TTS or fallback) and cached
      in memory as (samples, sample_rate) pairs (~50KB per language set).
    - play_filler() picks a random clip and plays it via sounddevice.
      play_filler() is a BLOCKING call (it calls sd.wait()) — callers on
      an asyncio event loop MUST use play_filler_async() instead, or they
      will freeze every other concurrent task for the clip's duration.
    - Mic should be gated for ~300ms during playback to prevent echo.
    - Timing instrumentation logs wake_to_filler_ms for verification.

Performance:
    - Time Complexity: O(1) per play_filler() call — random.choice() on
      pre-cached arrays, no synthesis on the hot path.
    - Space Complexity: O(L * P) where L = number of language sets (~2) and
      P = phrases per set (~5) — a fixed, small number of short clips.
    - Latency: sub-millisecond from call to sd.play() dispatch. Actual audio
      onset depends on the audio backend, not this module.

Fixes applied in this revision (all verified — see notes inline):

    1. CRITICAL — `Kokoro.from_pretrained(...)` is not a real API. The
       kokoro_onnx package's actual constructor is
       `Kokoro(model_path, voices_path)` (verified against the project's
       README/examples and released wheel). `Kokoro.from_pretrained` does
       not exist on that class, so every call raised AttributeError and
       silently fell through to the pyttsx3 fallback (or the sine-wave
       beep, if pyttsx3 was also unavailable). In other words: the "haan
       bol" / natural-voice filler described in this module's own
       docstring was never actually being produced — only a robotic
       pyttsx3 voice or, on many installs, a plain beep. Fixed to call the
       real constructor.

    2. CRITICAL — a brand-new Kokoro instance (which loads a ~80-300MB
       ONNX model + voice bank off disk) was being constructed once PER
       PHRASE inside _synthesize_clip(), i.e. 10 separate full model loads
       for 10 short phrases, instead of 1 load + 10 cheap .create() calls.
       This turned an O(1)-model-load design into O(N) model loads and
       could add many seconds to the very startup this module exists to
       make instant. Fixed: the Kokoro engine is now built once and reused
       for every phrase.

    3. CRITICAL — play_filler() calls sd.play(); sd.wait(), which blocks
       the calling thread until the whole clip has finished playing. The
       only real call site for this module (orchestrator.py's
       run_pipeline(), an `async def`) calls it directly, un-awaited and
       not off-loaded to a thread — meaning every concurrent asyncio task
       (STT streaming, the parallel vision pipeline in
       handle_concurrent_event, etc.) froze for the ~300-500ms the filler
       played. That is the opposite of "instant, non-blocking presence
       feedback". Fixed by adding play_filler_async(), an awaitable
       wrapper that runs the blocking call in a worker thread via
       asyncio.to_thread — this is the version call sites under asyncio
       must use. (The orchestrator call site is patched to use it.)

    4. Per-clip sample rate was being lost. _synthesize_clip() previously
       returned only the numpy array and stashed the sample rate as a
       *shared* `self._sample_rate` instance attribute, overwritten by
       every subsequent call. If any single phrase ever fell back to
       pyttsx3 (OS-native rate, e.g. 22050Hz) while others were
       successfully synthesized by Kokoro (fixed 24000Hz), every clip in
       the cache would be played back at whichever rate happened to be
       set *last* — audibly pitched/sped up or down. Fixed: every cached
       clip is now stored as an explicit (samples, sample_rate) pair, and
       played back at its own rate, never a shared mutable one.

    5. initialize() and the module-level singleton had no locking at all,
       unlike the equivalent stores already hardened elsewhere in this
       codebase (reaction_rules.get_reaction_rules(), user_memory's
       get_user_memory(), speaker_verifier's get_speaker_verifier()) —
       all of which anticipate concurrent access. The orchestrator's own
       call site does a check-then-act
       `if not _filler_cache._initialized: _filler_cache.initialize()`,
       which is a real race if two wake events are ever in flight at once
       (see handle_concurrent_event's asyncio.gather of the vision and
       speech pipelines). Fixed with the same double-checked-locking
       pattern used by the rest of the codebase, both on initialize()
       itself and on the get_filler_cache() singleton.

    6. The pyttsx3 fallback constructed a brand-new `pyttsx3.init()` engine
       per phrase and never released it. pyttsx3 wraps a native OS TTS
       driver (espeak/sapi5/nsss); repeatedly instantiating without
       stopping it is a known resource leak and, on some drivers, a source
       of hangs on the *next* init in the same process. Fixed to build one
       engine once and reuse + explicitly stop() it.

    7. Known, NOT silently papered over: Kokoro's shipped voice set
       (af_*/am_*/bf_*/bm_* etc.) has no dedicated Hindi/Hinglish voice.
       Feeding "haan bol" / "bol bhai" through an English voice's G2P
       front-end will not sound like natural Hinglish — it will sound like
       an English voice attempting Romanized Hindi. There is no verified
       fix for this within Kokoro's current voice bank; this is a real
       product gap, not just a code bug, and is flagged here rather than
       hidden behind a "works on my machine" beep fallback.

    8. CRITICAL — _get_kokoro_engine()'s default model paths were the bare
       relative filenames "kokoro-v1.0.onnx" / "voices-v1.0.bin", resolved
       against the process's current working directory at runtime. The
       sibling module actually used for real Guru/Maya speech,
       speech/tts/tts_engine.py's CoquiTTSEngine, resolves (and
       auto-downloads) the SAME physical model files to a fixed, CWD-
       independent cache directory: Path.home() / ".cache" / "agent_guru"
       / "kokoro". A GUI app's working directory at launch is not
       reliably the install directory (or any directory containing these
       files), so on essentially any real-world launch this module would
       silently fail to find a model that is correctly present on disk at
       the canonical cache path — falling through to the pyttsx3/beep
       fallback every time, defeating fixes #1 and #2 above by accident of
       CWD rather than genuine model unavailability. Fixed: the defaults
       now point at the same canonical cache directory tts_engine.py uses,
       so both modules load the one shared, already-downloaded model
       instead of the filler cache needing (and never getting) its own
       copy. The KOKORO_MODEL_PATH / KOKORO_VOICES_PATH environment-
       variable overrides are preserved unchanged for testing/CI.

Author: Agent Guru Team
Date: 2026-07-07
"""

from __future__ import annotations

import logging
import os
import random
import threading
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Filler phrase banks — grouped by language preference
# ---------------------------------------------------------------------------

_FILLER_PHRASES: dict[str, list[str]] = {
    "hinglish": ["haan bol", "haan?", "bol bhai", "hmm?", "bolo"],
    "english": ["yeah?", "mmhm?", "go ahead", "yep?", "I'm listening"],
}

# Default language if preference not set
_DEFAULT_LANG = "hinglish"

# Duration to gate microphone during filler playback (seconds)
FILLER_MIC_GATE_DURATION_S = 0.35

# Fixed sample rate for the synthetic beep fallback. Independent of whatever
# rate any real TTS backend happens to return — see fix #4 above for why
# clip sample rates must never be shared mutable state.
_BEEP_SAMPLE_RATE = 24000

# Canonical Kokoro model cache location — MUST match
# speech/tts/tts_engine.py's _CACHE_DIR exactly (fix #8): both modules
# load the SAME physical model files, downloaded once by that module's
# CoquiTTSEngine._ensure_loaded(). Bare relative filenames here would
# resolve against the process's CWD at runtime, which is not reliably
# the install directory (or any directory containing the model) for a
# real deployed GUI app.
_KOKORO_CACHE_DIR = Path.home() / ".cache" / "agent_guru" / "kokoro"
_DEFAULT_KOKORO_MODEL_PATH = _KOKORO_CACHE_DIR / "kokoro-v1.0.onnx"
_DEFAULT_KOKORO_VOICES_PATH = _KOKORO_CACHE_DIR / "voices-v1.0.bin"

# A single cached (samples, sample_rate) filler clip.
_FillerClip = tuple[np.ndarray, int]


class FillerResponseCache:
    """Pre-cached filler audio clips for instant wake-word acknowledgement.

    Usage::

        cache = FillerResponseCache()
        cache.initialize()  # call once at startup (or via asyncio.to_thread)

        # From synchronous code:
        cache.play_filler("guru", "hinglish", wake_timestamp=t0)

        # From asyncio code (REQUIRED — play_filler() itself blocks):
        await cache.play_filler_async("guru", "hinglish", wake_timestamp=t0)

    The cache tries to synthesize fillers via Kokoro TTS at startup, using a
    single Kokoro engine instance shared across all phrases. If Kokoro is
    unavailable, it falls back to a single shared pyttsx3 engine. If neither
    is available, it generates simple sine-wave beep tones — still better
    than silence for presence feedback.
    """

    def __init__(self) -> None:
        # lang_pref -> list of (samples, sample_rate) pairs
        self._cache: dict[str, list[_FillerClip]] = {}
        self._initialized: bool = False
        self._lock = threading.Lock()

        # Lazily-built, reused-across-calls synthesis engines. Built once in
        # initialize() rather than once-per-phrase (fix #2).
        self._kokoro: object | None = None
        self._kokoro_unavailable: bool = False
        self._pyttsx3_engine: object | None = None
        self._pyttsx3_unavailable: bool = False

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Pre-synthesize all filler clips. Safe to call once at startup.

        Thread-safe double-checked locking (fix #5) — safe to call from
        multiple threads/tasks racing to warm the cache on first use.

        This does real, potentially slow, disk + model-load work (loading
        the Kokoro ONNX model) and MUST NOT be called directly from an
        asyncio event-loop thread; run it via asyncio.to_thread() (or
        during the app's existing concurrent subsystem startup) instead.
        """
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return

            kokoro = self._get_kokoro_engine()

            for lang, phrases in _FILLER_PHRASES.items():
                clips: list[_FillerClip] = []
                for phrase in phrases:
                    clip = None
                    if kokoro is not None:
                        clip = self._synthesize_kokoro(phrase, kokoro)
                    if clip is None:
                        clip = self._synthesize_pyttsx3(phrase)
                    if clip is not None and len(clip[0]) > 0:
                        clips.append(clip)

                if not clips:
                    # Fallback: generate a short listening beep
                    clips.append((self._generate_beep(duration_s=0.15), _BEEP_SAMPLE_RATE))
                    logger.info(
                        "FillerCache: no TTS clips for '%s' — using beep fallback",
                        lang,
                    )

                self._cache[lang] = clips
                logger.info(
                    "FillerCache: cached %d clips for '%s'", len(clips), lang
                )

            self._initialized = True
            logger.info(
                "FillerResponseCache initialized (%d language sets)", len(self._cache)
            )

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play_filler(
        self,
        personality: str = "guru",
        language_pref: str = "",
        wake_timestamp: float | None = None,
    ) -> float:
        """Play a random filler clip. Returns duration in seconds.

        BLOCKING: this calls sd.wait() and does not return until the clip
        has finished playing. Callers running inside an asyncio event loop
        must use play_filler_async() instead (fix #3) — calling this
        directly from an `async def` freezes every other concurrent task
        for the clip's duration.

        Args:
            personality: "guru" or "maya" — currently unused but reserved for
                         personality-specific filler voices in future.
            language_pref: "hinglish" or "english". Falls back to default.
            wake_timestamp: time.perf_counter() at wake-word detection, for
                           timing instrumentation. If provided, logs
                           wake_to_filler_ms.

        Returns:
            Duration of the played filler in seconds, or 0.0 if playback failed.
        """
        if not self._initialized:
            logger.warning("FillerCache: not initialized — skipping filler")
            return 0.0

        lang = language_pref if language_pref in self._cache else _DEFAULT_LANG
        clips = self._cache.get(lang)
        if not clips:
            return 0.0

        samples, sample_rate = random.choice(clips)  # noqa: S311 — not security-sensitive  # nosec B311

        # Timing instrumentation
        play_start = time.perf_counter()
        if wake_timestamp is not None:
            wake_to_filler_ms = (play_start - wake_timestamp) * 1000
            logger.info(
                "TIMING: wake_to_filler_ms=%.1f", wake_to_filler_ms
            )

        try:
            import sounddevice as sd

            sd.play(samples, samplerate=sample_rate)
            sd.wait()
            duration_s = len(samples) / sample_rate
            logger.debug(
                "Filler played (%.0fms, lang=%s)", duration_s * 1000, lang
            )
            return duration_s
        except Exception:
            logger.exception("Filler playback failed")
            return 0.0

    async def play_filler_async(
        self,
        personality: str = "guru",
        language_pref: str = "",
        wake_timestamp: float | None = None,
    ) -> float:
        """Non-blocking wrapper around play_filler() for asyncio callers.

        Runs the blocking synthesis/playback call in a worker thread via
        asyncio.to_thread(), so it never stalls the event loop or any
        other concurrently-running task (fix #3). This is the version any
        `async def` pipeline stage must call.
        """
        import asyncio

        return await asyncio.to_thread(
            self.play_filler, personality, language_pref, wake_timestamp
        )

    # ------------------------------------------------------------------
    # Synthesis backends
    # ------------------------------------------------------------------

    def _get_kokoro_engine(self):
        """Build (once) and return the shared Kokoro engine, or None.

        FIX: previously a new `Kokoro.from_pretrained(...)` was constructed
        per phrase, and `.from_pretrained` isn't a real method on this
        class in the first place — the real constructor is
        `Kokoro(model_path, voices_path)`. Built once here and cached on
        the instance so every phrase reuses the same loaded model
        (fixes #1 and #2).

        FIX #8: the default model/voices paths now point at the same
        canonical, CWD-independent cache directory speech/tts/tts_engine.py
        already downloads these exact files to, instead of bare relative
        filenames that only resolved by accident of working directory.
        """
        if self._kokoro_unavailable:
            return None
        if self._kokoro is not None:
            return self._kokoro
        try:
            from kokoro_onnx import Kokoro

            self._kokoro = Kokoro(
                os.environ.get("KOKORO_MODEL_PATH", str(_DEFAULT_KOKORO_MODEL_PATH)),
                os.environ.get("KOKORO_VOICES_PATH", str(_DEFAULT_KOKORO_VOICES_PATH)),
            )
            return self._kokoro
        except Exception:
            logger.info(
                "FillerCache: Kokoro unavailable — will use fallback backend",
                exc_info=True,
            )
            self._kokoro_unavailable = True
            return None

    def _synthesize_kokoro(self, text: str, kokoro) -> _FillerClip | None:
        """Synthesize one phrase with the shared Kokoro engine.

        Returns (samples, sample_rate), or None on failure for this phrase
        only — a single bad phrase no longer disables Kokoro for the rest
        of the batch.
        """
        try:
            samples, sample_rate = kokoro.create(
                text, voice="af_heart", speed=1.2, lang="en-us"
            )
            return np.asarray(samples, dtype=np.float32), int(sample_rate)
        except Exception:
            logger.debug("Kokoro synthesis failed for %r", text, exc_info=True)
            return None

    def _get_pyttsx3_engine(self):
        """Build (once) and return the shared pyttsx3 engine, or None.

        FIX: previously a new pyttsx3.init() engine was created per phrase
        and never stopped — a resource leak, and on some native drivers a
        source of hangs on the next init() in the same process. Built once
        here and reused.
        """
        if self._pyttsx3_unavailable:
            return None
        if self._pyttsx3_engine is not None:
            return self._pyttsx3_engine
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", 180)
            self._pyttsx3_engine = engine
            return engine
        except Exception:
            logger.info(
                "FillerCache: pyttsx3 unavailable — will use beep fallback",
                exc_info=True,
            )
            self._pyttsx3_unavailable = True
            return None

    def _synthesize_pyttsx3(self, text: str) -> _FillerClip | None:
        """Synthesize one phrase with the shared pyttsx3 engine (fallback).

        Returns (samples, sample_rate), or None on failure for this phrase.
        """
        engine = self._get_pyttsx3_engine()
        if engine is None:
            return None

        import tempfile

        tmp_path: str | None = None
        try:
            import soundfile as sf

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp_path = f.name

            engine.save_to_file(text, tmp_path)
            engine.runAndWait()

            data, sample_rate = sf.read(tmp_path, dtype="float32")
            return np.asarray(data, dtype=np.float32), int(sample_rate)
        except Exception:
            logger.debug("pyttsx3 synthesis failed for %r", text, exc_info=True)
            return None
        finally:
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    # Best-effort cleanup of our own temp file in a finally
                    # block. Raising here would replace the real synthesis
                    # result (or the real error) with a cleanup error.
                    pass

    def _generate_beep(self, duration_s: float = 0.15) -> np.ndarray:
        """Generate a short sine-wave beep as ultimate fallback.

        A gentle 800Hz tone that sounds like a subtle "listening" indicator.
        Always at _BEEP_SAMPLE_RATE — a fixed constant, not shared mutable
        instance state (see fix #4).
        """
        t = np.linspace(
            0, duration_s, int(_BEEP_SAMPLE_RATE * duration_s), dtype=np.float32
        )
        # 800Hz sine with fade-in/fade-out envelope
        freq = 800.0
        signal = np.sin(2 * np.pi * freq * t).astype(np.float32)

        # Apply smooth envelope (avoid clicks)
        fade_samples = int(_BEEP_SAMPLE_RATE * 0.02)  # 20ms fade
        if fade_samples > 0 and len(signal) > 2 * fade_samples:
            fade_in = np.linspace(0, 1, fade_samples, dtype=np.float32)
            fade_out = np.linspace(1, 0, fade_samples, dtype=np.float32)
            signal[:fade_samples] *= fade_in
            signal[-fade_samples:] *= fade_out

        # Keep volume low — this is a subtle acknowledgement, not an alarm
        signal *= 0.3
        return signal


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_filler_cache: FillerResponseCache | None = None
_filler_cache_lock = threading.Lock()


def get_filler_cache() -> FillerResponseCache:
    """Return the global FillerResponseCache (lazy init, thread-safe).

    FIX: previously a bare `if _filler_cache is None: _filler_cache = ...`
    with no lock — a real race if the first wake event and a concurrent
    vision-pipeline task (see handle_concurrent_event) both hit this at
    once. Double-checked locking, matching the pattern already used by
    get_user_memory() and get_reaction_rules() elsewhere in this codebase.
    """
    global _filler_cache
    if _filler_cache is None:
        with _filler_cache_lock:
            if _filler_cache is None:
                _filler_cache = FillerResponseCache()
    return _filler_cache
