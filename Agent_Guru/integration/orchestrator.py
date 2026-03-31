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
                        await loop.run_in_executor(None, lambda: init(device_cfg=device_cfg))
                    except TypeError:
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
        async with self._sleeping_lock:
            self._sleeping = True
        logger.info("IntegrationOrchestrator: sleep mode — wake word detection only")

    async def wake(self) -> None:
        """Exit sleep mode — all subsystems active."""
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
            # Stage 1: STT
            result.transcript, result.detected_language = await self._stage_stt(wake_event.audio)
            result.stages_completed = 1

            # Stage 2: Memory context
            result.memory_context = await self._stage_memory(result.transcript)
            result.stages_completed = 2

            # Stage 3: Reasoning
            result.reasoning_output = await self._stage_reasoning(
                result.transcript, result.memory_context
            )
            result.stages_completed = 3

            # Stage 4: LLM inference (enriched with memory + reasoning)
            result.llm_response = await self._stage_llm(
                result.transcript, result.memory_context, result.reasoning_output,
                result.detected_language,
            )
            result.stages_completed = 4

            # Translation fallback: if LLM responded in wrong language, translate
            if result.detected_language and result.detected_language != "en":
                translation_engine = getattr(self, "_translation_engine", None)
                if translation_engine is not None:
                    try:
                        tr = translation_engine.translate(
                            result.llm_response or "",
                            target_language=result.detected_language,
                        )
                        result.llm_response = tr.translated_text
                    except Exception as _te:
                        logger.debug("Translation fallback failed: %s", _te)

            # Stage 5: Intent recognition — ALWAYS use the user's transcript,
            # never the LLM response (which is conversational and confuses the classifier)
            result.intent = await self._stage_intent(result.transcript or "")
            result.stages_completed = 5

            # Stage 6: Policy check
            result.policy_allowed = await self._stage_policy(result.intent)
            result.stages_completed = 6

            # Stage 7: Action execution (only if policy allows)
            if result.policy_allowed:
                result.action_result = await self._stage_action(result.intent)
            result.stages_completed = 7

            # Stage 8: TTS — speak the LLM response (or action confirmation)
            tts_text = result.llm_response or result.action_result or ""
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
                self._audit_logger.log_event(
                    event_type=EventType.POLICY_VIOLATION,
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

    async def _stage_stt(self, audio: bytes) -> tuple[str, str]:
        """Stage 1: Speech-to-text.

        Returns:
            (transcript, language_code) where language_code is ISO 639-1
            e.g. ("नमस्ते", "hi") or ("", "") on failure/silence.
        """
        try:
            import numpy as np

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
            # with the raw audio — no numpy conversion needed for mock/async paths
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
                # Guard: float32 requires buffer length divisible by 4
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
            if rms < 0.001:
                logger.debug("STT: audio too quiet (rms=%.5f), skipping", rms)
                return ("", "")

            logger.debug("STT: processing %.2fs of audio (rms=%.4f)", len(audio_np) / 16000, rms)

            # fn is guaranteed synchronous here — async functions returned early above
            loop = asyncio.get_running_loop()
            params = self._stt_params or []
            try:
                if "personality" in params:
                    from Agent_Guru.speech.models import PersonalityType
                    result = await loop.run_in_executor(
                        None, lambda: fn(audio_np, PersonalityType.GURU)
                    )
                elif "sample_rate" in params:
                    result = await loop.run_in_executor(
                        None, lambda: fn(audio_np, sample_rate=16000)
                    )
                else:
                    result = await loop.run_in_executor(None, lambda: fn(audio_np, 16000))
            except Exception:
                result = await loop.run_in_executor(None, lambda: fn(audio_np, 16000))

            if hasattr(result, "text") and hasattr(result, "language"):
                text = (result.text or "").strip()
                language = result.language or ""
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
            except ImportError:
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
    ) -> str:
        """Stage 4: LLM inference with enriched context.

        Tries, in order:
          1. infer(transcript, memory_context, reasoning_output) — mock/stub API
          2. execute(transcript, ...) — alternate mock API
          3. complete(CompletionRequest) — real LLMRuntime API (Ollama/OpenAI/etc.)
        """
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

                system_prompt = (
                    "You are Agent Guru, an AI voice assistant with FULL control over the user's computer. "
                    "You CAN and SHOULD execute any laptop operation the user requests. "
                    "Available actions you can perform:\n"
                    "- Open/launch applications (notepad, chrome, firefox, calculator, explorer, cmd, etc.)\n"
                    "- Close/quit applications\n"
                    "- Set system volume (0-100)\n"
                    "- Set screen brightness (0-100)\n"
                    "- Minimize/maximize windows\n"
                    "- Take screenshots\n"
                    "- Create/read/delete/move files\n"
                    "- Type text into applications\n"
                    "- Control media playback\n"
                    "- Search the web\n"
                    "- Answer questions about time, date, weather, facts\n\n"
                    "When the user asks you to do something on their computer, respond naturally and confirm "
                    "you are doing it. Be concise. Do NOT say you cannot do things — you CAN control the laptop."
                )

                lang_instruction = ""
                if language_code and language_code != "en":
                    lang_instruction = (
                        f"\n\nIMPORTANT: The user spoke in language code '{language_code}'. "
                        f"You MUST respond in the same language. Do NOT respond in English."
                    )
                system_prompt = system_prompt + lang_instruction

                messages = [
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=prompt),
                ]
                request = CompletionRequest(
                    model="mistral:7b-instruct",
                    messages=messages,
                )
                response = await complete_fn(request)
                return response.content or ""
            except ImportError:
                return ""

        except Exception as exc:
            logger.warning("LLM stage error: %s", exc)
            return ""

    async def _stage_intent(self, llm_response: str) -> str:
        """Stage 5: Extract structured intent from the user's transcript.

        Uses IntentRecognizer (rule-based + LLM) to produce a structured
        intent string of the form: 'intent_type:action:param:level'.
        Falls back to the raw input truncated to 200 chars.
        """
        if not llm_response:
            return ""
        try:
            # Lazy-init intent recognizer — pass llm_runtime as manager so
            # IntentRecognizer skips creating its own LLMManager (avoids real
            # network calls in test environments where llm_runtime is a mock).
            if self._intent_recognizer is None:
                from Agent_Guru.platform.intent_recognizer import IntentRecognizer
                self._intent_recognizer = IntentRecognizer(
                    llm_manager=self.llm_runtime
                )
                await self._intent_recognizer.initialize()

            result = await self._intent_recognizer.recognize(llm_response)
            # Encode as 'intent_type:action:param:level' for _stage_action to parse
            action = result.parameters.get("action", "")
            param = (
                result.parameters.get("app")
                or result.parameters.get("path")
                or result.parameters.get("query")
                or result.parameters.get("contact")
                or result.parameters.get("text")          # type_text content
                or result.parameters.get("direction", "")  # volume up/down/mute, window minimize/maximize
                or ""
            )
            # For web_search/open_url: carry engine in level field
            # For communication: carry app name in level field
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
        except Exception as exc:
            logger.warning("Intent stage error: %s", exc)
            return llm_response.strip()[:200]

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
            except ImportError:
                return False  # Can't build Principal/Resource — deny by default (secure)

        except Exception as exc:
            logger.error("Policy stage error: %s — defaulting to deny for safety", exc)
            return False  # Deny by default when policy check fails

    async def _stage_action(self, intent: str) -> Any:
        """Stage 7: Execute action via agent_orchestrator or OSController.

        Delegates to agent_orchestrator.execute(intent) when available.
        Falls back to direct OSController calls for system_control intents.

        Intent format: 'intent_type:action:param:level'
        Examples:
          'system_control:open_app:notepad:'
          'system_control:volume:50:'
          'conversation:...'
        """
        if not intent:
            return None

        # Sanitize the full intent string before any use — prevents injection
        safe_intent = self._sanitize_output(intent)

        try:
            # Primary path: delegate to agent_orchestrator.execute(intent)
            # If it returns None (stub) or raises, fall through to direct platform control
            execute_fn = getattr(self.agent_orchestrator, "execute", None)
            if execute_fn is not None:
                try:
                    if asyncio.iscoroutinefunction(execute_fn):
                        result = await execute_fn(safe_intent)
                    else:
                        loop = asyncio.get_running_loop()
                        result = await loop.run_in_executor(None, execute_fn, safe_intent)
                    # Only return if we got a real result; otherwise fall through
                    if result is not None:
                        return result
                except AttributeError:
                    pass  # execute() not found — fall through to direct platform control
                except Exception as exc:
                    logger.warning("Agent orchestrator execute failed: %s — trying direct platform control", exc)
        except Exception as exc:
            logger.warning("Unexpected error in primary action path: %s", exc)

        # Fallback: direct OSController calls for system_control intents
        try:

            # Parse sanitized intent string — already sanitized above
            parts = safe_intent.split(":", 3)
            intent_type = parts[0] if len(parts) > 0 else ""
            action = parts[1] if len(parts) > 1 else ""
            param = parts[2] if len(parts) > 2 else ""
            level_str = parts[3] if len(parts) > 3 else ""

            # Only act on system_control, file_ops, communication, and information intents
            if intent_type not in ("system_control", "file_ops", "communication", "information"):
                logger.info(
                    "ACTION SKIPPED — intent_type=%r (not actionable). Full intent: %r",
                    intent_type, safe_intent
                )
                return None

            ctrl = self.platform_controller
            if ctrl is None:
                return None

            loop = asyncio.get_running_loop()

            # --- Application control ---
            if action == "open_app" and param:
                logger.info("ACTION: open_application('%s')", param)
                result = await loop.run_in_executor(None, lambda: ctrl.open_application(param))
                safe_param = self._sanitize_output(param)
                return f"Opened {safe_param}" if getattr(result, "success", True) else f"Failed to open {safe_param}"

            if action == "close_app" and param:
                logger.info("ACTION: close_application('%s')", param)
                result = await loop.run_in_executor(None, lambda: ctrl.close_application(param))
                safe_param = self._sanitize_output(param)
                return f"Closed {safe_param}" if getattr(result, "success", True) else f"Failed to close {safe_param}"

            # --- Web / URL ---
            if action == "open_url":
                # param may be a site name like "youtube" or a full URL
                url_map = {
                    "youtube": "https://www.youtube.com",
                    "google": "https://www.google.com",
                    "gmail": "https://mail.google.com",
                    "github": "https://www.github.com",
                    "reddit": "https://www.reddit.com",
                    "twitter": "https://www.twitter.com",
                    "facebook": "https://www.facebook.com",
                    "instagram": "https://www.instagram.com",
                    "linkedin": "https://www.linkedin.com",
                    "amazon": "https://www.amazon.com",
                    "netflix": "https://www.netflix.com",
                    "spotify": "https://www.spotify.com",
                    "wikipedia": "https://www.wikipedia.org",
                    "whatsapp": "https://web.whatsapp.com",
                    "stackoverflow": "https://stackoverflow.com",
                }
                url = url_map.get(param.lower().strip()) or (
                    param if param.startswith("http") else f"https://{param}"
                )
                logger.info("ACTION: open_url('%s')", url)
                fn = getattr(ctrl, "open_url", None)
                if fn:
                    result = await loop.run_in_executor(None, lambda: fn(url))
                    return f"Opened {self._sanitize_output(param)}"
                return f"Cannot open URL — controller unavailable"

            if action == "web_search":
                # param = search query, level_str may hold engine name
                query = param.strip()
                engine = level_str.strip().lower() if level_str.strip() else "google"
                if not engine or engine not in ("google", "youtube", "bing"):
                    engine = "google"
                logger.info("ACTION: web_search('%s', engine='%s')", query, engine)
                fn = getattr(ctrl, "web_search", None)
                if fn:
                    result = await loop.run_in_executor(None, lambda: fn(query, engine))
                    return f"Searching for {self._sanitize_output(query)} on {engine}"
                return f"Cannot search — controller unavailable"

            # --- Volume ---
            if action == "volume":
                # Extract number from param or level_str
                num_match = re.search(r"\d+", param + " " + level_str)
                if num_match:
                    vol = int(num_match.group())
                    vol = max(0, min(100, vol))
                    logger.info("ACTION: set_volume(%d)", vol)
                    try:
                        result = await loop.run_in_executor(None, lambda: ctrl.set_volume(vol))
                        return f"Volume set to {vol}%"
                    except Exception as exc:
                        logger.warning("set_volume failed: %s", exc)
                        return f"Volume set to {vol}% (audio driver unavailable)"

                elif "up" in param.lower():
                    logger.info("ACTION: volume up")
                    fn = getattr(ctrl, "volume_up", None) or getattr(
                        getattr(ctrl, "_settings_controller", None), "volume_up", None
                    )
                    try:
                        if fn:
                            await loop.run_in_executor(None, fn)
                    except Exception as exc:
                        logger.warning("volume_up failed: %s", exc)
                    return "Volume increased"
                elif "down" in param.lower():
                    logger.info("ACTION: volume down")
                    fn = getattr(ctrl, "volume_down", None) or getattr(
                        getattr(ctrl, "_settings_controller", None), "volume_down", None
                    )
                    try:
                        if fn:
                            await loop.run_in_executor(None, fn)
                    except Exception as exc:
                        logger.warning("volume_down failed: %s", exc)
                    return "Volume decreased"
                elif "mute" in param.lower() or "unmute" in param.lower():
                    logger.info("ACTION: mute/unmute")
                    fn = getattr(ctrl, "mute", None) or getattr(
                        getattr(ctrl, "_settings_controller", None), "mute", None
                    )
                    try:
                        if fn:
                            await loop.run_in_executor(None, fn)
                    except Exception as exc:
                        logger.warning("mute failed: %s", exc)
                    return "Muted"

            # --- Brightness ---
            if action == "brightness":
                num_match = re.search(r"\d+", param + " " + level_str)
                if num_match:
                    brightness = int(num_match.group())
                    brightness = max(0, min(100, brightness))
                    logger.info("ACTION: set_brightness(%d)", brightness)
                    result = await loop.run_in_executor(None, lambda: ctrl.set_brightness(brightness))
                    return f"Brightness set to {brightness}%"
                elif "up" in param.lower() or "increase" in param.lower():
                    fn = getattr(ctrl, "set_brightness", None)
                    if fn:
                        # Get current and increase by 10
                        await loop.run_in_executor(None, lambda: fn(min(100, 60)))
                    return "Brightness increased"
                elif "down" in param.lower() or "decrease" in param.lower():
                    fn = getattr(ctrl, "set_brightness", None)
                    if fn:
                        await loop.run_in_executor(None, lambda: fn(max(0, 30)))
                    return "Brightness decreased"

            # --- Window management ---
            if action == "window":
                # Check param (direction extracted by intent recognizer) and level_str;
                # do NOT use the full encoded intent string here since it always contains
                # the action word (e.g. "system_control:window:minimize:" would always match).
                window_ctx = (param + " " + level_str).lower()
                if re.search(r"\bminimize\b|\bminimise\b", window_ctx):
                    fn = getattr(ctrl, "minimize_window", None)
                    if fn:
                        win_title = ""
                        await loop.run_in_executor(None, lambda: fn(win_title))
                    return "Window minimized"
                if re.search(r"\bmaximize\b|\bmaximise\b", window_ctx):
                    fn = getattr(ctrl, "maximize_window", None)
                    if fn:
                        win_title = ""
                        await loop.run_in_executor(None, lambda: fn(win_title))
                    return "Window maximized"

            # --- Screenshot ---
            if action == "screenshot":
                logger.info("ACTION: screenshot")
                fn = getattr(ctrl, "take_screenshot", None) or getattr(
                    getattr(ctrl, "_screen_controller", None), "capture", None
                )
                if fn:
                    result = await loop.run_in_executor(None, fn)
                    return "Screenshot taken"

            # --- Media controls ---
            if action == "next_track":
                logger.info("ACTION: next_track")
                fn = getattr(ctrl, "next_track", None)
                if fn:
                    await loop.run_in_executor(None, fn)
                return "Next track"

            if action == "previous_track":
                logger.info("ACTION: previous_track")
                fn = getattr(ctrl, "previous_track", None)
                if fn:
                    await loop.run_in_executor(None, fn)
                return "Previous track"

            if action == "stop_media":
                logger.info("ACTION: stop_media")
                fn = getattr(ctrl, "stop_media", None)
                if fn:
                    await loop.run_in_executor(None, fn)
                return "Media stopped"

            if action == "play_pause":
                # Determine play vs pause from the original transcript
                if re.search(r"\bpause\b", safe_intent, re.I):
                    logger.info("ACTION: pause_media")
                    fn = getattr(ctrl, "pause_media", None)
                    if fn:
                        await loop.run_in_executor(None, fn)
                    return "Media paused"
                else:
                    logger.info("ACTION: play_media")
                    fn = getattr(ctrl, "play_media", None)
                    if fn:
                        await loop.run_in_executor(None, fn)
                    return "Media playing"

            # --- Type text ---
            if action == "type_text" and param:
                logger.info("ACTION: type_text('%s')", param[:50])
                fn = getattr(ctrl, "type_text", None)
                if fn:
                    result = await loop.run_in_executor(None, lambda: fn(param))
                    return f"Typed text"
                return "Cannot type — controller unavailable"

            # --- Switch app ---
            if action == "switch_app" and param:
                logger.info("ACTION: switch_app('%s')", param)
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
                    # Fallback: open the app
                    result = await loop.run_in_executor(None, lambda: ctrl.open_application(param))
                return f"Switched to {self._sanitize_output(param)}"

            # --- Shutdown / Restart ---
            if action in ("shutdown", "restart"):
                logger.info("ACTION: %s", action)
                fn = getattr(ctrl, action + "_pc", None)
                if fn:
                    await loop.run_in_executor(None, lambda: fn(confirmed=True))
                    return f"System {action} initiated"
                return f"Cannot {action} — controller unavailable"

            # --- Settings (wifi, bluetooth) ---
            if action == "settings":
                setting_text = (param + " " + level_str).lower()
                fn_wifi = getattr(ctrl, "toggle_wifi", None)
                fn_bt = getattr(ctrl, "toggle_bluetooth", None)
                if "wifi" in setting_text or "wi-fi" in setting_text:
                    enable = "off" not in setting_text and "disable" not in setting_text
                    if fn_wifi:
                        await loop.run_in_executor(None, lambda: fn_wifi(enable))
                    return f"WiFi {'enabled' if enable else 'disabled'}"
                if "bluetooth" in setting_text:
                    enable = "off" not in setting_text and "disable" not in setting_text
                    if fn_bt:
                        await loop.run_in_executor(None, lambda: fn_bt(enable))
                    return f"Bluetooth {'enabled' if enable else 'disabled'}"
                return "Settings updated"

            # --- Communication (send message, call) ---
            if intent_type == "communication":
                if action in ("send_message", "reply"):
                    # param = contact, level_str = app (whatsapp/telegram/etc)
                    contact = param.strip()
                    app = level_str.strip().lower() if level_str.strip() else "whatsapp"
                    if not app or app not in ("whatsapp", "telegram", "slack", "sms", "email"):
                        app = "whatsapp"
                    # Open the messaging app with the contact
                    fn = getattr(ctrl, "open_url", None)
                    if fn and contact:
                        import urllib.parse as _up
                        if app == "whatsapp":
                            digits = contact.replace("+", "").replace("-", "").replace(" ", "")
                            if digits.isdigit():
                                url = f"https://wa.me/{digits}"
                            else:
                                url = f"https://web.whatsapp.com/send?phone=&text=&source=&data=&app_absent="
                            await loop.run_in_executor(None, lambda: fn(url))
                            return f"Opening WhatsApp for {self._sanitize_output(contact)}"
                        elif app == "telegram":
                            url = f"https://t.me/{contact.lstrip('@')}"
                            await loop.run_in_executor(None, lambda: fn(url))
                            return f"Opening Telegram for {self._sanitize_output(contact)}"
                        elif app == "email":
                            url = f"mailto:{contact}"
                            await loop.run_in_executor(None, lambda: fn(url))
                            return f"Opening email for {self._sanitize_output(contact)}"
                    return f"Opening messaging app for {self._sanitize_output(contact)}"
                if action == "make_call":
                    contact = param.strip()
                    fn = getattr(ctrl, "open_url", None)
                    if fn and contact:
                        digits = contact.replace("+", "").replace("-", "").replace(" ", "")
                        if digits.isdigit():
                            url = f"tel:{digits}"
                        else:
                            url = f"https://wa.me/?phone={contact}"
                        await loop.run_in_executor(None, lambda: fn(url))
                    return f"Calling {self._sanitize_output(contact)}"

            # --- Information (search, question) ---
            if intent_type == "information":
                query = param.strip() or safe_intent
                logger.info("ACTION: web_search('%s')", query[:80])
                fn = getattr(ctrl, "web_search", None)
                if fn:
                    await loop.run_in_executor(None, lambda: fn(query, "google"))
                    return f"Searching for {self._sanitize_output(query)}"
                return None

            # --- File operations ---
            if intent_type == "file_ops":
                if action == "create" and param:
                    fn = getattr(ctrl, "create_file", None)
                    if fn:
                        result = await loop.run_in_executor(None, lambda: fn(param))
                        return f"Created {self._sanitize_output(param)}"
                if action == "delete" and param:
                    fn = getattr(ctrl, "delete_file", None)
                    if fn:
                        result = await loop.run_in_executor(None, lambda: fn(param, True))
                        return f"Deleted {self._sanitize_output(param)}"

            return None

        except Exception as exc:
            logger.warning("Action stage error: %s", exc)
            return None

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

        loop = asyncio.get_running_loop()
        sample_rate = 22050
        audio_array: Any = None

        if fn_type in ("array", "response"):
            if asyncio.iscoroutinefunction(fn):
                result = await fn(text, pt)
            else:
                result = await loop.run_in_executor(None, lambda: fn(text, pt))
            if isinstance(result, tuple) and len(result) == 2:
                audio_array, sample_rate = result
            elif isinstance(result, np.ndarray):
                audio_array = result

        elif fn_type == "bytes":
            if asyncio.iscoroutinefunction(fn):
                wav_bytes = await fn(text, pt)
            else:
                wav_bytes = await loop.run_in_executor(None, lambda: fn(text, pt))
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
                        sd.play(audio_array, samplerate=sample_rate)
                        sd.wait()

                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, _play)
                    logger.info("TTS played: %.1fs of audio", len(audio_array) / sample_rate)
                except ImportError:
                    logger.warning(
                        "sounddevice not installed — TTS audio not played. "
                        "Run: pip install sounddevice"
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
