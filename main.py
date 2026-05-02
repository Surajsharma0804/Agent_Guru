"""
Agent Guru — Main Entry Point

Wires all subsystems through IntegrationOrchestrator and starts the assistant.

Usage:
    python main.py

Wake words:
    "Hey Guru" / "Guru" — activates Guru (professional, analytical)
    "Hey Maya" / "Maya" — activates Maya (warm, creative)
"""
from __future__ import annotations

import asyncio
import logging
_logger = logging.getLogger(__name__)
import signal
import sys
from typing import Any, Optional

# Load .env before anything else so OLLAMA_MODEL, API keys, etc. are available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed — env vars must be set manually

# ---------------------------------------------------------------------------
# GPU / Ollama environment — set BEFORE any imports that touch CUDA or Ollama.
# OLLAMA_NO_CUDA=1 and OLLAMA_LLM_LIBRARY=cpu are sometimes set at the system
# level (e.g. during initial Ollama install on Windows). Override them here so
# the running process always uses GPU when CUDA is available.
# ---------------------------------------------------------------------------
import os as _os_startup
_os_startup.environ.pop("OLLAMA_NO_CUDA", None)
_os_startup.environ.pop("OLLAMA_LLM_LIBRARY", None)
# num_gpu=99 tells Ollama to offload as many layers as fit in VRAM.
# This is also passed per-request in the Ollama adapter options.
if not _os_startup.environ.get("OLLAMA_NUM_GPU"):
    _os_startup.environ["OLLAMA_NUM_GPU"] = "99"
# Ensure CUDA device 0 is visible (not masked by CUDA_VISIBLE_DEVICES=-1)
cuda_dev = _os_startup.environ.get("CUDA_VISIBLE_DEVICES", "")
if cuda_dev in ("-1", ""):
    _os_startup.environ["CUDA_VISIBLE_DEVICES"] = "0"
del _os_startup

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# Set Windows console to UTF-8 so log messages with special chars display correctly
import os as _os_enc
if _os_enc.name == 'nt':
    _os_enc.system('chcp 65001 >nul 2>&1')  # UTF-8 code page

# Fix Python stdout/stderr encoding
import sys as _sys, io as _io
if hasattr(_sys.stdout, 'buffer'):
    try:
        _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        _sys.stderr = _io.TextIOWrapper(_sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
    datefmt="%H:%M:%S",
    stream=_sys.stdout,
    force=True,
)
logger = logging.getLogger("guru.main")

# Suppress noisy warnings that fire constantly on a dev machine.
# None of these affect functionality — they're just informational thresholds.
logging.getLogger("guruvision.avatar.performance").setLevel(logging.ERROR)
logging.getLogger("guruvision.avatar").setLevel(logging.WARNING)
logging.getLogger("phonemizer").setLevel(logging.ERROR)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Subsystem imports — each wrapped so a missing dep logs clearly and raises
# ---------------------------------------------------------------------------

def _load_speech():
    try:
        from Agent_Guru.speech.engine import SpeechEngine
        return SpeechEngine()
    except Exception as e:
        logger.error("SpeechEngine failed to load: %s", e)
        _stub("speech_engine", critical=True)
        raise


def _load_vision():
    try:
        from Agent_Guru.vision.engine import GuruVisionEngine
        return GuruVisionEngine()
    except Exception as e:
        logger.warning("VisionEngine unavailable (%s) — vision disabled", e)
        return _stub("vision_engine")


def _load_llm():
    try:
        from Agent_Guru.llm import LLMRuntime, load_config_from_env
        cfg = load_config_from_env()
        if not cfg.ollama_config.host:
            cfg.ollama_config.host = "http://localhost:11434"
        return LLMRuntime.from_config(cfg)
    except Exception as e:
        logger.error("LLMRuntime failed to load: %s", e)
        _stub("llm_runtime", critical=True)
        raise


def _load_platform():
    try:
        from Agent_Guru.platform.os_controller import OSController
        return OSController(require_confirmation=False)
    except Exception as e:
        logger.warning("OSController unavailable (%s) — trying SystemSettingsController", e)
        try:
            from Agent_Guru.platform.controllers import SystemSettingsController
            return SystemSettingsController()
        except Exception as e2:
            logger.warning("PlatformController unavailable (%s) — platform control disabled", e2)
            return _stub("platform_controller")


def _load_agents():
    try:
        from Agent_Guru.agents import AgentOrchestrator
        return AgentOrchestrator()
    except Exception as e:
        logger.warning("AgentOrchestrator unavailable (%s) — agent actions disabled", e)
        return _stub("agent_orchestrator")


def _load_memory():
    try:
        from Agent_Guru.memory.config import MemoryConfig
        from Agent_Guru.memory.memory_manager import MemoryManager
        return MemoryManager(MemoryConfig())
    except Exception as e:
        logger.warning("MemoryManager unavailable (%s) — memory disabled", e)
        return _stub("memory")


def _load_reasoning():
    try:
        from Agent_Guru.reasoning.engine import ReasoningEngine
        return ReasoningEngine()
    except Exception as e:
        logger.warning("ReasoningEngine unavailable (%s) — reasoning disabled", e)
        return _stub("reasoning")


def _load_security():
    try:
        from Agent_Guru.security.biometric_auth import BiometricAuthenticator
        return BiometricAuthenticator()
    except Exception as e:
        logger.warning("SecuritySystem unavailable (%s) — security disabled", e)
        return _stub("security")


def _load_policy():
    try:
        from Agent_Guru.policy import PolicyEngine
        return PolicyEngine()
    except Exception as e:
        logger.warning("PolicyEngine unavailable (%s) — policy disabled", e)
        return _stub("policy")


def _load_avatar():
    try:
        from Agent_Guru.avatar import GuruAvatarSystem
        return GuruAvatarSystem(render_backend="headless")
    except Exception as e:
        logger.warning("AvatarSystem unavailable (%s) — avatar disabled", e)
        return _stub("avatar")


def _load_deployment():
    try:
        from Agent_Guru.deployment import OnboardingManager
        return OnboardingManager()
    except Exception as e:
        logger.warning("DeploymentSystem unavailable (%s) — deployment disabled", e)
        return _stub("deployment")


def _stub(name: str, critical: bool = False):
    """Return a minimal async-compatible stub for a missing subsystem.

    Critical stubs log an explicit ERROR so the operator knows the assistant
    is degraded.  Non-critical stubs are optional features.
    """
    from unittest.mock import AsyncMock, MagicMock
    if critical:
        logger.error(
            "DEGRADED: '%s' is running as a stub — responses will be limited.", name
        )
    m = MagicMock(name=name)
    m.initialize = AsyncMock(return_value=None)
    return m


# ---------------------------------------------------------------------------
# GPU pool
# ---------------------------------------------------------------------------

def _load_gpu_pool():
    import asyncio
    try:
        from Agent_Guru.integration.gpu_pool import GPUResourcePool
        return GPUResourcePool()
    except Exception as e:
        logger.warning(
            "GPUResourcePool unavailable (%s) — falling back to CPU-only pool", e
        )
        # Return a minimal CPU-only pool so startup continues
        # BUG-006 fix: include asyncio.Lock so concurrent startup coroutines
        # don't race on _allocations (previously missing from manual __new__ path).
        from Agent_Guru.integration.gpu_pool import GPUResourcePool, DeviceConfig
        pool = GPUResourcePool.__new__(GPUResourcePool)
        pool.device = "cpu"
        pool.total_vram = 0
        pool._allocations: dict = {}
        pool._lock = asyncio.Lock()  # BUG-006: was missing — race condition fixed

        def _cpu_allocate(name: str) -> DeviceConfig:
            return DeviceConfig(device="cpu", vram_limit_gb=0.0)

        pool.allocate = _cpu_allocate
        return pool


# ---------------------------------------------------------------------------
# Silero VAD — production-grade end-of-speech detection (same as Alexa/Siri)
# ---------------------------------------------------------------------------

_silero_vad_model: Any = None
_silero_get_speech_ts: Any = None


def _load_silero_vad() -> bool:
    """Load Silero VAD model once. Returns True on success."""
    global _silero_vad_model, _silero_get_speech_ts
    if _silero_vad_model is not None:
        return True
    try:
        from silero_vad import load_silero_vad, get_speech_timestamps  # type: ignore[import]
        _silero_vad_model = load_silero_vad()
        _silero_get_speech_ts = get_speech_timestamps
        logger.info("Silero VAD loaded — production-grade end-of-speech detection active")
        return True
    except Exception as exc:
        logger.warning("Silero VAD unavailable (%s) — using energy fallback", exc)
        return False


async def _capture_command_with_vad(
    wake_manager: Any,
    max_duration_s: float = 15.0,
    silence_duration_s: float = 1.5,
    silence_rms_threshold: float = 0.003,
) -> bytes:
    """Capture command audio using Silero VAD — same approach as Alexa/Siri.

    How Alexa/Siri do it:
    1. Start recording immediately after wake word fires
    2. Use neural VAD (Silero) to detect speech vs silence in real-time
    3. Stop recording ~1 second after the last speech segment ends
    4. Hard cap at 15s to prevent infinite recording

    Silero VAD is a neural network trained on millions of hours of speech.
    It correctly handles natural pauses, background noise, soft speech,
    and accented speech — far more reliable than energy thresholds.

    Args:
        wake_manager: WakeWordManager with capture_command_audio().
        max_duration_s: Hard cap on recording duration (default 15s).
        silence_duration_s: Stop after this many seconds of silence post-speech.
            1.0s matches Alexa/Siri standard (700ms-1000ms).
        silence_rms_threshold: Energy fallback threshold if Silero unavailable.

    Returns:
        Concatenated audio bytes (float32 PCM at 16kHz).
    """
    import numpy as np
    import torch

    # Load Silero VAD (cached after first call)
    use_silero = _load_silero_vad()

    # Each capture_command_audio(chunks=1) returns chunk_duration_s of audio
    chunk_duration_s: float = getattr(
        getattr(wake_manager, "_config", None), "audio_capture_duration", 1.5
    )
    if chunk_duration_s <= 0:
        chunk_duration_s = 1.5

    max_chunks = max(1, int(max_duration_s / chunk_duration_s))

    all_audio: list[np.ndarray] = []
    silence_after_speech_s = 0.0
    speech_ever_detected = False

    for i in range(max_chunks):
        try:
            chunk_bytes = await wake_manager.capture_command_audio(chunks=1)
        except Exception as exc:
            logger.warning("VAD capture chunk %d failed: %s", i, exc)
            break

        if not chunk_bytes:
            silence_after_speech_s += chunk_duration_s
        else:
            chunk_np = np.frombuffer(chunk_bytes, dtype=np.float32).copy()
            all_audio.append(chunk_np)

            # ── Silero VAD: neural speech detection ──────────────────────
            has_speech = False
            if use_silero and _silero_vad_model is not None:
                try:
                    audio_tensor = torch.from_numpy(chunk_np)
                    speech_ts = _silero_get_speech_ts(
                        audio_tensor,
                        _silero_vad_model,
                        sampling_rate=16000,
                        threshold=0.6,           # Higher threshold = less false positives
                        min_speech_duration_ms=200,  # Ignore very short sounds
                        min_silence_duration_ms=200,
                    )
                    has_speech = len(speech_ts) > 0
                except Exception:
                    rms = float(np.sqrt(np.mean(chunk_np ** 2)))
                    has_speech = rms >= silence_rms_threshold
            else:
                # Energy fallback
                rms = float(np.sqrt(np.mean(chunk_np ** 2)))
                has_speech = rms >= silence_rms_threshold

            if has_speech:
                speech_ever_detected = True
                silence_after_speech_s = 0.0
                logger.debug("VAD chunk %d: SPEECH", i)
            else:
                silence_after_speech_s += chunk_duration_s
                logger.debug("VAD chunk %d: silence (%.1fs after speech)", i, silence_after_speech_s)

        # Stop when silence_duration_s of silence detected AFTER speech
        if speech_ever_detected and silence_after_speech_s >= silence_duration_s:
            logger.info(
                "VAD: end-of-speech after %d chunks (%.1fs total, %.1fs silence)",
                i + 1, len(all_audio) * chunk_duration_s, silence_after_speech_s
            )
            break
        # Also stop if we've captured enough audio and there's been no speech at all
        # (prevents recording forever when user doesn't speak)
        if not speech_ever_detected and len(all_audio) * chunk_duration_s >= 6.0:
            logger.info("VAD: no speech detected after 6s — stopping")
            break

    if not all_audio:
        return b""

    combined = np.concatenate(all_audio).astype(np.float32)

    # ── Background audio rejection ────────────────────────────────────────
    # If the captured audio looks like music/TV (high spectral flatness,
    # low zero-crossing variance), it's probably background noise that
    # leaked through after the wake word fired. Discard it.
    # This is the same check used in wake word detection.
    try:
        from Agent_Guru.speech.audio.wake_word import WakeWordDetector
        if WakeWordDetector._looks_like_music(combined):
            logger.info(
                "VAD: captured audio looks like background music — discarding "
                "(%.1fs, rms=%.4f). Speak closer to the mic.",
                len(combined) / 16000,
                float(np.sqrt(np.mean(combined ** 2))),
            )
            return b""
    except Exception:
        pass  # If check fails, proceed with the audio

    logger.info("VAD: captured %.1fs of audio", len(combined) / 16000)
    return combined.tobytes()


# ---------------------------------------------------------------------------
# Main async startup
# ---------------------------------------------------------------------------

async def run() -> None:
    from Agent_Guru.integration import IntegrationOrchestrator, WakeWordEvent
    from Agent_Guru.speech.wake_word_manager import WakeWordManager, WakeWordManagerConfig
    from Agent_Guru.speech.audio.wake_word import WakeWordConfig
    from Agent_Guru.speech.models import PersonalityType

    # BUG-025: replaced print() calls with logger.info() so startup messages
    # flow through the logging infrastructure instead of raw stdout.
    logger.info("=" * 44)
    logger.info("         Agent Guru  v0.1.0              ")
    logger.info("  Say 'Hey Guru' or 'Hey Maya' to start  ")
    logger.info("=" * 44)

    # --- Load all subsystems ---
    logger.info("Loading subsystems...")
    speech     = _load_speech()
    vision     = _load_vision()
    llm        = _load_llm()
    platform   = _load_platform()
    agents     = _load_agents()
    memory     = _load_memory()
    reasoning  = _load_reasoning()
    security   = _load_security()
    policy     = _load_policy()
    avatar     = _load_avatar()
    deployment = _load_deployment()
    gpu_pool   = _load_gpu_pool()

    # --- Wire through IntegrationOrchestrator ---
    orch = IntegrationOrchestrator(
        speech_engine=speech,
        vision_engine=vision,
        llm_runtime=llm,
        platform_controller=platform,
        agent_orchestrator=agents,
        memory=memory,
        reasoning=reasoning,
        security=security,
        policy=policy,
        avatar=avatar,
        deployment=deployment,
        gpu_pool=gpu_pool,
    )

    # --- Concurrent startup of all subsystems ---
    logger.info("Starting all subsystems concurrently...")
    await orch.startup()
    logger.info("All subsystems ready.")

    # --- Pre-warm Whisper tiny for wake word personality detection ---
    # This ensures Maya is detected correctly on the FIRST call.
    # Without pre-warming, the first detection always falls back to the
    # spectral heuristic (which always picks Guru).
    # --- Pre-warm Silero VAD and Whisper tiny at startup ---
    logger.info("Pre-loading Silero VAD...")
    await asyncio.get_running_loop().run_in_executor(None, _load_silero_vad)

    logger.info("Pre-warming Whisper tiny for wake word detection...")
    _whisper_tiny_global: Any = None
    try:
        import numpy as np
        from faster_whisper import WhisperModel
        import torch

        # Try GPU (int8) first — 10x faster than CPU, safe on Windows with CTranslate2
        # Fall back to CPU float32 if CUDA is unavailable or has DLL issues
        _ww_device = "cpu"
        _ww_compute = "float32"
        if torch.cuda.is_available():
            try:
                _test = WhisperModel("tiny", device="cuda", compute_type="int8")
                _dummy = np.zeros(16000, dtype=np.float32)
                list(_test.transcribe(_dummy, language="en", beam_size=1)[0])
                _ww_device = "cuda"
                _ww_compute = "int8"
                _whisper_tiny_global = _test
                logger.info("Whisper tiny pre-warmed on GPU (int8) — fast Maya detection ready")
            except Exception as _gpu_err:
                logger.warning("Whisper tiny GPU failed (%s) — using CPU", _gpu_err)
                _whisper_tiny_global = None

        if _whisper_tiny_global is None:
            _whisper_tiny_global = WhisperModel("tiny", device="cpu", compute_type="float32")
            _dummy = np.zeros(16000, dtype=np.float32)
            list(_whisper_tiny_global.transcribe(_dummy, language="en", beam_size=1)[0])
            logger.info("Whisper tiny pre-warmed on CPU — Maya detection ready")

    except Exception as _e:
        logger.warning("Whisper tiny pre-warm failed (%s) — Maya detection uses spectral fallback", _e)
        _whisper_tiny_global = None

    # --- Define pipeline callback BEFORE starting the listener ---
    async def _on_wake_word(detection) -> None:
        """Called by WakeWordManager when a real wake word is detected."""
        personality_name = detection.personality.value.upper()
        logger.info("Wake word: '%s' → %s", detection.wake_word, personality_name)
        _logger.info("[%s] Listening for your command...", personality_name)

        # Wait 0.5s after wake word fires before starting capture.
        # This gives the user time to finish saying the wake word and
        # take a natural breath before speaking the command.
        await asyncio.sleep(0.5)

        # Capture command audio using Silero VAD (same as Alexa/Siri).
        # Stops ~1s after the user stops speaking. Hard cap: 15s.
        import numpy as np
        try:
            audio_bytes = await _capture_command_with_vad(wake_manager)

            # Prepend wake word audio so STT sees the full utterance
            # e.g. "Hey Maya play chak de india" → full sentence captured
            wake_audio = getattr(detection, "audio_chunk", None)
            if wake_audio is not None and len(wake_audio) > 0:
                wake_bytes = wake_audio.astype(np.float32).tobytes()
                audio_bytes = wake_bytes + audio_bytes

            if audio_bytes:
                command_audio = np.frombuffer(audio_bytes, dtype=np.float32)
                rms = float(np.sqrt(np.mean(command_audio ** 2)))
                logger.info(
                    "Command audio captured: %.2fs, rms=%.4f",
                    len(command_audio) / 16000, rms
                )
        except Exception as exc:
            logger.warning("Command audio capture failed: %s", exc)
            audio_bytes = b""

        event = WakeWordEvent(
            wake_word=detection.wake_word,
            audio=audio_bytes,
        )
        result = await orch.run_pipeline(event)
        logger.info(
            "Pipeline complete — stages: %d/8, personality: %s, transcript: %r",
            result.stages_completed,
            result.personality.value,
            result.transcript,
        )
        if result.error:
            logger.warning("Pipeline error: %s", result.error)
        print(f"  [{personality_name}] Ready — say 'Hey Guru' or 'Hey Maya' again.\n")

    # --- Initialise wake word manager and open microphone ---
    wake_cfg = WakeWordConfig(
        wake_words={
            "hey guru": PersonalityType.GURU,
            "guru":     PersonalityType.GURU,
            "hey maya": PersonalityType.MAYA,
            "maya":     PersonalityType.MAYA,
        },
        energy_threshold=0.025,  # raised from 0.015 — music/speaker output won't trigger
        cooldown_seconds=3.0,    # 3s cooldown — stops rapid re-triggers from music
    )
    mgr_cfg = WakeWordManagerConfig(
        wake_word_config=wake_cfg,
        # Capture 1.5s chunks — longer audio = more reliable MFCC detection
        audio_capture_duration=1.5,
        # Poll every 50ms in sleep mode — low CPU, still responsive
        sleep_poll_interval=0.05,
        on_detection_callback=_on_wake_word,
    )
    wake_manager = WakeWordManager(mgr_cfg)

    await wake_manager.initialize()

    # Inject the pre-warmed Whisper tiny model into the detector so it never
    # reloads from disk on the first detection — zero latency on first Maya call.
    if _whisper_tiny_global is not None:
        try:
            detector = getattr(wake_manager, "_detector", None) or getattr(wake_manager, "_wake_word_detector", None)
            if detector is not None:
                detector._whisper_tiny = _whisper_tiny_global
                logger.info("Pre-warmed Whisper tiny injected into WakeWordDetector")
        except Exception as _inj_err:
            logger.warning("Could not inject pre-warmed Whisper: %s", _inj_err)

    # Extended warmup — lets the mic AGC stabilise and energy buffer fill
    # with real ambient noise levels so the first detection isn't a false positive.
    # 3s matches Alexa/Google's standard mic calibration window.
    logger.info("Calibrating microphone (3s)...")
    await asyncio.sleep(3.0)
    await wake_manager.start_listening()
    logger.info("Microphone open — listening for wake words.")

    logger.info("[OK] Agent Guru is running.")
    logger.info("  GPU device  : %s", gpu_pool.device)
    if gpu_pool.device == "cuda":
        total_gb = gpu_pool.total_vram / (1024 ** 3)
        logger.info("  Total VRAM  : %.1f GB", total_gb)
    else:
        logger.info("  Mode        : CPU-only (no CUDA GPU detected)")
    logger.info("  Listening for 'Hey Guru' or 'Hey Maya'...")
    logger.info("  Press Ctrl+C to stop.")

    # --- Graceful shutdown on SIGINT/SIGTERM ---
    stop_event = asyncio.Event()

    def _handle_signal(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            signal.signal(sig, _handle_signal)

    # Keep running until interrupted
    await stop_event.wait()

    # --- Shutdown ---
    logger.info("Shutting down Agent Guru...")
    await wake_manager.stop_listening()
    await orch.sleep()

    if hasattr(speech, "shutdown") and callable(speech.shutdown):
        try:
            speech.shutdown()
        except Exception as e:
            _logger.warning("Suppressed exception: %s", e)

    logger.info("Agent Guru stopped. Goodbye.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        _logger.info("Interrupted.")
        sys.exit(0)
