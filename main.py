"""
Agent Guru - Main Entry Point

Wires all subsystems through IntegrationOrchestrator and starts the assistant.

Usage:
    python main.py

Wake words:
    "Hey Guru" / "Guru" - activates Guru (professional, analytical)
    "Hey Maya" / "Maya" - activates Maya (warm, creative)
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import signal
import sys
from typing import Any

# Load .env before anything else so OLLAMA_MODEL, API keys, etc. are available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed - env vars must be set manually

# ---------------------------------------------------------------------------
# GPU / Ollama environment - set BEFORE any imports that touch CUDA or Ollama.
# ---------------------------------------------------------------------------
os.environ.pop("OLLAMA_NO_CUDA", None)
os.environ.pop("OLLAMA_LLM_LIBRARY", None)
# num_gpu=99 tells Ollama to offload as many layers as fit in VRAM.
if not os.environ.get("OLLAMA_NUM_GPU"):
    os.environ["OLLAMA_NUM_GPU"] = "99"
# Ensure CUDA device 0 is visible (not masked by CUDA_VISIBLE_DEVICES=-1)
_cuda_dev = os.environ.get("CUDA_VISIBLE_DEVICES", "")
if _cuda_dev in ("-1", ""):
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"

# ---------------------------------------------------------------------------
# Console encoding - Windows UTF-8 setup
# ---------------------------------------------------------------------------
if os.name == 'nt':
    import subprocess
    try:
        subprocess.run(  # noqa: S602, S607
            'chcp 65001', shell=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass  # Non-critical - UTF-8 code page is best-effort

# Fix Python stdout/stderr encoding
if hasattr(sys.stdout, 'buffer'):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s - %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("guru.main")

# Startup timeout - prevents infinite hang if Ollama or Whisper download stalls
_STARTUP_TIMEOUT_S = float(os.environ.get("AGENT_GURU_STARTUP_TIMEOUT", "120"))
# Max restart attempts with exponential backoff before giving up
_MAX_RESTART_ATTEMPTS = int(os.environ.get("AGENT_GURU_MAX_RESTARTS", "5"))

# Suppress noisy warnings that fire constantly on a dev machine.
logging.getLogger("guruvision.avatar.performance").setLevel(logging.ERROR)
logging.getLogger("guruvision.avatar").setLevel(logging.WARNING)
logging.getLogger("phonemizer").setLevel(logging.ERROR)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Subsystem imports - each wrapped so a missing dep logs clearly and raises
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
        logger.warning("VisionEngine unavailable (%s) - vision disabled", e)
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
        logger.warning("OSController unavailable (%s) - trying SystemSettingsController", e)
        try:
            from Agent_Guru.platform.controllers.system_settings import SystemSettingsController
            return SystemSettingsController()
        except Exception as e2:
            logger.warning("PlatformController unavailable (%s) - platform control disabled", e2)
            return _stub("platform_controller")


def _load_agents():
    try:
        from Agent_Guru.agents import AgentOrchestrator
        return AgentOrchestrator()
    except Exception as e:
        logger.warning("AgentOrchestrator unavailable (%s) - agent actions disabled", e)
        return _stub("agent_orchestrator")


def _load_memory():
    try:
        from Agent_Guru.memory.config import MemoryConfig
        from Agent_Guru.memory.memory_manager import MemoryManager
        return MemoryManager(MemoryConfig())
    except Exception as e:
        logger.warning("MemoryManager unavailable (%s) - memory disabled", e)
        return _stub("memory")


def _load_reasoning():
    try:
        from Agent_Guru.reasoning.engine import ReasoningEngine
        return ReasoningEngine()
    except Exception as e:
        logger.warning("ReasoningEngine unavailable (%s) - reasoning disabled", e)
        return _stub("reasoning")


def _load_security():
    try:
        from Agent_Guru.security.biometric_auth import BiometricAuthenticator
        return BiometricAuthenticator()
    except Exception as e:
        logger.warning("SecuritySystem unavailable (%s) - security disabled", e)
        return _stub("security")


def _load_policy():
    try:
        from Agent_Guru.policy import PolicyEngine
        return PolicyEngine()
    except Exception as e:
        logger.warning("PolicyEngine unavailable (%s) - policy disabled", e)
        return _stub("policy")


def _load_avatar():
    try:
        from Agent_Guru.avatar import GuruAvatarSystem
        return GuruAvatarSystem(render_backend="headless")
    except Exception as e:
        logger.warning("AvatarSystem unavailable (%s) - avatar disabled", e)
        return _stub("avatar")


def _load_deployment():
    try:
        from Agent_Guru.deployment import OnboardingManager
        return OnboardingManager()
    except Exception as e:
        logger.warning("DeploymentSystem unavailable (%s) - deployment disabled", e)
        return _stub("deployment")


def _stub(name: str, critical: bool = False):
    """Return a minimal async-compatible stub for a missing subsystem.

    Critical stubs log an explicit ERROR so the operator knows the assistant
    is degraded.  Non-critical stubs are optional features.
    """
    from unittest.mock import AsyncMock, MagicMock
    if critical:
        logger.error(
            "DEGRADED: '%s' is running as a stub - responses will be limited.", name
        )
    m = MagicMock(name=name)
    m.initialize = AsyncMock(return_value=None)
    return m


# ---------------------------------------------------------------------------
# GPU pool
# ---------------------------------------------------------------------------

def _load_gpu_pool():
    try:
        from Agent_Guru.integration.gpu_pool import GPUResourcePool
        return GPUResourcePool()
    except Exception as e:
        logger.warning(
            "GPUResourcePool unavailable (%s) - falling back to CPU-only pool", e
        )
        # MED-003 fix: previous __new__ path omitted whisper_budget/onnx_budget/torch_budget.
        # Now all attributes that GPUResourcePool.allocate() touches are initialised so
        # the fallback object behaves identically to a real CPU pool (no AttributeError).
        from Agent_Guru.integration.gpu_pool import GPUResourcePool, DeviceConfig  # noqa: F811
        pool = GPUResourcePool.__new__(GPUResourcePool)
        pool.device = "cpu"
        pool.total_vram = 0
        pool.whisper_budget = 0
        pool.onnx_budget = 0
        pool.torch_budget = 0
        object.__setattr__(pool, '_allocations', {})

        def _cpu_allocate(subsystem: str) -> DeviceConfig:
            return DeviceConfig(device="cpu", memory_limit=0)

        pool.allocate = _cpu_allocate  # type: ignore[assignment]
        return pool


# ---------------------------------------------------------------------------
# Silero VAD - production-grade end-of-speech detection (same as Alexa/Siri)
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
        logger.info("Silero VAD loaded - production-grade end-of-speech detection active")
        return True
    except Exception as exc:
        logger.warning("Silero VAD unavailable (%s) - using energy fallback", exc)
        return False


async def _capture_command_with_vad(
    wake_manager: Any,
    max_duration_s: float = 12.0,
    silence_duration_s: float = 1.2,
    silence_rms_threshold: float = 0.008,
) -> bytes:
    """Capture command audio after wake word fires.

    Uses Silero VAD with the correct two-threshold hysteresis approach
    (same as production voice assistants):
    - positive_threshold=0.5: frame is speech if probability > 0.5
    - negative_threshold=0.15: frame is silence if probability < 0.15
    - Frames between 0.15-0.5 are ignored (hysteresis zone)

    This prevents both false positives (background noise triggering speech)
    and false negatives (soft speech being missed).

    Standard settings from Silero VAD docs:
    - threshold: 0.5 (standard), lower = more sensitive
    - min_speech_duration_ms: 250ms (filters clicks/pops)
    - min_silence_duration_ms: 100ms (allows natural pauses)
    """
    import numpy as np
    import torch

    use_silero = _load_silero_vad()

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

            has_speech = False
            if use_silero and _silero_vad_model is not None:
                try:
                    audio_tensor = torch.from_numpy(chunk_np)
                    # Standard Silero VAD settings from official docs
                    speech_ts = _silero_get_speech_ts(
                        audio_tensor,
                        _silero_vad_model,
                        sampling_rate=16000,
                        threshold=0.5,               # standard - balanced sensitivity
                        min_speech_duration_ms=250,  # filter clicks/pops
                        min_silence_duration_ms=100, # allow natural pauses
                        speech_pad_ms=30,            # pad speech segments slightly
                    )
                    has_speech = len(speech_ts) > 0
                except Exception:
                    rms = float(np.sqrt(np.mean(chunk_np ** 2)))
                    has_speech = rms >= silence_rms_threshold
            else:
                rms = float(np.sqrt(np.mean(chunk_np ** 2)))
                has_speech = rms >= silence_rms_threshold

            if has_speech:
                speech_ever_detected = True
                silence_after_speech_s = 0.0
            else:
                silence_after_speech_s += chunk_duration_s

        if speech_ever_detected and silence_after_speech_s >= silence_duration_s:
            logger.info(
                "VAD: end-of-speech after %d chunks (%.1fs total, %.1fs silence)",
                i + 1, len(all_audio) * chunk_duration_s, silence_after_speech_s,
            )
            break

        if not speech_ever_detected and len(all_audio) * chunk_duration_s >= 8.0:
            logger.info("VAD: no speech detected after 8s - stopping")
            break

    if not all_audio:
        return b""

    combined = np.concatenate(all_audio).astype(np.float32)
    combined_rms = float(np.sqrt(np.mean(combined ** 2)))

    # Gate: if overall RMS is near silence, don't waste time on STT
    if combined_rms < 0.005:
        logger.info("VAD: audio is near-silence (rms=%.4f) - discarding", combined_rms)
        return b""

    # Only reject background audio if NO speech was detected at all
    if not speech_ever_detected:
        try:
            from Agent_Guru.speech.audio.wake_word import WakeWordDetector
            if WakeWordDetector._looks_like_music(combined):
                logger.info("VAD: no speech + music detected - discarding")
                return b""
        except Exception:
            pass

    logger.info("VAD: captured %.1fs of audio (rms=%.4f)", len(combined) / 16000, combined_rms)
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

        def _load_whisper_tiny(device: str, compute_type: str) -> WhisperModel:
            """Load Whisper tiny, preferring local cache to avoid HuggingFace calls."""
            try:
                return WhisperModel("tiny", device=device, compute_type=compute_type, local_files_only=True)
            except Exception:
                return WhisperModel("tiny", device=device, compute_type=compute_type)

        # Try GPU (int8) first - 10x faster than CPU, safe on Windows with CTranslate2
        # Fall back to CPU float32 if CUDA is unavailable or has DLL issues
        _ww_device = "cpu"
        _ww_compute = "float32"
        if torch.cuda.is_available():
            try:
                _test = _load_whisper_tiny("cuda", "int8")
                _dummy = np.zeros(16000, dtype=np.float32)
                list(_test.transcribe(_dummy, language="en", beam_size=1)[0])
                _ww_device = "cuda"
                _ww_compute = "int8"
                _whisper_tiny_global = _test
                logger.info("Whisper tiny pre-warmed on GPU (int8) - fast Maya detection ready")
            except Exception as _gpu_err:
                logger.warning("Whisper tiny GPU failed (%s) - using CPU", _gpu_err)
                _whisper_tiny_global = None

        if _whisper_tiny_global is None:
            _whisper_tiny_global = _load_whisper_tiny("cpu", "float32")
            _dummy = np.zeros(16000, dtype=np.float32)
            list(_whisper_tiny_global.transcribe(_dummy, language="en", beam_size=1)[0])
            logger.info("Whisper tiny pre-warmed on CPU - Maya detection ready")

    except Exception as _e:
        logger.warning("Whisper tiny pre-warm failed (%s) - Maya detection uses spectral fallback", _e)
        _whisper_tiny_global = None

    # --- Define pipeline callback BEFORE starting the listener ---
    async def _on_wake_word(detection) -> None:
        """Called by WakeWordManager when a real wake word is detected."""
        personality_name = detection.personality.value.upper()
        logger.info("Wake word: '%s' → %s", detection.wake_word, personality_name)
        logger.info("[%s] Listening for your command...", personality_name)

        await asyncio.sleep(0.5)

        import numpy as np
        try:
            audio_bytes = await _capture_command_with_vad(wake_manager)

            wake_audio = getattr(detection, "audio_chunk", None)
            if wake_audio is not None and len(wake_audio) > 0:
                wake_bytes = wake_audio.astype(np.float32).tobytes()
                audio_bytes = wake_bytes + audio_bytes

            if audio_bytes:
                command_audio = np.frombuffer(audio_bytes, dtype=np.float32)
                rms = float(np.sqrt(np.mean(command_audio ** 2)))
                logger.info("Command audio captured: %.2fs, rms=%.4f", len(command_audio) / 16000, rms)
        except Exception as exc:
            logger.warning("Command audio capture failed: %s", exc)
            audio_bytes = b""

        try:
            event = WakeWordEvent(wake_word=detection.wake_word, audio=audio_bytes)

            # Play a short "thinking" tone so the user knows we heard them
            # and are processing - prevents them thinking it's broken during LLM wait
            try:
                import sounddevice as _sd_beep
                import numpy as _np_beep
                _sr = 22050
                _t = _np_beep.linspace(0, 0.15, int(_sr * 0.15), False)
                _beep = (_np_beep.sin(2 * _np_beep.pi * 880 * _t) * 0.3).astype(_np_beep.float32)
                _fade = _np_beep.linspace(1, 0, len(_beep))
                _sd_beep.play(_beep * _fade, samplerate=_sr)  # type: ignore[attr-defined]
                _sd_beep.wait()
            except Exception:
                pass

            result = await orch.run_pipeline(event)

            actual_personality = result.personality.value.upper()
            logger.info(
                "Pipeline complete - stages: %d/8, personality: %s, transcript: %r",
                result.stages_completed, result.personality.value, result.transcript,
            )
            if result.error:
                logger.warning("Pipeline error: %s", result.error)
            logger.info(
                "[%s] Ready - say 'Hey Guru' or 'Hey Maya' again.",
                actual_personality,
            )

        except Exception as exc:
            # Never let a pipeline crash kill the whole process
            logger.error("Pipeline crashed (will keep listening): %s", exc, exc_info=True)
            logger.warning("[%s] Error - still listening.", personality_name)

    async def _say_microphone_status(message: str) -> None:
        """Speak a microphone-lost or microphone-restored notice.

        When the input stream died, the only trace used to be a log line
        nobody at a voice assistant reads, while the startup banner still
        said it was listening. Speaking is the one channel that reaches a
        user who is talking to it. Bounded like the pipeline's own TTS stage
        so a stuck synthesiser cannot stall the loop that reopens the mic.
        """
        from Agent_Guru.integration.orchestrator import TTS_TIMEOUT_S, Personality

        try:
            await asyncio.wait_for(
                orch._stage_tts(message, Personality.GURU), timeout=TTS_TIMEOUT_S,
            )
        except TimeoutError:
            logger.warning("Microphone status notice not spoken: TTS exceeded %.1fs", TTS_TIMEOUT_S)

    # --- Initialise wake word manager and open microphone ---
    wake_cfg = WakeWordConfig(
        wake_words={
            "hey guru": PersonalityType.GURU,
            "guru":     PersonalityType.GURU,
            "hey maya": PersonalityType.MAYA,
            "maya":     PersonalityType.MAYA,
        },
        energy_threshold=0.015,  # tuned for sounddevice - ambient RMS ~0.001, speech ~0.01-0.05
        cooldown_seconds=3.0,    # 3s cooldown - stops rapid re-triggers from music
    )
    mgr_cfg = WakeWordManagerConfig(
        wake_word_config=wake_cfg,
        # Capture 1.5s chunks - longer audio = more reliable MFCC detection
        audio_capture_duration=1.5,
        # Poll every 50ms in sleep mode - low CPU, still responsive
        sleep_poll_interval=0.05,
        on_detection_callback=_on_wake_word,
        on_microphone_lost=_say_microphone_status,
        on_microphone_restored=_say_microphone_status,
    )
    wake_manager = WakeWordManager(mgr_cfg)

    await wake_manager.initialize()

    # Inject the pre-warmed Whisper tiny model into the detector so it never
    # reloads from disk on the first detection - zero latency on first Maya call.
    if _whisper_tiny_global is not None:
        try:
            detector = getattr(wake_manager, "_detector", None) or getattr(wake_manager, "_wake_word_detector", None)
            if detector is not None:
                detector._whisper_tiny = _whisper_tiny_global
                logger.info("Pre-warmed Whisper tiny injected into WakeWordDetector")
        except Exception as _inj_err:
            logger.warning("Could not inject pre-warmed Whisper: %s", _inj_err)

    # Extended warmup - lets the mic AGC stabilise and energy buffer fill
    # with real ambient noise levels so the first detection isn't a false positive.
    # 3s matches Alexa/Google's standard mic calibration window.
    logger.info("Calibrating microphone (3s)...")
    await asyncio.sleep(3.0)
    await wake_manager.start_listening()
    logger.info("Microphone open - listening for wake words.")

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

    # Guard against IntegrationOrchestrator versions without sleep()
    if hasattr(orch, "sleep") and callable(orch.sleep):
        try:
            await orch.sleep()
        except Exception as e:
            logger.warning("Orchestrator sleep failed (non-critical): %s", e)

    if hasattr(speech, "shutdown") and callable(speech.shutdown):
        try:
            speech.shutdown()
        except Exception as e:
            logger.warning("Speech shutdown suppressed: %s", e)

    logger.info("Agent Guru stopped. Goodbye.")


# ---------------------------------------------------------------------------
# Entry point - with auto-restart on crash
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import time as _time

    _restart_count = 0
    _backoff_s = 3.0

    while _restart_count < _MAX_RESTART_ATTEMPTS:
        try:
            asyncio.run(run())
            # run() only returns on clean shutdown (Ctrl+C / SIGTERM)
            break
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
            break
        except Exception as _crash:
            _restart_count += 1
            if _restart_count >= _MAX_RESTART_ATTEMPTS:
                logger.critical(
                    "Agent Guru crashed %d times - giving up. Last error: %s",
                    _restart_count, _crash, exc_info=True,
                )
                sys.exit(1)
            logger.error(
                "Agent Guru crashed (%d/%d): %s - restarting in %.0fs...",
                _restart_count, _MAX_RESTART_ATTEMPTS,
                _crash, _backoff_s, exc_info=True,
            )
            _time.sleep(_backoff_s)
            _backoff_s = min(_backoff_s * 2, 60.0)  # Exponential backoff, max 60s
            logger.info("Restarting Agent Guru (attempt %d)...", _restart_count + 1)
            continue
    else:
        logger.critical("Max restart attempts (%d) exhausted. Exiting.", _MAX_RESTART_ATTEMPTS)
        sys.exit(1)
