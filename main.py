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
import signal
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("guru.main")


# ---------------------------------------------------------------------------
# Subsystem imports — each wrapped so a missing dep logs clearly and raises
# ---------------------------------------------------------------------------

def _load_speech():
    try:
        from Agent_Guru.speech.engine import SpeechEngine
        return SpeechEngine()
    except Exception as e:
        logger.error("SpeechEngine failed to load: %s", e)
        return _stub("speech_engine", critical=True)


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
        return _stub("llm_runtime", critical=True)


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
    from Agent_Guru.integration.gpu_pool import GPUResourcePool
    return GPUResourcePool()


# ---------------------------------------------------------------------------
# Main async startup
# ---------------------------------------------------------------------------

async def run() -> None:
    from Agent_Guru.integration import IntegrationOrchestrator, WakeWordEvent
    from Agent_Guru.speech.wake_word_manager import WakeWordManager, WakeWordManagerConfig
    from Agent_Guru.speech.audio.wake_word import WakeWordConfig
    from Agent_Guru.speech.models import PersonalityType

    print()
    print("=" * 44)
    print("         Agent Guru  v0.1.0              ")
    print("  Say 'Hey Guru' or 'Hey Maya' to start  ")
    print("=" * 44)
    print()

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

    # --- Define pipeline callback BEFORE starting the listener ---
    async def _on_wake_word(detection) -> None:
        """Called by WakeWordManager when a real wake word is detected."""
        personality_name = detection.personality.value.upper()
        logger.info("Wake word: '%s' → %s", detection.wake_word, personality_name)
        print(f"\n  [{personality_name}] Listening for your command...")

        # Capture ~3 seconds of command audio after the wake word
        import numpy as np
        try:
            if wake_manager._audio_capture is not None:
                chunks = []
                # 2 chunks × 1.5s = 3s of command audio
                for _ in range(2):
                    chunk = await asyncio.get_event_loop().run_in_executor(
                        None, wake_manager._audio_capture.capture
                    )
                    chunks.append(chunk)
                command_audio = np.concatenate(chunks)
                audio_bytes = command_audio.astype(np.float32).tobytes()
                rms = float(np.sqrt(np.mean(command_audio ** 2)))
                logger.info(
                    "Command audio captured: %.2fs, rms=%.4f",
                    len(command_audio) / 16000, rms
                )
            else:
                audio_bytes = b""
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
        energy_threshold=0.015,  # calibrated: silence ~0.0001, speech ~0.018-0.038
        cooldown_seconds=2.0,     # 2s between detections
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
    # Brief warmup — lets the energy buffer stabilise so the first few
    # noise frames don't immediately trigger a false detection
    await asyncio.sleep(1.5)
    await wake_manager.start_listening()
    logger.info("Microphone open — listening for wake words.")

    print()
    print("[OK] Agent Guru is running.")
    print("  GPU device  :", gpu_pool.device)
    if gpu_pool.device == "cuda":
        total_gb = gpu_pool.total_vram / (1024 ** 3)
        print(f"  Total VRAM  : {total_gb:.1f} GB")
    else:
        print("  Mode        : CPU-only (no CUDA GPU detected)")
    print()
    print("  Listening for 'Hey Guru' or 'Hey Maya'...")
    print("  Press Ctrl+C to stop.")
    print()

    # --- Graceful shutdown on SIGINT/SIGTERM ---
    stop_event = asyncio.Event()

    def _handle_signal(*_):
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            signal.signal(sig, _handle_signal)

    # Keep running until interrupted
    await stop_event.wait()

    # --- Shutdown ---
    print()
    logger.info("Shutting down Agent Guru...")
    await wake_manager.stop_listening()
    await orch.sleep()

    if hasattr(speech, "shutdown") and callable(speech.shutdown):
        try:
            speech.shutdown()
        except Exception:
            pass

    print("Agent Guru stopped. Goodbye.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
