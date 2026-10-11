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

# Before anything reads its settings: settings.toml in the data folder fills in
# the environment variables every module reads; a variable already set wins.
from Agent_Guru.utils.path_utils import app_data_dir as _app_data_dir  # noqa: E402
from Agent_Guru.utils.settings import apply_settings_file  # noqa: E402

apply_settings_file(_app_data_dir("settings.toml"))

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


def _load_mcp_servers():
    """The MCP servers configured in settings.toml, or [] when there are none or the table is wrong.

    A wrong [mcp] table is reported and MCP left off for this run, rather
    than stopping the assistant; `python -m Agent_Guru mcp list` says what
    is wrong.
    """
    try:
        from Agent_Guru.utils.path_utils import app_data_dir
        from Agent_Guru.utils.settings import read_settings_section

        settings = app_data_dir("settings.toml")
        if not read_settings_section(settings, "mcp"):
            return []  # nothing configured: the MCP code is not even loaded
        from Agent_Guru.integration.mcp_tools import load_servers

        return [s for s in load_servers(settings, dict(os.environ)) if s.enabled]
    except Exception as e:
        logger.warning("MCP servers not used (%s)", e)
        return []


def _load_policy(mcp_servers=()):
    try:
        from Agent_Guru.policy import PolicyEngine
        from Agent_Guru.policy.defaults import install_default_policies

        # An engine with no policies denies everything, and this one had
        # none: every voice command was denied and answered "Done.".
        engine = PolicyEngine()
        install_default_policies(engine)
        if mcp_servers:
            from Agent_Guru.integration.mcp_tools import install_mcp_policies

            # Exactly the tools the owner allowed, with a declared risk.
            install_mcp_policies(engine, list(mcp_servers))
        return engine
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

def _load_trace_store():
    """The store each voice turn is recorded in, or None to record nothing.

    A turn's result used to be logged and dropped, so stage timings, the
    action's verified status and the spoken reply were not kept anywhere.
    Off with AGENT_GURU_TRACES=0. Kept in turns.db beside memory.db, which
    already holds the same transcripts and replies.
    """
    if os.environ.get("AGENT_GURU_TRACES", "1").strip().lower() in {"0", "false", "no", "off"}:
        logger.info("Turn traces off (AGENT_GURU_TRACES)")
        return None
    try:
        from Agent_Guru.integration.turn_trace import TurnTraceStore
        from Agent_Guru.utils.path_utils import app_data_dir

        return TurnTraceStore(app_data_dir("turns.db"))
    except Exception as e:
        logger.warning("Turn traces unavailable (%s) - turns will not be recorded", e)
        return None


def _load_document_store():
    """The owner's documents (documents.db), searched for passages that answer a question.

    None if the store cannot be opened; the assistant then answers as it
    did before documents could be added.
    """
    try:
        from Agent_Guru.platform.features.documents import DocumentStore
        from Agent_Guru.utils.path_utils import app_data_dir

        return DocumentStore(app_data_dir("documents.db"))
    except Exception as e:
        logger.warning("Documents unavailable (%s) - answering without them", e)
        return None


def _load_audit_logger():
    """The audit log kept on disk, chained and signed with a key that survives restarts.

    The orchestrator's audit log used to live in memory, so every turn's
    entry was gone when the app exited. If the signing key cannot be read
    (another Windows account, a damaged file), the log falls back to memory
    for this run and says so, rather than replacing the key: a new key would
    make every earlier entry fail verification.
    """
    try:
        from Agent_Guru.security.audit.logger import open_owner_audit_log

        return open_owner_audit_log()
    except Exception as e:
        logger.warning("Audit log kept in memory only for this run (%s)", e)
        return None


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
# Command capture after the wake word
# ---------------------------------------------------------------------------
# Was _capture_command_with_vad here, judging whole 1.5 s chunks; it ran on a
# median 2.06 s after the speaker stopped and could not be tested from main.py.
# Agent_Guru/speech/audio/command_capture.py explains the replacement.
from Agent_Guru.speech.audio.command_capture import capture_command, load_silero  # noqa: E402


async def _answer_follow_ups(
    orch: Any,
    result: Any,
    listen: Any,
    make_event: Any,
    before_turn: Any = lambda: None,
    max_answers: int = 4,
) -> Any:
    """Listen for the answer when a reply asked for one, without a wake word.

    A message draft asks "What would you like me to send John?" and then
    reads the message back. Without this the user had to say the wake word
    before each answer, three times for one message. A turn whose result is
    awaiting_reply is followed by one more capture; silence ends it (the
    question stays open until the draft expires, and can still be answered
    after the wake word), and at most max_answers answers are taken.
    """
    answers = 0
    while getattr(result, "awaiting_reply", False) and answers < max_answers:
        logger.info("Listening for your answer...")
        audio = await listen()
        if not audio:
            logger.info("No answer heard - say the wake word to answer later.")
            break
        before_turn()
        result = await orch.run_pipeline(make_event(audio))
        answers += 1
    return result


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
    mcp_servers = _load_mcp_servers()
    policy     = _load_policy(mcp_servers)
    avatar     = _load_avatar()
    deployment = _load_deployment()
    gpu_pool   = _load_gpu_pool()
    trace_store = _load_trace_store()
    audit_logger = _load_audit_logger()
    document_store = _load_document_store()
    # The assistant's own research tools (web, documents, memory), served
    # in process through the same toolbox and policy as MCP servers. Off
    # with AGENT_GURU_RESEARCH=0.
    if os.environ.get("AGENT_GURU_RESEARCH", "1").strip().lower() not in {"0", "false", "no", "off"}:
        try:
            from Agent_Guru.integration.mcp_tools import install_mcp_policies
            from Agent_Guru.integration.research import ResearchTools, research_server

            research = research_server()
            research.local = ResearchTools(documents=document_store, memory=memory)
            mcp_servers = [*mcp_servers, research]
            install_mcp_policies(policy, [research])
        except Exception as e:
            logger.warning("Research tools unavailable (%s)", e)
    from Agent_Guru.utils.path_utils import app_data_dir
    # Pending reminders are kept here between runs; one missed while the app
    # was off is said on the next start, with how late it is.
    reminder_store = app_data_dir("reminders.json")
    learn_facts = os.environ.get("AGENT_GURU_LEARN_FACTS", "1").strip().lower() not in {"0", "false", "no", "off"}

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
        trace_store=trace_store,
        audit_logger=audit_logger,
        reminder_store=reminder_store,
        learn_facts=learn_facts,
        document_store=document_store,
        mcp_servers=mcp_servers,
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
    await asyncio.get_running_loop().run_in_executor(None, load_silero)

    logger.info("Pre-warming Whisper tiny for wake word detection...")
    _whisper_tiny_global: Any = None
    try:
        import numpy as np
        from faster_whisper import WhisperModel

        from Agent_Guru.speech.stt.whisper_stt import cuda_trial, prepare_cuda_runtime

        def _load_whisper_tiny(device: str, compute_type: str) -> WhisperModel:
            """Load Whisper tiny, preferring local cache to avoid HuggingFace calls."""
            try:
                return WhisperModel("tiny", device=device, compute_type=compute_type, local_files_only=True)
            except Exception:
                return WhisperModel("tiny", device=device, compute_type=compute_type)

        # Try GPU (int8) first - 10x faster than CPU, safe on Windows with CTranslate2
        # Fall back to CPU float32 if CUDA is unavailable or has DLL issues
        # Gated on torch.cuda.is_available() before, which a clean install's
        # CPU-only torch always answers False, so this never tried the GPU
        # even with a working one. CTranslate2 runs Whisper, so ask it; the
        # trial transcription below still decides whether the GPU works.
        _ww_device = "cpu"
        _ww_compute = "float32"
        if prepare_cuda_runtime():
            try:
                # cuda_trial() records a failure for the whole process: after
                # one failed CUDA attempt a second one hangs, and the command
                # transcriber would otherwise make it on the first command.
                with cuda_trial():
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
            audio_bytes = await capture_command(wake_manager)

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

        def _thinking_tone() -> None:
            # Play a short "thinking" tone so the user knows we heard them
            # and are processing - prevents them thinking it's broken during LLM wait
            try:
                import numpy as _np_beep

                # Under the process-wide PortAudio lock, like all playback: the
                # mic recovery path used to re-initialise PortAudio from another
                # thread mid-playback, which cut audio off or crashed the process.
                from Agent_Guru.speech.audio.portaudio_lock import play_and_wait
                _sr = 22050
                _t = _np_beep.linspace(0, 0.15, int(_sr * 0.15), False)
                _beep = (_np_beep.sin(2 * _np_beep.pi * 880 * _t) * 0.3).astype(_np_beep.float32)
                _fade = _np_beep.linspace(1, 0, len(_beep))
                play_and_wait(_beep * _fade, _sr)
            except Exception:
                pass

        try:
            event = WakeWordEvent(wake_word=detection.wake_word, audio=audio_bytes)
            _thinking_tone()
            result = await orch.run_pipeline(event)
            result = await _answer_follow_ups(
                orch, result,
                listen=lambda: capture_command(wake_manager),
                make_event=lambda audio: WakeWordEvent(wake_word=detection.wake_word, audio=audio),
                before_turn=_thinking_tone,
            )

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

    # This used to log "Calibrating microphone (3s)" and then only sleep. The
    # mic was never read and the threshold printed afterwards was the shipped
    # default on every machine, so the line sent anyone debugging a quiet mic
    # looking at a calibration that never happened. It now measures the room
    # and logs what it found.
    calibration = await wake_manager.calibrate_noise_floor(3.0)
    if calibration is not None and calibration.rejected:
        # Not a noise floor: talking or music during the 3 s. Calling it one
        # (as this line did, "noise floor rms=0.15609") misreports what was
        # heard; the manager has already told the user what to do about it.
        logger.info(
            "Microphone not calibrated: the room was as loud as speech (level %.3f); "
            "default wake threshold %.4f kept, room re-measured while listening",
            calibration.noise_rms, calibration.threshold_after,
        )
    elif calibration is not None:
        logger.info(
            "Microphone calibrated over %.1fs: noise floor rms=%.5f, peak=%.4f, "
            "wake threshold %.4f%s",
            calibration.seconds, calibration.noise_rms, calibration.peak,
            calibration.threshold_after,
            ""
            if calibration.threshold_after == calibration.threshold_before
            else f" (raised from {calibration.threshold_before:.4f} for a noisy room)",
        )
    else:
        logger.warning("Microphone not calibrated: no working input device yet")
    await wake_manager.start_listening()
    logger.info("Microphone open - listening for wake words.")

    logger.info("[OK] Agent Guru is running.")
    logger.info("  GPU device  : %s", gpu_pool.device)
    if gpu_pool.device == "cuda":
        total_gb = gpu_pool.total_vram / (1024 ** 3)
        logger.info("  Total VRAM  : %.1f GB", total_gb)
    else:
        # Was "CPU-only (no CUDA GPU detected)", read from the torch-based pool:
        # false with PyPI's CPU-only torch on a machine with a GPU, printed right
        # under the pool's own line saying a CUDA device is present.
        logger.info("  Mode        : CPU for torch features (reason in the GPUResourcePool line)")
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

    # MCP servers are child processes; each is ended with what it started.
    try:
        await orch.close_tools()
    except Exception as e:
        logger.warning("Closing MCP servers failed: %s", e)

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

def main() -> None:
    """Run the assistant, restarting it after a crash with exponential backoff.

    This loop used to sit under ``if __name__ == "__main__"``, so only
    ``python main.py`` had it. ``python -m Agent_Guru`` and the
    ``agent-guru`` console script import ``main`` from this file, which did
    not exist, and both failed at once with "cannot import name 'main'".
    """
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


if __name__ == "__main__":
    main()
