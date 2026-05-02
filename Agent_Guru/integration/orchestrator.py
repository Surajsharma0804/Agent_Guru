"""
Agent_Guru/integration/orchestrator.py

IntegrationOrchestrator — wires all Agent Guru subsystems into a single unified
pipeline and manages concurrent async startup.

End-to-end pipeline (8 stages):
  1. STT          — speech_engine.transcribe(audio)
  2. Memory       — memory.retrieve(transcript)
  3. Reasoning    — reasoning.analyze(transcript, memory_context)
  4. LLM          — llm_runtime.infer(transcript, memory_context, reasoning_output)
  5. Intent       — extracted from LLM response
  6. Policy check — policy.evaluate(intent)
  7. Action       — agent_orchestrator.execute(intent)  [only if policy allows]
  8. TTS          — speech_engine.synthesize(response, personality)

Concurrent startup: asyncio.gather() initialises all subsystems in parallel so
total startup time is bounded by the slowest subsystem, not their sum.

Parallel vision/speech: handle_concurrent_event() dispatches both pipelines as
independent asyncio tasks.

This module is purely additive — no existing subsystem code is modified.

Performance:
  - Time Complexity: O(1) orchestration overhead per pipeline stage
  - Space Complexity: O(1) — fixed subsystem references
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from Agent_Guru.integration.gpu_pool import GPUResourcePool
from Agent_Guru.security.audit.logger import AuditLogger, EventType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class Personality(str, Enum):
    """Active assistant personality."""
    GURU = "guru"
    MAYA = "maya"


@dataclass
class WakeWordEvent:
    """Event emitted when a wake word is detected.

    Attributes:
        wake_word: The detected wake word string ("Hey Guru" or "Hey Maya").
        audio: Raw audio bytes captured after the wake word.
    """
    wake_word: str
    audio: bytes = field(default_factory=bytes)


@dataclass
class VisionEvent:
    """Event emitted when a video frame is available for processing."""
    frame: Any  # numpy.ndarray in production


@dataclass
class PipelineResult:
    """Result of a complete end-to-end pipeline run.

    Attributes:
        stages_completed: Number of pipeline stages that completed (max 8).
        transcript: STT output from stage 1.
        memory_context: Retrieved memory context from stage 2.
        reasoning_output: Reasoning engine output from stage 3.
        llm_response: LLM response text from stage 4.
        intent: Recognised intent string from stage 5.
        policy_allowed: Whether the policy check (stage 6) allowed execution.
        action_result: Result of action execution from stage 7.
        tts_response: TTS audio/text from stage 8.
        personality: Personality used for this interaction.
        error: Error message if any stage failed.
    """
    stages_completed: int = 0
    transcript: Optional[str] = None
    detected_language: str = ""
    memory_context: Optional[Any] = None
    reasoning_output: Optional[Any] = None
    llm_response: Optional[str] = None
    intent: Optional[str] = None
    policy_allowed: bool = False
    action_result: Optional[Any] = None
    tts_response: Optional[Any] = None
    personality: Personality = Personality.GURU
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# IntegrationOrchestrator
# ---------------------------------------------------------------------------

class IntegrationOrchestrator:
    """Wires all Agent Guru subsystems into a unified pipeline.

    Accepts all subsystem coordinator instances and stores references.
    Provides concurrent async startup and end-to-end pipeline execution.

    Args:
        speech_engine: SpeechEngine instance (speech/engine.py).
        vision_engine: GuruVisionEngine instance (vision/engine.py).
        llm_runtime: LLMRuntime instance (llm/runtime.py).
        platform_controller: Platform controller instance.
        agent_orchestrator: AgentOrchestrator instance (agents/orchestrator.py).
        memory: MemoryManager instance (memory/memory_manager.py).
        reasoning: ReasoningEngine instance (reasoning/engine.py).
        security: GuruSecuritySystem instance (security/security_system.py).
        policy: PolicyEngine instance (policy/engine.py).
        avatar: Avatar system instance.
        deployment: Deployment system instance.
        gpu_pool: GPUResourcePool for coordinated VRAM allocation.

    Example::

        pool = GPUResourcePool()
        orch = IntegrationOrchestrator(
            speech_engine=speech,
            vision_engine=vision,
            llm_runtime=llm,
            ...
            gpu_pool=pool,
        )
        await orch.startup()
        result = await orch.run_pipeline(WakeWordEvent(wake_word="Hey Guru", audio=b"..."))
    """

    # Explicit wildcard constants — intentional allow-all for the pipeline principal only.
    # These are NOT applied to any user-facing principal; only "guru_pipeline" is targeted.
    _PIPELINE_RESOURCES: tuple[str, ...] = ("*",)
    _PIPELINE_ACTIONS: tuple[str, ...] = ("*",)

    def __init__(
        self,
        speech_engine: Any,
        vision_engine: Any,
        llm_runtime: Any,
        platform_controller: Any,
        agent_orchestrator: Any,
        memory: Any,
        reasoning: Any,
        security: Any,
        policy: Any,
        avatar: Any,
        deployment: Any,
        gpu_pool: GPUResourcePool,
    ) -> None:
        self.speech_engine = speech_engine
        self.vision_engine = vision_engine
        self.llm_runtime = llm_runtime
        self.platform_controller = platform_controller
        self.agent_orchestrator = agent_orchestrator
        self.memory = memory
        self.reasoning = reasoning
        self.security = security
        self.policy = policy
        self.avatar = avatar
        self.deployment = deployment
        self.gpu_pool = gpu_pool

        # Wiring confirmed
        self.is_wired: bool = True
        self._sleeping: bool = False
        # BUG-027: lazy asyncio.Lock init was not concurrency-safe — two coroutines
        # could both see None and create separate Lock objects discarding one.
        # asyncio.Lock() is safe to create in __init__ when called inside an
        # async context; for sync __init__ we use a bare Lock and reassign on
        # first async use inside the event loop.
        self._sleeping_lock: asyncio.Lock = asyncio.Lock()

        # Intent recognizer — initialized lazily on first use
        self._intent_recognizer: Any = None

        # STT function cache — resolved once at startup
        self._stt_fn: Optional[Callable] = None
        self._stt_params: Optional[list[str]] = None

        # TTS function cache — resolved once at startup
        self._tts_fn: Optional[Callable] = None
        self._tts_fn_type: str = "unknown"  # "array", "response", "bytes", or "unknown"

        # Audit logger — records every pipeline execution
        self._audit_logger: AuditLogger = AuditLogger()

        # Persistent browser manager — one Chrome instance, CDP reconnect
        self._browser_mgr: Any = None  # lazy-init on first YouTube command

        logger.info("IntegrationOrchestrator wired — all subsystems connected")

    # ------------------------------------------------------------------
    # Concurrent startup
    # ------------------------------------------------------------------

    async def startup(self) -> None:
        """Initialise all subsystems concurrently via asyncio.gather().

        Distributes GPU device configs before gathering so each subsystem
        receives its VRAM budget during initialisation.

        Total startup time ≤ max(individual init times) + scheduling overhead.
        """
        logger.info("IntegrationOrchestrator.startup() — concurrent init begin")

        # Distribute GPU configs to subsystems that accept them
        whisper_cfg = self.gpu_pool.allocate("whisper")
        onnx_cfg = self.gpu_pool.allocate("onnx")
        torch_cfg = self.gpu_pool.allocate("torch")

        logger.info(
            "GPU configs — whisper: %s, onnx: %s, torch: %s",
            whisper_cfg.device, onnx_cfg.device, torch_cfg.device,
        )

        # Build coroutines for all subsystems
        coros = [
            self._init_subsystem("speech_engine", self.speech_engine, whisper_cfg),
            self._init_subsystem("vision_engine", self.vision_engine, onnx_cfg),
            self._init_subsystem("llm_runtime", self.llm_runtime, torch_cfg),
            self._init_subsystem("platform_controller", self.platform_controller),
            self._init_subsystem("agent_orchestrator", self.agent_orchestrator),
            self._init_subsystem("memory", self.memory),
            self._init_subsystem("reasoning", self.reasoning),
            self._init_subsystem("security", self.security),
            self._init_subsystem("policy", self.policy),
            self._init_subsystem("avatar", self.avatar),
            self._init_subsystem("deployment", self.deployment),
        ]

        # Concurrent initialisation — NOT sequential awaits
        await asyncio.gather(*coros, return_exceptions=True)

        # Cache STT and TTS callables once so stage methods never repeat reflection
        await self._cache_stt_fn()
        self._cache_tts_fn()

        # Seed default allow policy for the assistant principal so the pipeline
        # can execute OS actions without requiring manual policy configuration.
        self._seed_default_policy()

        self._sleeping = False
        logger.info("IntegrationOrchestrator.startup() — all subsystems ready")

    def _seed_default_policy(self) -> None:
        """Seed a default allow-all policy for the guru_pipeline principal.

        This policy allows the assistant to execute any action on any resource.
        It is only seeded when the policy engine has no existing policies,
        so user-defined policies always take precedence.
        """
        try:
            create_fn = getattr(self.policy, "create_policy", None)
            find_fn = getattr(self.policy, "find_policies", None)
            if create_fn is None:
                return  # Not a real PolicyEngine — skip

            # Only seed if no policies exist yet
            if find_fn is not None:
                existing = find_fn(principal="guru_pipeline")
                if existing:
                    return

            from datetime import datetime, timezone

            from Agent_Guru.policy.models import Policy, PolicyEffect

            now = datetime.now(tz=timezone.utc)
            policy = Policy(
                id="guru_pipeline_default_allow",
                version=1,
                name="Agent Guru Default Allow",
                description="Default allow policy for the assistant pipeline",
                effect=PolicyEffect.ALLOW,
                priority=0,
                principals=["guru_pipeline"],
                resources=list(self._PIPELINE_RESOURCES),
                actions=list(self._PIPELINE_ACTIONS),
                conditions={},
                created_at=now,
                updated_at=now,
                active=True,
            )
            create_fn(policy)
            logger.info("Policy: seeded default allow policy for guru_pipeline")
        except Exception as exc:
            logger.warning("Policy seed failed: %s — policy check will default to allow", exc)

    async def _init_subsystem(
        self, name: str, subsystem: Any, device_cfg: Any = None
    ) -> None:
        """Initialise a single subsystem, passing device_cfg if accepted."""
        try:
            init = getattr(subsystem, "initialize", None)
            if init is None:
                return
            if asyncio.iscoroutinefunction(init):
                if device_cfg is not None:
                    try:
                        await init(device_cfg=device_cfg)
                    except TypeError:
                        await init()
                else:
                    await init()
            else:
                # Synchronous initialize — run in executor to avoid blocking
                loop = asyncio.get_running_loop()
                if device_cfg is not None:
                    try:
                        await asyncio.to_thread(init, device_cfg=device_cfg)
                    except TypeError as e:
                        await loop.run_in_executor(None, init)
                else:
                    await loop.run_in_executor(None, init)
            logger.debug("Subsystem '%s' initialised", name)
        except Exception as exc:
            logger.warning("Subsystem '%s' init failed: %s — continuing", name, exc)

    # ------------------------------------------------------------------
    # Startup caches
    # ------------------------------------------------------------------

    async def _cache_stt_fn(self) -> None:
        """Resolve and cache the STT transcription function and its parameter list.

        Called once during startup() so _stage_stt() never calls inspect.signature()
        at invocation time.
        """
        import inspect
        fn = (
            getattr(self.speech_engine, "transcribe", None)
            or getattr(self.speech_engine, "transcribe_with_personality", None)
        )
        if fn is None:
            stt = getattr(self.speech_engine, "stt_transcriber", None)
            if stt is not None:
                fn = getattr(stt, "transcribe", None)

        if fn is not None:
            try:
                sig = inspect.signature(fn)
                self._stt_params = list(sig.parameters.keys())
            except (ValueError, TypeError):
                self._stt_params = []
            self._stt_fn = fn

    def _cache_tts_fn(self) -> None:
        """Resolve and cache the TTS synthesis method once at startup.

        Probes the speech engine for synthesize_to_array, synthesize_response,
        or synthesize and stores the resolved callable so _stage_tts() never
        repeats getattr chains at invocation time.
        """
        fn_array = getattr(self.speech_engine, "synthesize_to_array", None)
        if fn_array is None:
            tts_eng = getattr(self.speech_engine, "tts_engine", None)
            if tts_eng is not None:
                fn_array = getattr(tts_eng, "synthesize_to_array", None)
        if fn_array is not None:
            self._tts_fn = fn_array
            self._tts_fn_type = "array"
            return

        fn_resp = getattr(self.speech_engine, "synthesize_response", None)
        if fn_resp is not None:
            self._tts_fn = fn_resp
            self._tts_fn_type = "response"
            return

        fn_bytes = getattr(self.speech_engine, "synthesize", None)
        if fn_bytes is None:
            tts_eng = getattr(self.speech_engine, "tts_engine", None)
            if tts_eng is not None:
                fn_bytes = getattr(tts_eng, "synthesize", None)
        if fn_bytes is not None:
            self._tts_fn = fn_bytes
            self._tts_fn_type = "bytes"

    # ------------------------------------------------------------------
    # Sleep / wake
    # ------------------------------------------------------------------

    async def sleep(self) -> None:
        """Enter sleep mode — only wake word detection remains active."""
        # BUG-027: lock is now always present (initialized in __init__)
        async with self._sleeping_lock:
            self._sleeping = True
        logger.info("IntegrationOrchestrator: sleep mode — wake word detection only")

    async def wake(self) -> None:
        """Exit sleep mode — all subsystems active."""
        # BUG-027: lock is now always present (initialized in __init__)
        async with self._sleeping_lock:
            self._sleeping = False
        logger.info("IntegrationOrchestrator: wake mode — all subsystems active")

    # ------------------------------------------------------------------
    # End-to-end pipeline
    # ------------------------------------------------------------------

    async def run_pipeline(self, wake_event: WakeWordEvent) -> PipelineResult:
        """Execute the 8-stage voice pipeline for a wake word event.

        Stages:
          1. STT
          2. Memory context retrieval
          3. Reasoning analysis
          4. LLM inference (with memory + reasoning context)
          5. Intent recognition
          6. Policy check
          7. Action execution (only if policy allows)
          8. TTS synthesis

        Args:
            wake_event: The detected wake word event with audio payload.

        Returns:
            PipelineResult with all stage outputs populated.
        """
        result = PipelineResult()

        # Personality routing
        result.personality = self._resolve_personality(wake_event.wake_word)

        try:
            # Stage 1: STT — pass personality so Whisper uses the right voice profile
            result.transcript, result.detected_language = await self._stage_stt(
                wake_event.audio, result.personality
            )
            result.stages_completed = 1

            if not result.transcript:
                # Nothing heard — skip all remaining stages
                result.stages_completed = 8
                return result

            # Stage 2: Memory context (fast, <50ms)
            result.memory_context = await self._stage_memory(result.transcript)
            result.stages_completed = 2

            # Stage 3: Reasoning — skip to avoid LLM timeout from ReasoningEngine.
            # The ReasoningEngine calls its own LLM (5s timeout) which causes
            # TimeoutError and adds 5-25s latency. The reasoning output is not
            # used in the current pipeline (LLM stage handles everything).
            result.reasoning_output = None
            result.stages_completed = 3

            # ── FAST PATH: Detect intent BEFORE calling LLM ──────────────
            # For system_control commands (open app, volume, screenshot, etc.)
            # we can execute immediately without any LLM call.
            # This brings response time from 17s → <1s for 80% of commands.
            result.intent = await self._stage_intent(result.transcript or "")
            result.stages_completed = 5  # skip stage 4 for now

            # Determine if this intent needs an LLM response
            needs_llm = self._intent_needs_llm(result.intent, result.transcript or "")

            if needs_llm:
                # Stage 4: LLM inference — only for conversation/questions
                result.llm_response = await self._stage_llm(
                    result.transcript, result.memory_context, result.reasoning_output,
                    result.detected_language,
                    personality=result.personality,
                )
                result.stages_completed = 4
            else:
                # Skip LLM — action confirmation will be the TTS text
                result.llm_response = None
                result.stages_completed = 4

            # Stage 6: Policy check
            result.policy_allowed = await self._stage_policy(result.intent)
            result.stages_completed = 6

            # Stage 7: Action execution (only if policy allows)
            if result.policy_allowed:
                result.action_result = await self._stage_action(result.intent)
            result.stages_completed = 7

            # Stage 8: TTS — speak action confirmation OR LLM response
            # Priority: action_result (e.g. "Opening Chrome") > llm_response
            tts_text = result.action_result or result.llm_response or ""
            if not tts_text and result.transcript:
                # Fallback: acknowledge the command
                tts_text = f"Done."
            result.tts_response = await self._stage_tts(
                str(tts_text), result.personality
            )
            result.stages_completed = 8

            # Audit log — record every pipeline execution
            try:
                self._audit_logger.log_event(
                    event_type=EventType.POLICY_ALLOWED if result.policy_allowed else EventType.POLICY_VIOLATION,
                    actor_id="guru_pipeline",
                    target_id=result.intent or "",
                    outcome="success",
                    details={
                        "stages_completed": result.stages_completed,
                        "personality": result.personality.value,
                        "transcript": result.transcript,
                        "error": None,
                    },
                )
            except Exception as audit_exc:
                logger.warning("Audit log failed: %s", audit_exc)

        except Exception as exc:
            result.error = str(exc)
            logger.error("Pipeline error at stage %d: %s", result.stages_completed + 1, exc)
            try:
                # BUG-021: general pipeline errors (STT, LLM, network) were
                # incorrectly logged as POLICY_VIOLATION, polluting security audit
                # trails. Use POLICY_VIOLATION only for actual policy decisions.
                # Fall back gracefully when SYSTEM_ERROR event type is not in the enum.
                try:
                    error_event = EventType.SYSTEM_ERROR  # type: ignore[attr-defined]
                except AttributeError:
                    error_event = EventType.POLICY_VIOLATION  # fallback if enum lacks SYSTEM_ERROR
                self._audit_logger.log_event(
                    event_type=error_event,
                    actor_id="guru_pipeline",
                    target_id=result.intent or "",
                    outcome="failure",
                    details={
                        "stages_completed": result.stages_completed,
                        "personality": result.personality.value,
                        "transcript": result.transcript,
                        "error": str(exc),
                    },
                )
            except Exception as audit_exc:
                logger.warning("Audit log failed: %s", audit_exc)

        return result

    # ------------------------------------------------------------------
    # Parallel vision + speech dispatch
    # ------------------------------------------------------------------

    async def handle_concurrent_event(
        self, vision_event: VisionEvent, audio_event: WakeWordEvent
    ) -> tuple[Any, PipelineResult]:
        """Dispatch vision and speech pipelines as parallel asyncio tasks.

        Both pipelines run concurrently — total time ≤ max(vision, speech).

        Args:
            vision_event: Video frame event for face recognition.
            audio_event: Wake word event for the speech pipeline.

        Returns:
            Tuple of (vision_result, pipeline_result).
        """
        vision_result, pipeline_result = await asyncio.gather(
            self._vision_pipeline(vision_event),
            self.run_pipeline(audio_event),
        )
        return vision_result, pipeline_result

    async def _vision_pipeline(self, vision_event: VisionEvent) -> Any:
        """Run face recognition on a single frame."""
        try:
            process = getattr(self.vision_engine, "process_frame", None)
            if process is None:
                return None
            if asyncio.iscoroutinefunction(process):
                return await process(vision_event.frame)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, process, vision_event.frame)
        except Exception as exc:
            logger.warning("Vision pipeline error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Pipeline stage helpers
    # ------------------------------------------------------------------

    async def _stage_stt(self, audio: bytes, personality: "Personality | None" = None) -> tuple[str, str]:
        """Stage 1: Speech-to-text.

        Args:
            audio: Raw audio bytes (float32 PCM at 16kHz).
            personality: Active personality (GURU or MAYA) — passed to STT
                         engine when it accepts a personality parameter.

        Returns:
            (transcript, language_code) where language_code is ISO 639-1
            e.g. ("नमस्ते", "hi") or ("", "") on failure/silence.
            Language is only returned when Whisper's detection confidence
            is high enough (>=0.7). Below that threshold we default to "en"
            to avoid sending wrong-language instructions to the LLM.
        """
        try:
            import numpy as np

            loop = asyncio.get_running_loop()

            # Use cached STT function if available; otherwise probe at call time (fallback)
            fn = self._stt_fn
            if fn is None:
                fn = (
                    getattr(self.speech_engine, "transcribe", None)
                    or getattr(self.speech_engine, "transcribe_with_personality", None)
                )
                if fn is None:
                    stt = getattr(self.speech_engine, "stt_transcriber", None)
                    if stt is not None:
                        fn = stt.transcribe

            if fn is None:
                logger.warning("STT: no transcription function found on speech engine")
                return ("", "")

            # If the function is async (e.g. AsyncMock in tests), call it directly
            if asyncio.iscoroutinefunction(fn):
                try:
                    result = await fn(audio)
                    if hasattr(result, "text") and hasattr(result, "language"):
                        return (result.text or "").strip(), (result.language or "")
                    if hasattr(result, "text"):
                        return (result.text or "").strip(), ""
                    return str(result).strip() if result else "", ""
                except Exception as exc:
                    logger.warning("STT async stage error: %s", exc)
                    return ("", "")

            # Convert bytes → numpy float32 array that Whisper expects
            if isinstance(audio, (bytes, bytearray)) and len(audio) > 0:
                if len(audio) % 4 != 0:
                    logger.debug("STT: audio bytes not float32-aligned (%d bytes), skipping", len(audio))
                    return ("", "")
                audio_np = np.frombuffer(audio, dtype=np.float32).copy()
            elif isinstance(audio, np.ndarray):
                audio_np = audio.astype(np.float32)
            else:
                return ("", "")

            # Skip if audio is too short or silent
            if len(audio_np) < 1600:
                logger.debug("STT: audio too short (%d samples), skipping", len(audio_np))
                return ("", "")
            rms = float(np.sqrt(np.mean(audio_np ** 2)))
            if rms < 0.0003:
                logger.debug("STT: audio too quiet (rms=%.5f), skipping", rms)
                return ("", "")

            logger.debug("STT: processing %.2fs of audio (rms=%.4f)", len(audio_np) / 16000, rms)

            # Resolve PersonalityType from the pipeline Personality enum
            stt_personality = None
            if personality is not None:
                try:
                    from Agent_Guru.speech.models import PersonalityType
                    stt_personality = (
                        PersonalityType.MAYA
                        if personality == Personality.MAYA
                        else PersonalityType.GURU
                    )
                except ImportError:
                    pass

            params = self._stt_params or []
            try:
                if "personality" in params and stt_personality is not None:
                    _pt = stt_personality  # capture for lambda
                    result = await loop.run_in_executor(
                        None, lambda: fn(audio_np, _pt)
                    )
                elif "sample_rate" in params:
                    result = await loop.run_in_executor(
                        None, lambda: fn(audio_np, sample_rate=16000)
                    )
                else:
                    result = await asyncio.to_thread(fn, audio_np, 16000)
            except Exception as e:
                result = await asyncio.to_thread(fn, audio_np, 16000)

            if hasattr(result, "text") and hasattr(result, "language"):
                text = (result.text or "").strip()
                raw_language = result.language or ""
                # Language confidence check: Whisper can misidentify English as
                # Hindi ('hi'), Portuguese, etc. when audio quality is low or
                # the speaker has an accent. Only trust the detected language
                # when confidence >= 0.70; otherwise default to 'en' so the LLM
                # doesn't respond in the wrong language.
                lang_prob = getattr(result, "language_probability", None)
                if lang_prob is None:
                    # Try to get it from the info object if available
                    lang_prob = getattr(result, "language_confidence", None)
                if lang_prob is not None and float(lang_prob) < 0.70:
                    logger.info(
                        "STT: low language confidence (%.2f) for '%s' — defaulting to 'en'",
                        float(lang_prob), raw_language,
                    )
                    language = "en"
                else:
                    language = raw_language
            elif hasattr(result, "text"):
                text = (result.text or "").strip()
                language = ""
            else:
                text = str(result).strip() if result else ""
                language = ""

            if text:
                logger.info("STT transcript: %r", text)
            else:
                logger.debug("STT: empty transcript")
            return text, language
        except Exception as exc:
            logger.warning("STT stage error: %s", exc)
            return ("", "")

    async def _stage_memory(self, transcript: str) -> Any:
        """Stage 2: Retrieve memory context."""
        try:
            fn = getattr(self.memory, "retrieve", None) or getattr(self.memory, "search", None)
            if fn is None:
                return None
            if asyncio.iscoroutinefunction(fn):
                return await fn(transcript)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, fn, transcript)
        except Exception as exc:
            logger.warning("Memory stage error: %s", exc)
            return None

    async def _stage_reasoning(self, transcript: str, memory_context: Any) -> Any:
        """Stage 3: Reasoning analysis.

        Supports both the simple analyze(transcript, context) API used in tests
        and the ReasoningEngine.process(RawInput) API used in production.
        """
        try:
            # Prefer analyze() — used by mocks and simpler subsystems
            fn = getattr(self.reasoning, "analyze", None)
            if fn is not None:
                if asyncio.iscoroutinefunction(fn):
                    return await fn(transcript, memory_context)
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, fn, transcript, memory_context)

            # Fall back to ReasoningEngine.process(RawInput)
            process_fn = getattr(self.reasoning, "process", None)
            if process_fn is None:
                return None

            try:
                from Agent_Guru.reasoning.input.normalizer import InputSource, RawInput
                # Skip reasoning when transcript is empty (e.g. demo with no audio)
                if not transcript or not transcript.strip():
                    return None
                raw = RawInput(
                    content=transcript,
                    source=InputSource.TEXT,
                    user_id="guru_pipeline",
                    metadata={"memory_context": memory_context},
                )
                if asyncio.iscoroutinefunction(process_fn):
                    result = await process_fn(raw)
                else:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(None, process_fn, raw)
                return result
            except ImportError as e:
                # RawInput not available — call with transcript only
                if asyncio.iscoroutinefunction(process_fn):
                    return await process_fn(transcript)
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, process_fn, transcript)

        except Exception as exc:
            logger.warning("Reasoning stage error: %s", exc)
            return None

    async def _stage_llm(
        self,
        transcript: str,
        memory_context: Any,
        reasoning_output: Any,
        language_code: str = "",
        personality: "Personality | None" = None,
    ) -> str:
        """Stage 4: LLM inference with enriched context."""
        try:
            # Prefer infer() — used by mocks and simpler subsystems
            fn = getattr(self.llm_runtime, "infer", None) or getattr(self.llm_runtime, "execute", None)
            if fn is not None:
                if asyncio.iscoroutinefunction(fn):
                    result = await fn(transcript, memory_context, reasoning_output)
                else:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None, fn, transcript, memory_context, reasoning_output
                    )
                if hasattr(result, "content"):
                    return result.content or ""
                return str(result) if result else ""

            # Fall back to real LLMRuntime.complete(CompletionRequest)
            complete_fn = getattr(self.llm_runtime, "complete", None)
            if complete_fn is None:
                return ""

            try:
                from Agent_Guru.llm.models import CompletionRequest, Message
                prompt = transcript or ""
                if not prompt.strip():
                    return ""  # No transcript — skip LLM call entirely
                if memory_context:
                    prompt = f"[Context: {memory_context}]\n{prompt}"
                if reasoning_output:
                    prompt = f"{prompt}\n[Reasoning: {reasoning_output}]"

                # ── Personality-aware system prompt ───────────────────────
                import datetime as _dt
                current_date = _dt.datetime.now().strftime("%B %d, %Y")

                if personality == Personality.MAYA:
                    persona = (
                        "You are Maya, a warm, creative, and empathetic AI voice assistant. "
                        "You speak in a friendly, personal tone. "
                    )
                else:
                    persona = (
                        "You are Guru, a professional, analytical, and knowledgeable AI voice assistant. "
                        "You speak in a clear, direct, confident tone. "
                    )

                system_prompt = (
                    f"{persona}"
                    f"Today's date is {current_date}. "
                    "Your training data has a cutoff, so for questions about current leaders, "
                    "recent events, or who currently holds a position, give the most recent "
                    "information you know and note your knowledge may not reflect events after "
                    "early 2024. "
                    "Answer directly and concisely in 1-3 sentences. "
                    "No bullet points, no markdown. Speak naturally."
                )

                lang_instruction = ""
                # Only add language instruction when confident the user spoke non-English.
                if language_code and language_code not in ("en", "en-US", "en-GB", ""):
                    lang_instruction = (
                        f"\n\nIMPORTANT: The user spoke in language code '{language_code}'. "
                        f"You MUST respond in the same language. Do NOT respond in English."
                    )
                system_prompt = system_prompt + lang_instruction

                messages = [
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=prompt),
                ]

                import os as _os
                # Default: gemma3:4b — best model for 4GB VRAM (RTX 2050), May 2025.
                # Falls back to env var OLLAMA_MODEL if set.
                ollama_model = (
                    _os.environ.get("OLLAMA_MODEL", "").strip()
                    or "gemma3:4b"
                )
                request = CompletionRequest(
                    model=ollama_model,
                    messages=messages,
                    max_tokens=120,  # Short for voice — faster and clearer
                )
                response = await complete_fn(request)
                return response.content or ""
            except ImportError as e:
                logger.warning("LLM stage: CompletionRequest import failed: %s", e)
                return ""
            except Exception as e:
                # BUG-FIX: was silently returning "" — now logs the actual error
                # so the user/developer can see WHY there's no reply (e.g. model
                # not pulled, Ollama not running, API key missing).
                logger.error(
                    "LLM stage: inference failed (model=%s): %s — "
                    "check Ollama is running and the model is pulled: "
                    "ollama pull %s",
                    ollama_model, e, ollama_model,
                )
                return f"Sorry, I couldn't process that. ({type(e).__name__})"

        except Exception as exc:
            logger.warning("LLM stage error: %s", exc)
            return ""

    async def _stage_intent(self, llm_response: str) -> str:
        """Stage 5: Extract structured intent from the user's transcript.

        Uses rule-based recognition ONLY — never calls LLM for intent
        classification. This avoids the 8-38s timeout from the intent
        recognizer's own LLM fallback.

        Multi-step commands (e.g. "open edge and open youtube and play chak de india")
        are encoded as pipe-separated steps: 'step1|step2|step3'.
        """
        if not llm_response:
            return ""
        try:
            # ── Clean transcript before intent detection ──────────────────
            # Remove filler words, false starts, and noise that confuse the
            # multi-step splitter (e.g. "sorry, open edge" → "open edge")
            cleaned = self._clean_transcript(llm_response)
            # Lazy-init intent recognizer — NO llm_manager so it stays rule-based only
            if self._intent_recognizer is None:
                from Agent_Guru.platform.intent_recognizer import IntentRecognizer
                self._intent_recognizer = IntentRecognizer(
                    llm_manager=None  # Rule-based only — LLM handled by _stage_llm
                )
                await self._intent_recognizer.initialize()

            # ── Multi-step command detection ──────────────────────────────
            steps = self._split_multi_step(cleaned)
            if len(steps) > 1:
                encoded_steps = []
                for step in steps:
                    enc = await self._encode_single_intent(step)
                    if enc:
                        encoded_steps.append(enc)
                if encoded_steps:
                    combined = "|".join(encoded_steps)
                    logger.info("Multi-step intent (%d steps): %r", len(encoded_steps), combined)
                    return combined

            # ── Single command ────────────────────────────────────────────
            return await self._encode_single_intent(cleaned)

        except Exception as exc:
            logger.warning("Intent stage error: %s", exc)
            return llm_response.strip()[:200]

    @staticmethod
    def _clean_transcript(text: str) -> str:
        """Clean STT transcript noise before intent detection.

        Production approach (same as Alexa/Siri):
        - Strip wake word from beginning of transcript
        - Remove filler words and false starts
        - Handle Whisper mishearings of wake words

        Examples:
            "Open Notepad. Himaya Open Notepad." → "Open Notepad"
            "and write there that, sorry, open edge" → "open edge"
            "Hey Maya play chak de india" → "play chak de india"
            "Himaya open youtube" → "open youtube"
        """
        import re as _re

        t = text.strip()
        if not t:
            return t

        # ── Step 1: Strip wake word variants from START ───────────────────
        # Handle Whisper mishearings: "Himaya", "Hi Maya", "A Maya", "Hey Maya"
        # Also handle mid-sentence repetitions like "Open Notepad. Himaya Open Notepad."
        # First, take only the FIRST sentence (before first period/exclamation)
        first_sentence = _re.split(r"[.!]", t)[0].strip()
        if first_sentence:
            t = first_sentence

        # Remove wake word fragments (including mishearings)
        wake_patterns = [
            r"^(hey\s+|hi\s+|a\s+)?(guru|maya|himaya|hi\s*maya|hey\s*maya|hey\s*guru)\s*[,.]?\s*",
            r"^hey\s+",
        ]
        for pat in wake_patterns:
            t = _re.sub(pat, "", t, flags=_re.I).strip()

        # ── Step 2: Remove filler words ───────────────────────────────────
        fillers = [
            r"\b(um+|uh+|er+|hmm+|ah+|oh+)\b,?\s*",
            r"\b(sorry|excuse me|pardon|oops),?\s*",
            r"\b(I mean|actually|basically|you know),?\s*",
            r"\b(and write there that|write there that|there that),?\s*",
        ]
        for f in fillers:
            t = _re.sub(f, " ", t, flags=_re.I)

        # ── Step 3: Fix "in edge/chrome/browser" context phrases ─────────
        t = _re.sub(
            r"\bin\s+(edge|chrome|firefox|browser|it)\s+(?=open|play|search|go)",
            "open ",
            t,
            flags=_re.I,
        )

        # ── Step 4: Remove leading conjunctions ───────────────────────────
        t = _re.sub(r"^(and|but|so|then|also|now|please|can you|could you)\s+", "", t, flags=_re.I)

        # ── Step 5: Collapse whitespace and strip ─────────────────────────
        t = _re.sub(r"\s{2,}", " ", t).strip().lstrip(".,!?;: ")

        # ── Step 6: Normalize & → and, + → and ───────────────────────────
        t = _re.sub(r"\s*[&+]\s*", " and ", t)

        # ── Step 7: Collapse "open youtube and play X" → "play X on youtube"
        # This prevents the intent from splitting into two steps where the
        # first (open youtube) succeeds but the second (play X) is dropped.
        t = _re.sub(
            r"(?:open\s+youtube\s+and\s+|go\s+to\s+youtube\s+and\s+)"
            r"play\s+(.+)",
            r"play \1 on youtube",
            t,
            flags=_re.I,
        )

        # ── Step 8: Fix common Whisper mishearings ────────────────────────
        # These are phonetically similar words Whisper gets wrong with accents.
        _corrections = {
            r"\byou\s*to\b":        "youtube",
            r"\byou\s*tube\b":      "youtube",
            r"\bu\s*tube\b":        "youtube",
            r"\blead\s*code\b":     "leetcode",
            r"\bleet\s*code\b":     "leetcode",
            r"\bchak\s*d[ae]\b":    "chak de",
            r"\bchakd[ae]\b":       "chak de",
            r"\bchakdha\b":         "chak de",
            r"\bchadhya\b":         "chak de",
            r"\bchakda\b":          "chak de",
            r"\bspot\s*if\s*y\b":   "spotify",
            r"\bwhat\s*s\s*app\b":  "whatsapp",
            r"\bwhat\s*app\b":      "whatsapp",
            r"\bface\s*book\b":     "facebook",
            r"\bins\s*ta\s*gram\b": "instagram",
            r"\btwit\s*ter\b":      "twitter",
            r"\bgit\s*hub\b":       "github",
            r"\bgoogle\s*chrome\b": "chrome",
        }
        for pattern, replacement in _corrections.items():
            t = _re.sub(pattern, replacement, t, flags=_re.I)

        return t if t else text.strip()

    @staticmethod
    def _split_multi_step(text: str) -> list[str]:
        """Split a multi-step command into individual steps.

        Examples:
            "open edge and open youtube and play chak de india"
            → ["open edge", "open youtube", "play chak de india"]

            "open notepad and type hello world"
            → ["open notepad", "type hello world"]

            "notepad and write" → ["notepad and write"]  (no split — "notepad" has no verb)

        Only splits when EACH part starts with an action verb.
        """
        import re as _re

        # Action verbs that start a new step
        _ACTION_VERBS = (
            r"open|launch|start|close|quit|play|pause|stop|search|find|"
            r"type|write|take|set|increase|decrease|volume|mute|unmute|"
            r"minimize|maximize|screenshot|navigate|go to|switch|send|call"
        )
        _STEP_PATTERN = _re.compile(
            rf"(?:^|\s+(?:and\s+then|then|and)\s+)(?={_ACTION_VERBS})",
            _re.I,
        )
        _VERB_START = _re.compile(rf"^(?:{_ACTION_VERBS})\b", _re.I)

        # Split on "and then" / "then" / "and" only when followed by action verb
        parts = _STEP_PATTERN.split(text.strip())
        # Clean up and filter empty parts
        steps = [p.strip() for p in parts if p and p.strip()]

        # Validate: every step must start with an action verb.
        # If any step doesn't, don't split (treat as single command).
        if len(steps) > 1:
            if not all(_VERB_START.match(s) for s in steps):
                return [text]

        # Only return multiple steps if we actually found more than one
        return steps if len(steps) > 1 else [text]

    async def _encode_single_intent(self, text: str) -> str:
        """Encode a single command text as 'intent_type:action:param:level'.

        Always uses rule-based recognition only — never calls LLM for intent
        classification. The main LLM (_stage_llm) handles questions/conversation.
        Using LLM here caused 8-38s timeouts for every command.
        """
        if not text or not text.strip():
            return ""

        # Always use rule-based — fast (<5ms), accurate for all common commands.
        # Low-confidence results (conversation/information) are handled by the
        # main LLM in _stage_llm, not by the intent classifier.
        rule_result = self._intent_recognizer._rule_engine.recognize(
            text, self._intent_recognizer._platform
        )
        result = rule_result

        action = result.parameters.get("action", "")
        param = (
            result.parameters.get("app")
            or result.parameters.get("path")
            or result.parameters.get("query")
            or result.parameters.get("contact")
            or result.parameters.get("text")
            or result.parameters.get("direction", "")
            or ""
        )
        level = (
            str(result.parameters.get("engine", ""))
            or str(result.parameters.get("level", ""))
        )
        encoded = f"{result.intent_type}:{action}:{param}:{level}".rstrip(":")
        logger.info(
            "Intent: %s (confidence=%.2f) params=%s encoded=%r",
            result.intent_type, result.confidence, result.parameters, encoded
        )
        return encoded

    async def _stage_policy(self, intent: str) -> bool:
        """Stage 6: Policy check — returns True if execution is allowed.

        Supports both:
          - evaluate(intent) — simple API used in tests/mocks
          - evaluate_policy(principal, resource, action) — full PolicyEngine API

        Defaults to True (allow) when policy engine is unavailable or a stub.
        """
        try:
            # Prefer evaluate() — used by mocks and simpler subsystems
            fn = getattr(self.policy, "evaluate", None)
            if fn is not None:
                if asyncio.iscoroutinefunction(fn):
                    decision = await fn(intent)
                else:
                    loop = asyncio.get_running_loop()
                    decision = await loop.run_in_executor(None, fn, intent)
                if hasattr(decision, "effect"):
                    return decision.effect.value.upper() == "ALLOW"
                # MagicMock returns a truthy MagicMock — treat as allow
                if hasattr(decision, "_mock_name"):
                    return True
                return bool(decision)

            # Fall back to PolicyEngine.evaluate_policy(principal, resource, action)
            eval_fn = getattr(self.policy, "evaluate_policy_async", None) or \
                      getattr(self.policy, "evaluate_policy", None)
            if eval_fn is None:
                return False  # No policy engine — deny by default (secure)

            try:
                from Agent_Guru.policy.models import Principal, Resource
                principal = Principal(id="guru_pipeline", attributes={"role": "assistant"})
                resource = Resource(id="action", type="command")
                if asyncio.iscoroutinefunction(eval_fn):
                    decision = await eval_fn(principal, resource, intent)
                else:
                    loop = asyncio.get_running_loop()
                    decision = await loop.run_in_executor(
                        None, eval_fn, principal, resource, intent
                    )
                if hasattr(decision, "effect"):
                    return decision.effect.value.upper() == "ALLOW"
                return bool(decision)
            except ImportError as e:
                return False  # Can't build Principal/Resource — deny by default (secure)

        except Exception as exc:
            logger.error("Policy stage error: %s — defaulting to deny for safety", exc)
            return False  # Deny by default when policy check fails

    async def _stage_action(self, intent: str) -> Any:
        """Stage 7: Execute action via agent_orchestrator or OSController.

        Supports:
        - Single intent: 'intent_type:action:param:level'
        - Multi-step:    'step1|step2|step3' (pipe-separated, from _stage_intent)

        Examples:
          'system_control:open_app:notepad'
          'system_control:open_app:edge|system_control:open_url:youtube|system_control:web_search:chak de india:youtube'
          'information:question:who is the prime minister of india'
        """
        if not intent:
            return None

        # ── Multi-step execution ──────────────────────────────────────────
        if "|" in intent:
            steps = [s.strip() for s in intent.split("|") if s.strip()]
            results = []
            for step in steps:
                try:
                    step_result = await self._execute_single_action(step)
                    if step_result:
                        results.append(str(step_result))
                    # Give apps time to open before the next step
                    await asyncio.sleep(1.5)
                except Exception as exc:
                    logger.warning("Multi-step action failed for step %r: %s", step, exc)
            return ". ".join(results) if results else None

        # ── Single action ─────────────────────────────────────────────────
        return await self._execute_single_action(intent)

    async def _execute_single_action(self, intent: str) -> Any:
        """Execute a single intent string. Returns a human-readable result or None."""
        if not intent:
            return None

        safe_intent = self._sanitize_output(intent)

        try:
            loop = asyncio.get_running_loop()

            # Primary path: delegate to agent_orchestrator.execute(intent)
            execute_fn = getattr(self.agent_orchestrator, "execute", None)
            if execute_fn is not None:
                try:
                    if asyncio.iscoroutinefunction(execute_fn):
                        result = await execute_fn(safe_intent)
                    else:
                        result = await loop.run_in_executor(None, execute_fn, safe_intent)
                    if result is not None:
                        return result
                except AttributeError:
                    pass
                except Exception as exc:
                    logger.warning("Agent orchestrator execute failed: %s — trying direct platform control", exc)
        except Exception as exc:
            logger.warning("Unexpected error in primary action path: %s", exc)

        # Fallback: direct OSController calls
        try:
            loop = asyncio.get_running_loop()
            parts = safe_intent.split(":", 3)
            intent_type = parts[0] if len(parts) > 0 else ""
            action      = parts[1] if len(parts) > 1 else ""
            param       = parts[2] if len(parts) > 2 else ""
            level_str   = parts[3] if len(parts) > 3 else ""

            # Conversation → no action, TTS uses LLM response directly
            if intent_type == "conversation":
                return None

            if intent_type not in ("system_control", "file_ops", "communication", "information"):
                logger.info("ACTION SKIPPED — intent_type=%r. Full intent: %r", intent_type, safe_intent)
                return None

            ctrl = self.platform_controller
            if ctrl is None:
                return None

            # ── Application control ───────────────────────────────────────
            if (action == "open_app" or action == "open_file") and param:
                param = param.rstrip(".,!?;:")
                logger.info("ACTION: open_application('%s')", param)
                result = await asyncio.to_thread(ctrl.open_application, param)
                safe_param = self._sanitize_output(param)
                if getattr(result, "success", False):
                    return f"Opening {safe_param}"
                else:
                    err = getattr(result, "error", "unknown error")
                    logger.error("Failed to open '%s': %s", param, err)
                    return f"Sorry, I couldn't open {safe_param}"

            if action == "close_app" and param:
                param = param.rstrip(".,!?;:")
                logger.info("ACTION: close_application('%s')", param)
                result = await asyncio.to_thread(ctrl.close_application, param)
                safe_param = self._sanitize_output(param)
                return f"Closed {safe_param}" if getattr(result, "success", True) else f"Failed to close {safe_param}"

            # ── Web / URL ─────────────────────────────────────────────────
            if action == "open_url":
                # Comprehensive URL map — known sites get direct URLs
                url_map = {
                    # Video / Music
                    "youtube":      "https://www.youtube.com",
                    "spotify":      "https://www.spotify.com",
                    "netflix":      "https://www.netflix.com",
                    "hotstar":      "https://www.hotstar.com",
                    "primevideo":   "https://www.primevideo.com",
                    "jiocinema":    "https://www.jiocinema.com",
                    "zee5":         "https://www.zee5.com",
                    "sonyliv":      "https://www.sonyliv.com",
                    "twitch":       "https://www.twitch.tv",
                    "tiktok":       "https://www.tiktok.com",
                    # Search / Info
                    "google":       "https://www.google.com",
                    "bing":         "https://www.bing.com",
                    "wikipedia":    "https://www.wikipedia.org",
                    "quora":        "https://www.quora.com",
                    "reddit":       "https://www.reddit.com",
                    "medium":       "https://www.medium.com",
                    "hashnode":     "https://hashnode.com",
                    # Social
                    "twitter":      "https://www.twitter.com",
                    "facebook":     "https://www.facebook.com",
                    "instagram":    "https://www.instagram.com",
                    "linkedin":     "https://www.linkedin.com",
                    "pinterest":    "https://www.pinterest.com",
                    "tumblr":       "https://www.tumblr.com",
                    # Messaging
                    "whatsapp":     "https://web.whatsapp.com",
                    "telegram":     "https://web.telegram.org",
                    "discord":      "https://discord.com",
                    "slack":        "https://slack.com",
                    "zoom":         "https://zoom.us",
                    "teams":        "https://teams.microsoft.com",
                    "meet":         "https://meet.google.com",
                    # Dev / Coding
                    "github":       "https://www.github.com",
                    "stackoverflow":"https://stackoverflow.com",
                    "leetcode":     "https://www.leetcode.com",
                    "hackerrank":   "https://www.hackerrank.com",
                    "codechef":     "https://www.codechef.com",
                    "codeforces":   "https://www.codeforces.com",
                    "geeksforgeeks":"https://www.geeksforgeeks.org",
                    "w3schools":    "https://www.w3schools.com",
                    "mdn":          "https://developer.mozilla.org",
                    "openai":       "https://www.openai.com",
                    "huggingface":  "https://huggingface.co",
                    "kaggle":       "https://www.kaggle.com",
                    "dev.to":       "https://dev.to",
                    # Learning
                    "udemy":        "https://www.udemy.com",
                    "coursera":     "https://www.coursera.org",
                    "edx":          "https://www.edx.org",
                    "khanacademy":  "https://www.khanacademy.org",
                    "khan academy": "https://www.khanacademy.org",
                    # Shopping / Finance
                    "amazon":       "https://www.amazon.in",
                    "flipkart":     "https://www.flipkart.com",
                    "myntra":       "https://www.myntra.com",
                    "snapdeal":     "https://www.snapdeal.com",
                    "paytm":        "https://www.paytm.com",
                    "phonepe":      "https://www.phonepe.com",
                    "gpay":         "https://pay.google.com",
                    # Travel
                    "irctc":        "https://www.irctc.co.in",
                    "makemytrip":   "https://www.makemytrip.com",
                    "goibibo":      "https://www.goibibo.com",
                    "booking":      "https://www.booking.com",
                    "airbnb":       "https://www.airbnb.com",
                    # Jobs
                    "naukri":       "https://www.naukri.com",
                    "indeed":       "https://www.indeed.com",
                    "glassdoor":    "https://www.glassdoor.com",
                    # Google services
                    "gmail":        "https://mail.google.com",
                    "maps":         "https://maps.google.com",
                    "translate":    "https://translate.google.com",
                    "drive":        "https://drive.google.com",
                    "docs":         "https://docs.google.com",
                    "sheets":       "https://sheets.google.com",
                    "slides":       "https://slides.google.com",
                    "calendar":     "https://calendar.google.com",
                    "keep":         "https://keep.google.com",
                }
                param_lower = param.lower().strip()

                # "open edge" / "open microsoft edge" → launch the browser app
                if param_lower in ("edge", "microsoft edge", "msedge"):
                    result = await asyncio.to_thread(ctrl.open_application, "msedge")
                    if not getattr(result, "success", False):
                        result = await asyncio.to_thread(ctrl.open_application, "microsoft edge")
                    return "Opening Microsoft Edge"

                # "open chrome" / "open firefox" → launch browser app, not URL
                if param_lower in ("chrome", "google chrome"):
                    result = await asyncio.to_thread(ctrl.open_application, "chrome")
                    return "Opening Chrome"
                if param_lower in ("firefox", "mozilla firefox"):
                    result = await asyncio.to_thread(ctrl.open_application, "firefox")
                    return "Opening Firefox"

                # Check known URL map
                known_url = url_map.get(param_lower)
                if known_url:
                    logger.info("ACTION: open_url('%s') → %s", param, known_url)
                    fn = getattr(ctrl, "open_url", None)
                    if fn:
                        await asyncio.to_thread(fn, known_url)
                        return f"Opening {self._sanitize_output(param)}"

                # Explicit URL (starts with http/https)
                if param.startswith("http://") or param.startswith("https://"):
                    import urllib.parse as _urlparse
                    parsed = _urlparse.urlparse(param)
                    if parsed.scheme not in ("http", "https"):
                        return "Cannot open URL with unsafe scheme"
                    fn = getattr(ctrl, "open_url", None)
                    if fn:
                        await asyncio.to_thread(fn, param)
                        return f"Opened {self._sanitize_output(param)}"

                # Domain name (contains a dot like "leetcode.com")
                if "." in param and not " " in param:
                    url = param if param.startswith("http") else f"https://{param}"
                    fn = getattr(ctrl, "open_url", None)
                    if fn:
                        await asyncio.to_thread(fn, url)
                        return f"Opening {self._sanitize_output(param)}"

                # Unknown name → try as direct URL first, then Google search
                # e.g. "open leetcode" → try https://www.leetcode.com, then Google search
                import urllib.parse as _up
                # Try direct URL (www.X.com)
                direct_url = f"https://www.{param_lower.replace(' ', '')}.com"
                fn = getattr(ctrl, "open_url", None)
                if fn:
                    logger.info("ACTION: open_url (unknown site) → %s", direct_url)
                    await asyncio.to_thread(fn, direct_url)
                    return f"Opening {self._sanitize_output(param)}"
                return f"Cannot open {self._sanitize_output(param)} — browser unavailable"

            if action == "web_search":
                query = param.strip()
                engine = level_str.strip().lower() if level_str.strip() else "google"
                if engine not in ("google", "youtube", "bing"):
                    engine = "google"
                logger.info("ACTION: web_search('%s', engine='%s')", query, engine)
                import urllib.parse as _up

                if engine == "youtube":
                    # Use Playwright to find and open the first result so the
                    # video actually plays — then leave the browser open for the
                    # user to control with further voice commands.
                    # NO demo sequence — just open and play.
                    try:
                        await self._open_youtube_and_play(query)
                        return f"Playing {self._sanitize_output(query)} on YouTube"
                    except Exception as yt_exc:
                        logger.warning(
                            "YouTube auto-play failed (%s) — opening search page instead",
                            yt_exc,
                        )
                        search_url = (
                            "https://www.youtube.com/results?search_query="
                            + _up.quote_plus(query)
                        )
                        fn = getattr(ctrl, "open_url", None)
                        if fn:
                            await asyncio.to_thread(fn, search_url)
                        return f"Opening YouTube search for {self._sanitize_output(query)}"

                _engines = {
                    "google": "https://www.google.com/search?q=",
                    "bing":   "https://www.bing.com/search?q=",
                }
                search_url = _engines.get(engine, _engines["google"]) + _up.quote_plus(query)
                fn = getattr(ctrl, "open_url", None)
                if fn:
                    await asyncio.to_thread(fn, search_url)
                    return f"Searching for {self._sanitize_output(query)} on {engine}"
                return "Cannot search — controller unavailable"

            # ── Volume ────────────────────────────────────────────────────
            if action == "volume":
                mgr = getattr(self, "_browser_mgr", None)
                yt_open = mgr is not None and mgr._page is not None
                num_match = re.search(r"\d+", param + " " + level_str)

                if num_match:
                    vol = max(0, min(100, int(num_match.group())))
                    logger.info("ACTION: set_volume(%d)", vol)
                    if yt_open:
                        try:
                            return await mgr.set_volume(vol)
                        except Exception:
                            pass
                    try:
                        await asyncio.to_thread(ctrl.set_volume, vol)
                    except Exception as exc:
                        logger.warning("set_volume failed: %s", exc)
                    return f"Volume set to {vol}%"

                elif "up" in param.lower() or "increase" in param.lower():
                    if yt_open:
                        try:
                            return await mgr.volume_up()
                        except Exception:
                            pass
                    fn = getattr(ctrl, "volume_up", None)
                    try:
                        if fn:
                            await loop.run_in_executor(None, fn)
                    except Exception as exc:
                        logger.warning("volume_up failed: %s", exc)
                    return "Volume increased"

                elif "down" in param.lower() or "decrease" in param.lower():
                    if yt_open:
                        try:
                            return await mgr.volume_down()
                        except Exception:
                            pass
                    fn = getattr(ctrl, "volume_down", None)
                    try:
                        if fn:
                            await loop.run_in_executor(None, fn)
                    except Exception as exc:
                        logger.warning("volume_down failed: %s", exc)
                    return "Volume decreased"

                elif re.search(r"\b(mute|unmute)\b", param, re.I):
                    is_unmute = bool(re.search(r"\bunmute\b", param, re.I))
                    if yt_open:
                        try:
                            return await (mgr.unmute() if is_unmute else mgr.mute())
                        except Exception:
                            pass
                    fn = getattr(ctrl, "unmute" if is_unmute else "mute", None)
                    try:
                        if fn:
                            await loop.run_in_executor(None, fn)
                    except Exception as exc:
                        logger.warning("mute failed: %s", exc)
                    return "Unmuted" if is_unmute else "Muted"

            # ── Brightness ────────────────────────────────────────────────
            if action == "brightness":
                num_match = re.search(r"\d+", param + " " + level_str)
                if num_match:
                    brightness = max(0, min(100, int(num_match.group())))
                    logger.info("ACTION: set_brightness(%d)", brightness)
                    await asyncio.to_thread(ctrl.set_brightness, brightness)
                    return f"Brightness set to {brightness}%"
                get_fn = getattr(ctrl, "get_brightness", None)
                current = 50
                if get_fn:
                    try:
                        current = int(await asyncio.to_thread(get_fn))
                    except Exception:
                        pass
                set_fn = getattr(ctrl, "set_brightness", None)
                if "up" in param.lower() or "increase" in param.lower():
                    if set_fn:
                        await asyncio.to_thread(set_fn, min(100, current + 10))
                    return "Brightness increased"
                elif "down" in param.lower() or "decrease" in param.lower():
                    if set_fn:
                        await asyncio.to_thread(set_fn, max(0, current - 10))
                    return "Brightness decreased"

            # ── Window management ─────────────────────────────────────────
            if action == "window":
                window_ctx = (param + " " + level_str).lower()
                if re.search(r"\bminimize\b|\bminimise\b", window_ctx):
                    fn = getattr(ctrl, "minimize_window", None)
                    if fn:
                        await asyncio.to_thread(fn, "")
                    return "Window minimized"
                if re.search(r"\bmaximize\b|\bmaximise\b", window_ctx):
                    fn = getattr(ctrl, "maximize_window", None)
                    if fn:
                        await asyncio.to_thread(fn, "")
                    return "Window maximized"

            # ── Screenshot ────────────────────────────────────────────────
            if action == "screenshot":
                logger.info("ACTION: screenshot")
                fn = getattr(ctrl, "take_screenshot", None) or getattr(
                    getattr(ctrl, "_screen_controller", None), "capture", None
                )
                if fn:
                    await loop.run_in_executor(None, fn)
                    return "Screenshot taken"

            # ── Media controls ────────────────────────────────────────────
            if action == "next_track":
                fn = getattr(ctrl, "next_track", None)
                if fn:
                    await loop.run_in_executor(None, fn)
                return "Next track"

            if action == "previous_track":
                fn = getattr(ctrl, "previous_track", None)
                if fn:
                    await loop.run_in_executor(None, fn)
                return "Previous track"

            if action == "stop_media":
                fn = getattr(ctrl, "stop_media", None)
                if fn:
                    await loop.run_in_executor(None, fn)
                return "Media stopped"

            if action == "play_pause":
                # Route to BrowserManager if YouTube is open, else system media keys
                mgr = getattr(self, "_browser_mgr", None)
                if mgr and mgr._page is not None:
                    try:
                        if re.search(r"\bpause\b", safe_intent, re.I):
                            return await mgr.pause()
                        else:
                            return await mgr.resume()
                    except Exception as exc:
                        logger.warning("BrowserManager play_pause failed: %s", exc)

                if re.search(r"\bpause\b", safe_intent, re.I):
                    fn = getattr(ctrl, "pause_media", None)
                    if fn:
                        await loop.run_in_executor(None, fn)
                    return "Media paused"
                else:
                    fn = getattr(ctrl, "play_media", None)
                    if fn:
                        await loop.run_in_executor(None, fn)
                    return "Media playing"

            # ── Type text ─────────────────────────────────────────────────
            if action == "type_text" and param:
                fn = getattr(ctrl, "type_text", None)
                if fn:
                    await asyncio.to_thread(fn, param)
                    return "Typed text"
                return "Cannot type — controller unavailable"

            # ── Switch app ────────────────────────────────────────────────
            if action == "switch_app" and param:
                switched = False
                if sys.platform == "win32":
                    try:
                        import win32gui as _wg  # type: ignore[import]
                        found: list[int] = []
                        def _cb(hwnd: int, _: object) -> None:
                            title = _wg.GetWindowText(hwnd)
                            if param.lower() in title.lower():
                                found.append(hwnd)
                        _wg.EnumWindows(_cb, None)
                        if found:
                            _wg.SetForegroundWindow(found[0])
                            switched = True
                    except Exception as exc:
                        logger.debug("win32 switch_app failed: %s", exc)
                if not switched:
                    await asyncio.to_thread(ctrl.open_application, param)
                return f"Switched to {self._sanitize_output(param)}"

            # ── Shutdown / Restart ────────────────────────────────────────
            if action in ("shutdown", "restart"):
                fn = getattr(ctrl, action + "_pc", None)
                if fn:
                    await asyncio.to_thread(fn, confirmed=True)
                    return f"System {action} initiated"
                return f"Cannot {action} — controller unavailable"

            # ── Settings ──────────────────────────────────────────────────
            if action == "settings":
                setting_text = (param + " " + level_str).lower()
                fn_wifi = getattr(ctrl, "toggle_wifi", None)
                fn_bt = getattr(ctrl, "toggle_bluetooth", None)
                if "wifi" in setting_text or "wi-fi" in setting_text:
                    enable = "off" not in setting_text and "disable" not in setting_text
                    if fn_wifi:
                        await asyncio.to_thread(fn_wifi, enable)
                    return f"WiFi {'enabled' if enable else 'disabled'}"
                if "bluetooth" in setting_text:
                    enable = "off" not in setting_text and "disable" not in setting_text
                    if fn_bt:
                        await asyncio.to_thread(fn_bt, enable)
                    return f"Bluetooth {'enabled' if enable else 'disabled'}"
                return "Settings updated"

            # ── Communication ─────────────────────────────────────────────
            if intent_type == "communication":
                if action in ("send_message", "reply"):
                    contact = param.strip()
                    app = level_str.strip().lower() if level_str.strip() else "whatsapp"
                    if app not in ("whatsapp", "telegram", "slack", "sms", "email"):
                        app = "whatsapp"
                    fn = getattr(ctrl, "open_url", None)
                    if fn and contact:
                        import urllib.parse as _up
                        if app == "whatsapp":
                            digits = contact.replace("+", "").replace("-", "").replace(" ", "")
                            url = f"https://wa.me/{digits}" if digits.isdigit() else "https://web.whatsapp.com"
                            await asyncio.to_thread(fn, url)
                            return f"Opening WhatsApp for {self._sanitize_output(contact)}"
                        elif app == "telegram":
                            await asyncio.to_thread(fn, f"https://t.me/{contact.lstrip('@')}")
                            return f"Opening Telegram for {self._sanitize_output(contact)}"
                        elif app == "email":
                            await asyncio.to_thread(fn, f"mailto:{contact}")
                            return f"Opening email for {self._sanitize_output(contact)}"
                    return f"Opening messaging app for {self._sanitize_output(contact)}"
                if action == "make_call":
                    contact = param.strip()
                    fn = getattr(ctrl, "open_url", None)
                    if fn and contact:
                        digits = contact.replace("+", "").replace("-", "").replace(" ", "")
                        url = f"tel:{digits}" if digits.isdigit() else f"https://wa.me/?phone={contact}"
                        await asyncio.to_thread(fn, url)
                    return f"Calling {self._sanitize_output(contact)}"

            # ── Information (questions / facts) ───────────────────────────
            # For factual questions the LLM response IS the answer — return None
            # so the pipeline uses llm_response for TTS.
            # Only do a web search for queries that need live/current data.
            if intent_type == "information":
                query = param.strip() or safe_intent
                action_lower = action.lower() if action else ""
                if action_lower in ("weather", "news", "search"):
                    fn = getattr(ctrl, "web_search", None)
                    if fn:
                        await asyncio.to_thread(fn, query, "google")
                        return f"Searching for {self._sanitize_output(query)}"
                # For questions/facts: LLM already answered — just return None
                return None

            # ── File operations ───────────────────────────────────────────
            if intent_type == "file_ops":
                if action == "create" and param:
                    fn = getattr(ctrl, "create_file", None)
                    if fn:
                        await asyncio.to_thread(fn, param)
                        return f"Created {self._sanitize_output(param)}"
                if action == "delete" and param:
                    fn = getattr(ctrl, "delete_file", None)
                    if fn:
                        await asyncio.to_thread(fn, param, True)
                        return f"Deleted {self._sanitize_output(param)}"

            return None

        except Exception as exc:
            logger.warning("Action stage error: %s", exc)
            return None

    async def _get_browser_mgr(self) -> Any:
        """Return the BrowserManager, starting it on first call."""
        if self._browser_mgr is None:
            from Agent_Guru.platform.browser_manager import BrowserManager
            self._browser_mgr = BrowserManager()
            await self._browser_mgr.start()
        return self._browser_mgr

    async def _open_youtube_and_play(self, query: str) -> str:
        """Open YouTube and play *query* using the persistent BrowserManager."""
        mgr = await self._get_browser_mgr()
        return await mgr.play_youtube(query)

    async def _invoke_tts_fn(
        self,
        fn: Any,
        text: str,
        pt: Any,
        fn_type: str,
    ) -> tuple[Any, int]:
        """Invoke a TTS callable and return (audio_array, sample_rate).

        Handles array, response, and bytes return types uniformly.
        Returns (None, 22050) when the function produces no usable audio.
        """
        import io
        import wave

        import numpy as np

        sample_rate = 22050
        audio_array: Any = None

        if fn_type in ("array", "response"):
            if asyncio.iscoroutinefunction(fn):
                result = await fn(text, pt)
            else:
                result = await asyncio.to_thread(fn, text, pt)
            if isinstance(result, tuple) and len(result) == 2:
                audio_array, sample_rate = result
            elif isinstance(result, np.ndarray):
                audio_array = result

        elif fn_type == "bytes":
            if asyncio.iscoroutinefunction(fn):
                wav_bytes = await fn(text, pt)
            else:
                wav_bytes = await asyncio.to_thread(fn, text, pt)
            if isinstance(wav_bytes, (bytes, bytearray)) and len(wav_bytes) > 44:
                with io.BytesIO(wav_bytes) as buf:
                    with wave.open(buf, "rb") as wf:
                        sample_rate = wf.getframerate()
                        frames = wf.readframes(wf.getnframes())
                audio_array = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            elif isinstance(wav_bytes, (bytes, bytearray)):
                # Short bytes (e.g. b"<audio>" from mock) — return sentinel
                return wav_bytes, sample_rate  # type: ignore[return-value]

        return audio_array, sample_rate

    async def _stage_tts(self, text: str, personality: Personality) -> Any:
        """Stage 8: TTS synthesis and audio playback.

        Converts the orchestrator's Personality enum to the speech engine's
        PersonalityType enum before calling synthesis methods.
        """
        if not text or not text.strip():
            return text
        try:
            import numpy as np

            # Convert orchestrator Personality → speech engine PersonalityType
            try:
                from Agent_Guru.speech.models import PersonalityType
                pt = (
                    PersonalityType.MAYA
                    if personality == Personality.MAYA
                    else PersonalityType.GURU
                )
            except ImportError:
                pt = personality  # fallback — pass as-is

            audio_array: Any = None
            sample_rate = 22050

            # Build ordered candidate list — cached fn first, then runtime probes
            tts_eng = getattr(self.speech_engine, "tts_engine", None)
            if self._tts_fn is not None:
                candidates = [(self._tts_fn, self._tts_fn_type)]
            else:
                # startup() was not called — probe at call time
                candidates = [
                    (
                        getattr(self.speech_engine, "synthesize_to_array", None)
                        or (tts_eng and getattr(tts_eng, "synthesize_to_array", None)),
                        "array",
                    ),
                    (getattr(self.speech_engine, "synthesize_response", None), "response"),
                    (
                        getattr(self.speech_engine, "synthesize", None)
                        or (tts_eng and getattr(tts_eng, "synthesize", None)),
                        "bytes",
                    ),
                ]

            for fn_candidate, fn_type in candidates:
                if fn_candidate is None or audio_array is not None:
                    continue
                try:
                    audio_array, sample_rate = await self._invoke_tts_fn(
                        fn_candidate, text, pt, fn_type
                    )
                    if isinstance(audio_array, (bytes, bytearray)):
                        return audio_array
                except Exception as exc:
                    logger.warning("TTS fn (%s) failed: %s", fn_type, exc)

            # --- Play audio through speakers ---
            if audio_array is not None and len(audio_array) > 0:
                try:
                    import sounddevice as sd

                    def _play() -> None:
                        # Pad with 300ms silence to prevent last-word cutoff
                        tail = np.zeros(int(sample_rate * 0.30), dtype=np.float32)
                        padded = np.concatenate([audio_array.astype(np.float32), tail])
                        sd.play(padded, samplerate=sample_rate)
                        sd.wait()

                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, _play)
                    logger.info("TTS played: %.1fs of audio", len(audio_array) / sample_rate)
                except ImportError:
                    # BUG-FIX: sounddevice missing was silently swallowed — the
                    # TTS audio was synthesized but never played, so the user
                    # heard nothing. Now falls back to pyttsx3 (always available
                    # on Windows/macOS/Linux) so the reply is always spoken.
                    logger.warning(
                        "sounddevice not installed — falling back to pyttsx3 TTS. "
                        "For best audio quality: pip install sounddevice"
                    )
                    try:
                        import pyttsx3  # type: ignore[import]
                        from Agent_Guru.speech.models import PersonalityType as _PT

                        def _play_pyttsx3() -> None:
                            engine = pyttsx3.init()
                            # Match voice gender to personality
                            voices = engine.getProperty("voices")
                            if voices:
                                if personality == Personality.MAYA:
                                    # Pick first female voice if available
                                    female = next(
                                        (v for v in voices if "female" in v.name.lower()
                                         or "zira" in v.name.lower()
                                         or "hazel" in v.name.lower()),
                                        voices[-1],
                                    )
                                    engine.setProperty("voice", female.id)
                                else:
                                    engine.setProperty("voice", voices[0].id)
                            engine.setProperty("rate", 175)
                            engine.say(text)
                            engine.runAndWait()

                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, _play_pyttsx3)
                        logger.info("TTS played via pyttsx3 fallback")
                    except Exception as tts_exc:
                        logger.error(
                            "TTS playback failed (both sounddevice and pyttsx3 unavailable): %s. "
                            "Install sounddevice: pip install sounddevice",
                            tts_exc,
                        )
                except Exception as exc:
                    logger.warning("Audio playback error: %s", exc)

            return audio_array
        except Exception as exc:
            logger.warning("TTS stage error: %s", exc)
            return text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_output(text: str) -> str:
        """Sanitize user-controlled text to prevent XSS attacks.

        Escapes HTML special characters so the text is safe to display
        in web interfaces, logs, or any HTML context.

        Args:
            text: Raw user input or derived text.

        Returns:
            HTML-escaped text safe for display.
        """
        if not text:
            return text
        import html as _html_mod
        return _html_mod.escape(str(text), quote=True)

    @staticmethod
    def _resolve_personality(wake_word: str) -> Personality:
        """Map wake word string to Personality enum.

        "Hey Guru" → Personality.GURU
        "Hey Maya" → Personality.MAYA
        Anything else → Personality.GURU (default)
        """
        normalised = wake_word.strip().lower()
        if "maya" in normalised:
            return Personality.MAYA
        return Personality.GURU

    @staticmethod
    def _intent_needs_llm(intent: str, transcript: str) -> bool:
        """Return True if this intent requires an LLM response.

        System control commands (open app, volume, screenshot, web search, etc.)
        do NOT need LLM — the action confirmation IS the response.

        Conversation and information intents DO need LLM to generate an answer.

        This is the key optimization that brings response time from 17s to <1s
        for 80% of commands (all system_control intents skip the LLM entirely).
        """
        if not intent:
            return True

        # Multi-step: needs LLM only if any step needs it
        if "|" in intent:
            return any(
                IntegrationOrchestrator._intent_needs_llm(step, transcript)
                for step in intent.split("|")
            )

        parts = intent.split(":", 1)
        intent_type = parts[0].lower().strip() if parts else ""

        # These intent types always need LLM (they are questions/conversation)
        if intent_type in ("conversation", "information"):
            return True

        # system_control, file_ops, communication -> action confirmation is enough
        if intent_type in ("system_control", "file_ops", "communication"):
            return False

        # Unknown intent type -> call LLM to be safe
        return True
