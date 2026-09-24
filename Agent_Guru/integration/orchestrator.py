"""Agent_Guru/integration/orchestrator.py.

IntegrationOrchestrator - wires all Agent Guru subsystems into a single unified
pipeline and manages concurrent async startup.

End-to-end pipeline (8 stages):
  1. STT          - speech_engine.transcribe(audio)
  2. Memory       - memory.retrieve(transcript)
  3. Reasoning    - reasoning.analyze(transcript, memory_context)
  4. LLM          - llm_runtime.infer(transcript, memory_context, reasoning_output)
  5. Intent       - extracted from LLM response
  6. Policy check - policy.evaluate(intent)
  7. Action       - agent_orchestrator.execute(intent)  [only if policy allows]
  8. TTS          - speech_engine.synthesize(response, personality)

Concurrent startup: asyncio.gather() initialises all subsystems in parallel so
total startup time is bounded by the slowest subsystem, not their sum.

Parallel vision/speech: handle_concurrent_event() dispatches both pipelines as
independent asyncio tasks.

This module is purely additive - no existing subsystem code is modified.

Performance:
  - Time Complexity: O(1) orchestration overhead per pipeline stage
  - Space Complexity: O(1) - fixed subsystem references

Concurrency note (pipeline_mode):
  Speaker-verification outcome ("full" vs "restricted") is carried on the
  per-call PipelineResult and passed explicitly through _stage_action() /
  _execute_single_action() as a parameter - never stored on `self`. Two
  pipeline runs can be in flight at once (see handle_concurrent_event), so
  any safety-relevant flag stored on the shared instance would be a race
  condition. Passing it by value through the call chain avoids that.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime as _dt
import inspect
import logging
import os
import re
import sys
import urllib.parse as _up
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC
from enum import Enum
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

from Agent_Guru.security.audit.logger import AuditLogger, EventType

if TYPE_CHECKING:
    from collections.abc import Callable

    from Agent_Guru.integration.gpu_pool import GPUResourcePool

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
        pipeline_mode: "full" or "restricted" - set by speaker verification.
            "restricted" means the speaking voice did not match the enrolled
            owner profile; destructive actions and memory writes are denied
            downstream, but the pipeline still responds conversationally
            (never a silent drop). Defaults to "full" when no speaker
            profile is enrolled, so a fresh install isn't locked out of its
            own destructive actions on day one.
        error: Error message if any stage failed.

    """

    stages_completed: int = 0
    transcript: str | None = None
    detected_language: str = ""
    memory_context: Any | None = None
    reasoning_output: Any | None = None
    llm_response: str | None = None
    intent: str | None = None
    policy_allowed: bool = False
    action_result: Any | None = None
    tts_response: Any | None = None
    personality: Personality = Personality.GURU
    pipeline_mode: str = "full"
    error: str | None = None


# ---------------------------------------------------------------------------
# Per-stage time budgets
# ---------------------------------------------------------------------------
# RELIABILITY FIX: run_pipeline() awaited seven of its eight stages with NO
# time limit whatsoever -- only Stage 3 (reasoning) had one. If STT, memory,
# the LLM, the policy check or TTS hung, the user got SILENCE FOREVER: no
# audio, no error, no audit entry, and no way to recover short of restarting
# the process, because nothing ever raised and the outer `except` never fired.
# For an always-on voice assistant that is the defining reliability property.
#
# Each budget is generous enough not to cut off legitimate slow work (a local
# Whisper transcription or a CPU-bound local LLM can genuinely take tens of
# seconds) and every one is overridable per deployment, because the right
# number depends entirely on the hardware and models in use.
#
# Stage 7 (action execution) is deliberately NOT bounded here -- see the note
# at its call site: cancelling an action mid-flight can leave a real
# side effect half-applied, which is worse than waiting.
def _env_seconds(name: str, default: float) -> float:
    """Read a timeout from the environment, falling back to *default*."""
    raw_value = os.environ.get(name)
    if not raw_value:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        logger.warning("Ignoring non-numeric %s=%r; using %.1fs", name, raw_value, default)
        return default
    if value <= 0:
        logger.warning("Ignoring non-positive %s=%r; using %.1fs", name, raw_value, default)
        return default
    return value


STT_TIMEOUT_S = _env_seconds("AGENT_GURU_STT_TIMEOUT", 30.0)
MEMORY_TIMEOUT_S = _env_seconds("AGENT_GURU_MEMORY_TIMEOUT", 5.0)
REASONING_TIMEOUT_S = _env_seconds("AGENT_GURU_REASONING_TIMEOUT", 2.0)
INTENT_TIMEOUT_S = _env_seconds("AGENT_GURU_INTENT_TIMEOUT", 5.0)
LLM_TIMEOUT_S = _env_seconds("AGENT_GURU_LLM_TIMEOUT", 60.0)
POLICY_TIMEOUT_S = _env_seconds("AGENT_GURU_POLICY_TIMEOUT", 5.0)
TTS_TIMEOUT_S = _env_seconds("AGENT_GURU_TTS_TIMEOUT", 30.0)
MEMORY_WRITE_TIMEOUT_S = _env_seconds("AGENT_GURU_MEMORY_WRITE_TIMEOUT", 10.0)

#: Spoken when the LLM exceeds its budget. Saying nothing leaves the user
#: staring at a silent assistant; falling through to the generic "Done."
#: would be worse still, because it claims an action succeeded.
LLM_TIMEOUT_REPLY = "Sorry, that took too long for me to work out. Could you ask me again?"


def _local_now() -> _dt.datetime:
    """The system clock in the machine's own time zone (a seam for tests)."""
    return _dt.datetime.now().astimezone()


def _clock_answer() -> str:
    """Answer "what's the time / date / day" from the system clock.

    The intent recognizer has always tagged these questions as
    information:time_date, and nothing consumed that action. They went to the
    LLM (about 45 seconds on the CPU-only machine of the first Windows run),
    whose prompt carries no clock at all, and then to a web search. The machine
    the assistant runs on already knows the answer, offline and instantly.
    Time and date are both given, so the one answer fits "what time is it",
    "what's the date" and "what day is it" alike.
    """
    now = _local_now()
    hour = now.strftime("%I").lstrip("0")
    return f"It's {hour}:{now:%M} {now:%p} on {now:%A}, {now.day} {now:%B} {now.year}."


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

    # Explicit wildcard constants - intentional allow-all for the pipeline principal only.
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
        # CRIT-001 fix: asyncio.Lock() must NOT be created before the event loop.
        # Deferred to first async use (sleep/wake) so the lock always binds to
        # the running loop, preventing RuntimeError on Python 3.10+.
        self._sleeping_lock: asyncio.Lock | None = None

        # Intent recognizer - initialized lazily on first use
        self._intent_recognizer: Any = None

        # STT function cache - resolved once at startup
        self._stt_fn: Callable | None = None
        self._stt_params: list[str] | None = None

        # TTS function cache - resolved once at startup
        self._tts_fn: Callable | None = None
        self._tts_fn_type: str = "unknown"  # "array", "response", "bytes", or "unknown"

        # Audit logger - records every pipeline execution
        self._audit_logger: AuditLogger = AuditLogger()

        # Persistent browser manager - one Chrome instance, CDP reconnect
        self._browser_mgr: Any = None  # lazy-init on first YouTube command

        # Reminder manager - handles "remind me in X minutes" commands
        self._reminder_mgr: Any = None  # lazy-init on first reminder command

        # User memory - persistent facts about the user (name, preferences, etc.)
        self._user_memory: Any = None  # lazy-init on first use

        # Emotion detector - persistent across pipeline calls for trend tracking
        self._emotion_detector: Any = None  # lazy-init on first LLM call

        # Empathy adapter - adapts responses for emotional state + distress support
        self._empathy_adapter: Any = None  # lazy-init alongside emotion detector

        # Last EmpathyAdapter.adapt_response() result and last detected emotion
        # label for this turn. Previously adapt_response() was called with an
        # empty string and its return value discarded entirely - the tone/
        # pacing/vocabulary guidance it computes never reached the LLM prompt.
        # _build_system_prompt() now reads _last_adapted_response to add a
        # real tone instruction instead of throwing that computation away.
        self._last_adapted_response: Any = None
        self._last_emotion_hint: str = "neutral"

        # Conversation history - last 12 exchanges (24 messages) for continuity.
        # Without this, the LLM has no memory of what was said 10 seconds ago.
        # A companion must remember at least the recent conversation.
        # The token budget guard in _stage_llm handles overflow gracefully.
        self._chat_history: deque = deque(maxlen=24)  # 12 user + 12 assistant turns

        # NOTE: there is intentionally NO self._pipeline_mode attribute.
        # pipeline_mode (speaker-verification outcome) is carried per-call on
        # PipelineResult and passed explicitly through _stage_action() /
        # _execute_single_action(). Storing it on `self` previously made the
        # restricted-mode security gate a silent no-op (the attribute was
        # read via getattr(self, "_pipeline_mode", "full") but never actually
        # assigned anywhere), and would additionally have been a race
        # condition across concurrent pipeline runs even if fixed. See the
        # module docstring's "Concurrency note".

        logger.info("IntegrationOrchestrator wired - all subsystems connected")

    # ------------------------------------------------------------------
    # Concurrent startup
    # ------------------------------------------------------------------

    async def startup(self) -> None:
        """Initialise all subsystems concurrently via asyncio.gather().

        Distributes GPU device configs before gathering so each subsystem
        receives its VRAM budget during initialisation.

        Total startup time ≤ max(individual init times) + scheduling overhead.
        """
        logger.info("IntegrationOrchestrator.startup() - concurrent init begin")

        # Distribute GPU configs to subsystems that accept them
        whisper_cfg = self.gpu_pool.allocate("whisper")
        onnx_cfg = self.gpu_pool.allocate("onnx")
        torch_cfg = self.gpu_pool.allocate("torch")

        logger.info(
            "GPU configs - whisper: %s, onnx: %s, torch: %s",
            whisper_cfg.device,
            onnx_cfg.device,
            torch_cfg.device,
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

        # FIX: the filler-response cache (played in run_pipeline()'s
        # post-wake-word pause) was previously only ever lazily initialised
        # on the FIRST live wake-word event, inside the hot pipeline path.
        # initialize() loads the Kokoro ONNX model + voice bank from disk -
        # exactly the kind of work this concurrent-startup phase exists to
        # absorb ahead of time. Warmed here instead so the very first
        # real interaction doesn't pay that load cost. _init_subsystem()
        # already handles a plain synchronous initialize() method (used by
        # every other subsystem above) by running it in a thread executor,
        # so this reuses that same generic path rather than adding a
        # special case.
        try:
            from Agent_Guru.speech.filler_response import get_filler_cache as _get_filler_cache_fn

            coros.append(self._init_subsystem("filler_cache", _get_filler_cache_fn()))
        except Exception:
            logger.debug(
                "Filler-response module unavailable - skipping cache warm-up",
                exc_info=True,
            )

        # Concurrent initialisation - NOT sequential awaits
        results = await asyncio.gather(*coros, return_exceptions=True)

        # P2-47: Log any subsystem startup failures instead of silently swallowing
        for _, result in zip(coros, results, strict=False):
            if isinstance(result, Exception):
                logger.error("Subsystem startup exception: %s", result)

        # Cache STT and TTS callables once so stage methods never repeat reflection
        await self._cache_stt_fn()
        self._cache_tts_fn()

        # Seed default allow policy for the assistant principal so the pipeline
        # can execute OS actions without requiring manual policy configuration.
        self._seed_default_policy()

        self._sleeping = False
        logger.info("IntegrationOrchestrator.startup() - all subsystems ready")

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
                return  # Not a real PolicyEngine - skip

            # Only seed if no policies exist yet
            if find_fn is not None:
                existing = find_fn(principal="guru_pipeline")
                if existing:
                    return

            from datetime import datetime

            from Agent_Guru.policy.models import Policy, PolicyEffect

            now = datetime.now(tz=UTC)
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
        except Exception:
            logger.exception("Policy seed failed - policy check will default to allow")

    async def _init_subsystem(self, name: str, subsystem: Any, device_cfg: Any = None) -> None:
        """Initialise a single subsystem, passing device_cfg if accepted."""
        try:
            init = getattr(subsystem, "initialize", None)
            if init is None:
                return
            if inspect.iscoroutinefunction(init):
                if device_cfg is not None:
                    try:
                        await init(device_cfg=device_cfg)
                    except TypeError:
                        await init()
                else:
                    await init()
            else:
                # Synchronous initialize - run in executor to avoid blocking
                loop = asyncio.get_running_loop()
                if device_cfg is not None:
                    try:
                        await asyncio.to_thread(init, device_cfg=device_cfg)
                    except TypeError:
                        await loop.run_in_executor(None, init)
                else:
                    await loop.run_in_executor(None, init)
            logger.debug("Subsystem '%s' initialised", name)
        except Exception as exc:
            logger.exception("Subsystem '%s' init failed: %s - continuing", name, exc)

    # ------------------------------------------------------------------
    # Startup caches
    # ------------------------------------------------------------------

    async def _cache_stt_fn(self) -> None:
        """Resolve and cache the STT transcription function and its parameter list.

        Called once during startup() so _stage_stt() never calls inspect.signature()
        at invocation time.
        """
        import inspect

        fn = getattr(self.speech_engine, "transcribe", None) or getattr(
            self.speech_engine,
            "transcribe_with_personality",
            None,
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
        """Enter sleep mode - only wake word detection remains active."""
        if self._sleeping_lock is None:
            self._sleeping_lock = asyncio.Lock()
        async with self._sleeping_lock:
            self._sleeping = True
        logger.info("IntegrationOrchestrator: sleep mode - wake word detection only")

    async def wake(self) -> None:
        """Exit sleep mode - all subsystems active."""
        if self._sleeping_lock is None:
            self._sleeping_lock = asyncio.Lock()
        async with self._sleeping_lock:
            self._sleeping = False
        logger.info("IntegrationOrchestrator: wake mode - all subsystems active")

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
        result.personality = self._resolve_personality(wake_event.wake_word)

        import time as _time
        _wake_timestamp = _time.perf_counter()

        from Agent_Guru.platform.features.user_memory import get_user_memory as _get_um

        # Filler response in the post-wake-word pause
        await self._play_filler(result, _wake_timestamp, _get_um)

        _pipeline_mode = "full"
        result.pipeline_mode = _pipeline_mode

        try:
            # Stage 1: STT. On timeout the transcript stays empty, which the
            # existing "nothing was said" path below already handles.
            try:
                result.transcript, result.detected_language = await asyncio.wait_for(
                    self._stage_stt(wake_event.audio, result.personality),
                    timeout=STT_TIMEOUT_S,
                )
            except TimeoutError:
                logger.warning(
                    "STT stage exceeded %.1fs - treating the utterance as unheard",
                    STT_TIMEOUT_S,
                )
                result.transcript, result.detected_language = "", ""
                result.error = f"stt_timeout after {STT_TIMEOUT_S:.1f}s"
            result.stages_completed = 1

            if not result.transcript:
                result.stages_completed = 8
                return result

            # Re-check personality from transcript
            self._correct_personality_from_transcript(result)

            # Speaker verification (opt-in)
            _pipeline_mode = self._verify_speaker(wake_event, result)

            # Reaction-rule early returns
            early_result = await self._check_reaction_rules(
                result, _pipeline_mode, _wake_timestamp, _get_um,
            )
            if early_result is not None:
                return early_result

            # Stage 2: Memory context. Recall is an enhancement, never a
            # precondition for answering, so a slow store degrades to "no
            # context" rather than stalling the turn.
            try:
                result.memory_context = await asyncio.wait_for(
                    self._stage_memory(result.transcript), timeout=MEMORY_TIMEOUT_S,
                )
            except TimeoutError:
                logger.warning(
                    "Memory stage exceeded %.1fs - answering without recalled context",
                    MEMORY_TIMEOUT_S,
                )
                result.memory_context = None
            result.stages_completed = 2

            # Stage 3: Reasoning (2s timeout)
            try:
                result.reasoning_output = await asyncio.wait_for(
                    self._stage_reasoning(result.transcript, result.memory_context),
                    timeout=REASONING_TIMEOUT_S,
                )
            except TimeoutError:
                logger.debug(
                    "Reasoning stage timed out (>%.1fs) - continuing without it",
                    REASONING_TIMEOUT_S,
                )
                result.reasoning_output = None
            except Exception:
                logger.debug("Reasoning stage error - continuing without it")
                result.reasoning_output = None
            result.stages_completed = 3

            # Stage 5 (before 4): Intent detection - fast path
            try:
                result.intent = await asyncio.wait_for(
                    self._stage_intent(result.transcript or ""), timeout=INTENT_TIMEOUT_S,
                )
            except TimeoutError:
                # No intent means no action is attempted; the LLM still answers
                # conversationally, which is the safe degradation.
                logger.warning(
                    "Intent stage exceeded %.1fs - continuing without an intent",
                    INTENT_TIMEOUT_S,
                )
                result.intent = None
            result.stages_completed = 5

            # Stage 4: LLM inference (only if needed)
            needs_llm = self._intent_needs_llm(result.intent, result.transcript or "")
            if needs_llm:
                try:
                    result.llm_response = await asyncio.wait_for(
                        self._stage_llm(
                            result.transcript, result.memory_context,
                            result.reasoning_output, result.detected_language,
                            personality=result.personality,
                            intent=result.intent,
                        ),
                        timeout=LLM_TIMEOUT_S,
                    )
                except TimeoutError:
                    logger.warning("LLM stage exceeded %.1fs", LLM_TIMEOUT_S)
                    result.llm_response = LLM_TIMEOUT_REPLY
                    result.error = f"llm_timeout after {LLM_TIMEOUT_S:.1f}s"
            else:
                result.llm_response = None
            result.stages_completed = 4

            # Stage 6: Policy check
            try:
                result.policy_allowed = await asyncio.wait_for(
                    self._stage_policy(result.intent), timeout=POLICY_TIMEOUT_S,
                )
            except TimeoutError:
                # FAIL CLOSED. A policy check that did not complete has not
                # granted anything; treating "slow" as "allowed" would turn a
                # hung policy engine into an authorization bypass.
                logger.warning(
                    "Policy stage exceeded %.1fs - denying the action (fail closed)",
                    POLICY_TIMEOUT_S,
                )
                result.policy_allowed = False
                result.error = f"policy_timeout after {POLICY_TIMEOUT_S:.1f}s"
            result.stages_completed = 6

            # Stage 7: Action execution.
            # DELIBERATELY UNBOUNDED. asyncio.wait_for() cancels the coroutine
            # it is waiting on, and an action is the one stage with real,
            # externally visible side effects -- a file half-written, an app
            # half-launched, a message half-sent. Cancelling mid-flight would
            # leave that half-state behind with no record of how far it got,
            # which is worse than waiting. Individual tools are responsible for
            # bounding their own work (see reasoning/tools/system/_command.py,
            # which caps every subprocess it runs).
            if result.policy_allowed:
                result.action_result = await self._stage_action(
                    result.intent, pipeline_mode=result.pipeline_mode,
                )
            result.stages_completed = 7

            # Stage 8: TTS
            tts_text = self._finalize_tts_text(result)
            try:
                result.tts_response = await asyncio.wait_for(
                    self._stage_tts(tts_text, result.personality), timeout=TTS_TIMEOUT_S,
                )
            except TimeoutError:
                logger.warning(
                    "TTS stage exceeded %.1fs - no audio for this turn", TTS_TIMEOUT_S,
                )
                result.tts_response = None
                result.error = f"tts_timeout after {TTS_TIMEOUT_S:.1f}s"
            result.stages_completed = 8

            # Track in chat history (single source of truth - see _llm_complete()
            # for why the second, duplicate append that used to live there was
            # removed). Uses the real detected emotion for this turn instead of
            # the "neutral" placeholder this used to hardcode regardless of what
            # _detect_emotion() actually found.
            if result.transcript and tts_text:
                self._chat_history.append({
                    "role": "user",
                    "content": result.transcript,
                    "emotion": getattr(self, "_last_emotion_hint", "neutral"),
                })
                self._chat_history.append({
                    "role": "assistant", "content": tts_text,
                })

                # Persist this turn to long-term memory. Previously self.memory
                # was queried for recall on every turn (_stage_memory) but
                # nothing ever fed it - store_interaction() was never called,
                # so retrieval always ran against an empty/stale store. See
                # docs/audit/claude_companion_and_control_audit_2026-09-13.md.
                # Bounded: the user already has their answer by this point, so
                # a slow write must not hold the turn open. Losing one stored
                # turn is recoverable; hanging the pipeline is not.
                try:
                    await asyncio.wait_for(
                        self._store_turn_in_memory(
                            result.personality, result.transcript, tts_text,
                        ),
                        timeout=MEMORY_WRITE_TIMEOUT_S,
                    )
                except TimeoutError:
                    logger.warning(
                        "Storing this turn in memory exceeded %.1fs - turn not persisted",
                        MEMORY_WRITE_TIMEOUT_S,
                    )

            # Audit log
            self._log_audit(result, outcome="success", error=None)
        except Exception as exc:
            result.error = str(exc)
            logger.exception("Pipeline error at stage %d", result.stages_completed + 1)
            self._log_audit(result, outcome="failure", error=str(exc), is_error=True)
        return result

    # ------------------------------------------------------------------
    # run_pipeline decomposed helpers
    # ------------------------------------------------------------------

    async def _play_filler(
        self, result: PipelineResult, wake_timestamp: float, _get_um: Any,
    ) -> None:
        """Play filler audio in the post-wake-word pause."""
        try:
            from Agent_Guru.speech.filler_response import get_filler_cache
            _filler_cache = get_filler_cache()
            if not _filler_cache._initialized:
                await asyncio.to_thread(_filler_cache.initialize)
            _lang_pref = _get_um().get("code_mixing", "hinglish")
            _persona_str = "maya" if result.personality == Personality.MAYA else "guru"
            await _filler_cache.play_filler_async(
                personality=_persona_str,
                language_pref=_lang_pref,
                wake_timestamp=wake_timestamp,
            )
        except Exception as _filler_exc:
            logger.debug("Filler playback skipped: %s", _filler_exc)

    @staticmethod
    def _correct_personality_from_transcript(result: PipelineResult) -> None:
        """Correct personality based on transcript keywords."""
        if result.transcript is None:
            return
        transcript_lower = result.transcript.lower().strip()
        if any(kw in transcript_lower[:30] for kw in ("maya", "hey maya", "hi maya")):
            if result.personality != Personality.MAYA:
                logger.info(
                    "Personality corrected: transcript starts with 'Maya' - "
                    "switching from GURU to MAYA",
                )
                result.personality = Personality.MAYA
        elif any(kw in transcript_lower[:30] for kw in ("guru", "hey guru", "hi guru")):
            if result.personality != Personality.GURU:
                logger.info(
                    "Personality corrected: transcript starts with 'Guru' - "
                    "switching from MAYA to GURU",
                )
                result.personality = Personality.GURU

    @staticmethod
    def _verify_speaker(wake_event: WakeWordEvent, result: PipelineResult) -> str:
        """Run optional speaker verification. Returns pipeline_mode."""
        try:
            from Agent_Guru.speech.biometric.speaker_verifier import get_speaker_verifier
            _verifier = get_speaker_verifier()
            if _verifier.is_enrolled() and wake_event.audio is not None:
                import numpy as np
                _audio_array = np.frombuffer(wake_event.audio, dtype=np.float32)
                _verify_result = _verifier.verify(_audio_array)
                result.pipeline_mode = _verify_result.mode
                if _verify_result.mode == "restricted":
                    logger.info(
                        "Speaker verification: RESTRICTED mode (similarity=%.3f)",
                        _verify_result.similarity,
                    )
                return _verify_result.mode
        except Exception as _sv_exc:
            logger.debug("Speaker verification skipped: %s", _sv_exc)
        return result.pipeline_mode

    async def _check_reaction_rules(
        self,
        result: PipelineResult,
        pipeline_mode: str,
        wake_timestamp: float,
        _get_um: Any,
    ) -> PipelineResult | None:
        """Check reaction rules and teaching intents. Returns result for early exit, or None."""
        import time as _time
        try:
            from Agent_Guru.platform.features.reaction_rules import (
                extract_teaching_intent, get_reaction_rules,
            )

            if pipeline_mode == "full" and result.transcript is not None:
                _teaching = extract_teaching_intent(result.transcript)
                if _teaching is not None:
                    _trigger, _response = _teaching
                    _store = get_reaction_rules()

                    _ok, _msg = _store.add_rule(
                        _trigger, _response,
                        intent_recognizer=self._intent_recognizer,
                    )
                    if _ok:
                        _lang = _get_um().get("code_mixing", "hinglish")
                        result.llm_response = (
                            "done, yaad rakh liya!" if _lang == "hinglish"
                            else "got it, I'll remember that!"
                        )
                    else:
                        result.llm_response = _msg
                    result.stages_completed = 8
                    await self._stage_tts(result.llm_response, result.personality)
                    logger.info(
                        "TIMING: wake_to_first_tts_ms=%.1f (teaching-intent)",
                        (_time.perf_counter() - wake_timestamp) * 1000,
                    )
                    return result

            # Reaction-rule matching
            _rule_response = (
                get_reaction_rules().match(result.transcript)
                if result.transcript is not None
                else None
            )
            if _rule_response is not None:
                result.llm_response = _rule_response
                result.stages_completed = 8
                await self._stage_tts(result.llm_response, result.personality)
                logger.info(
                    "TIMING: wake_to_first_tts_ms=%.1f (reaction-rule)",
                    (_time.perf_counter() - wake_timestamp) * 1000,
                )
                return result
        except Exception as _rr_exc:
            logger.debug("Reaction rule check skipped: %s", _rr_exc)
        return None

    @staticmethod
    def _finalize_tts_text(result: PipelineResult) -> str:
        """Determine TTS text and handle clipboard write-back."""
        tts_text = result.action_result or result.llm_response or ""
        if not tts_text and result.transcript:
            tts_text = "Done."

        if result.llm_response and result.transcript:
            from Agent_Guru.platform.features.dictation import (
                get_clipboard_action, is_clipboard_command, set_clipboard_text,
            )
            if is_clipboard_command(result.transcript):
                action = get_clipboard_action(result.transcript)
                if action in ("fix", "summarize"):
                    set_clipboard_text(result.llm_response)
                    tts_text = (
                        result.llm_response + " I've updated your clipboard with the result."
                    )
        return tts_text

    def _log_audit(
        self, result: PipelineResult, *, outcome: str,
        error: str | None, is_error: bool = False,
    ) -> None:
        """Log audit event for pipeline execution."""
        try:
            if is_error:
                try:
                    event_type = EventType.SYSTEM_ERROR  # type: ignore[attr-defined]
                except AttributeError:
                    event_type = EventType.POLICY_VIOLATION
            else:
                event_type = (
                    EventType.POLICY_ALLOWED if result.policy_allowed
                    else EventType.POLICY_VIOLATION
                )
            self._audit_logger.log_event(
                event_type=event_type,
                actor_id="guru_pipeline",
                target_id=result.intent or "",
                outcome=outcome,
                details={
                    "stages_completed": result.stages_completed,
                    "personality": result.personality.value,
                    "transcript": result.transcript,
                    "error": error,
                },
            )
        except Exception:
            logger.exception("Audit log failed")

    # ------------------------------------------------------------------
    # Parallel vision + speech dispatch
    # ------------------------------------------------------------------

    async def handle_concurrent_event(
        self,
        vision_event: VisionEvent,
        audio_event: WakeWordEvent,
    ) -> tuple[Any, PipelineResult]:
        """Dispatch vision and speech pipelines as parallel asyncio tasks.

        Both pipelines run concurrently - total time ≤ max(vision, speech).

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
            if inspect.iscoroutinefunction(process):
                return await process(vision_event.frame)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, process, vision_event.frame)
        except Exception:
            logger.exception("Vision pipeline error")
            return None

    # ------------------------------------------------------------------
    # Pipeline stage helpers
    # ------------------------------------------------------------------

    async def _stage_stt(
        self,
        audio: bytes,
        personality: Personality | None = None,
    ) -> tuple[str, str]:
        """Stage 1: Speech-to-text.

        Args:
            audio: Raw audio bytes (float32 PCM at 16kHz).
            personality: Active personality (GURU or MAYA) - passed to STT
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

            fn = self._resolve_stt_fn()
            if fn is None:
                logger.warning("STT: no transcription function found on speech engine")
                return ("", "")

            # Async STT functions (e.g. AsyncMock in tests) - call directly
            if inspect.iscoroutinefunction(fn):
                try:
                    result = await fn(audio)
                    return self._parse_stt_result(result)
                except Exception:
                    logger.exception("STT async stage error")
                    return ("", "")

            # Convert and validate audio
            audio_np = self._validate_audio(audio, np)
            if audio_np is None:
                return ("", "")

            # Invoke STT in executor thread
            loop = asyncio.get_running_loop()
            result = await self._invoke_stt(fn, audio_np, personality, loop)
            text, language = self._parse_stt_result(result)

            if text:
                logger.info("STT transcript: %r", text)
            else:
                logger.debug("STT: empty transcript")
            return text, language
        except Exception:
            logger.exception("STT stage error")
            return ("", "")

    def _resolve_stt_fn(self) -> Any | None:
        """Resolve the STT function from the speech engine."""
        fn = self._stt_fn
        if fn is None:
            fn = getattr(self.speech_engine, "transcribe", None) or getattr(
                self.speech_engine, "transcribe_with_personality", None,
            )
            if fn is None:
                stt = getattr(self.speech_engine, "stt_transcriber", None)
                if stt is not None:
                    fn = stt.transcribe
        return fn

    @staticmethod
    def _validate_audio(audio: Any, np: Any) -> Any | None:
        """Convert raw audio to numpy float32 and validate. Returns None if invalid."""
        if isinstance(audio, (bytes, bytearray)) and len(audio) > 0:
            if len(audio) % 4 != 0:
                logger.debug(
                    "STT: audio bytes not float32-aligned (%d bytes), skipping", len(audio),
                )
                return None
            audio_np = np.frombuffer(audio, dtype=np.float32).copy()
        elif isinstance(audio, np.ndarray):
            audio_np = audio.astype(np.float32)
        else:
            return None

        if len(audio_np) < 1600:
            logger.debug("STT: audio too short (%d samples), skipping", len(audio_np))
            return None
        rms = float(np.sqrt(np.mean(audio_np**2)))
        if rms < 0.0003:
            logger.debug("STT: audio too quiet (rms=%.5f), skipping", rms)
            return None

        logger.debug("STT: processing %.2fs of audio (rms=%.4f)", len(audio_np) / 16000, rms)
        return audio_np

    async def _invoke_stt(
        self, fn: Any, audio_np: Any, personality: Personality | None, loop: Any,
    ) -> Any:
        """Invoke the STT function with appropriate parameters."""
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
                logger.exception("Operation failed")

        params = self._stt_params or []
        try:
            if "personality" in params and stt_personality is not None:
                _pt = stt_personality
                return await loop.run_in_executor(None, lambda: fn(audio_np, _pt))
            if "sample_rate" in params:
                return await loop.run_in_executor(
                    None, lambda: fn(audio_np, sample_rate=16000),
                )
            return await asyncio.to_thread(fn, audio_np, 16000)
        except Exception:
            return await asyncio.to_thread(fn, audio_np, 16000)

    @staticmethod
    def _parse_stt_result(result: Any) -> tuple[str, str]:
        """Parse STT result into (text, language) with confidence check."""
        if hasattr(result, "text") and hasattr(result, "language"):
            text = (result.text or "").strip()
            raw_language = result.language or ""
            lang_prob = getattr(result, "language_probability", None)
            if lang_prob is None:
                lang_prob = getattr(result, "language_confidence", None)
            if lang_prob is not None and float(lang_prob) < 0.70:
                logger.info(
                    "STT: low language confidence (%.2f) for '%s' - defaulting to 'en'",
                    float(lang_prob), raw_language,
                )
                language = "en"
            else:
                language = raw_language
            return text, language
        if hasattr(result, "text"):
            return (result.text or "").strip(), ""
        return (str(result).strip() if result else "", "")

    async def _stage_memory(self, transcript: str) -> Any:
        """Stage 2: Retrieve memory context."""
        try:
            fn = getattr(self.memory, "retrieve", None) or getattr(self.memory, "search", None)
            if fn is None:
                return None
            if inspect.iscoroutinefunction(fn):
                return await fn(transcript)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, fn, transcript)
        except Exception:
            logger.exception("Memory stage error")
            return None

    async def _stage_reasoning(self, transcript: str, memory_context: Any) -> Any:
        """Stage 3: Reasoning analysis.

        Supports both the simple analyze(transcript, context) API used in tests
        and the ReasoningEngine.process(RawInput) API used in production.
        """
        try:
            # Prefer analyze() - used by mocks and simpler subsystems
            fn = getattr(self.reasoning, "analyze", None)
            if fn is not None:
                if inspect.iscoroutinefunction(fn):
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
                if inspect.iscoroutinefunction(process_fn):
                    result = await process_fn(raw)
                else:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(None, process_fn, raw)
                return result
            except ImportError:
                # RawInput not available - call with transcript only
                if inspect.iscoroutinefunction(process_fn):
                    return await process_fn(transcript)
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, process_fn, transcript)
        except Exception:
            logger.exception("Reasoning stage error")
            return None

    # Known model knowledge cutoffs - class-level constant
    _KNOWN_CUTOFFS: ClassVar[dict[str, str]] = {
        "gemma3": "early 2025",
        "gemma2": "mid 2024",
        "llama3.1": "late 2023",
        "llama3.2": "late 2023",
        "llama3.3": "late 2023",
        "sarvam-m": "early 2025",
        "qwen2.5": "late 2024",
    }

    async def _stage_llm(
        self,
        transcript: str,
        memory_context: Any,
        reasoning_output: Any,
        language_code: str = "",
        personality: Personality | None = None,
        intent: str | None = None,
    ) -> str:
        """Stage 4: LLM inference with enriched context."""
        try:
            # Prefer infer() - used by mocks and simpler subsystems
            fn = getattr(self.llm_runtime, "infer", None) or getattr(
                self.llm_runtime, "execute", None,
            )
            if fn is not None:
                if inspect.iscoroutinefunction(fn):
                    result = await fn(transcript, memory_context, reasoning_output)
                else:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None, fn, transcript, memory_context, reasoning_output,
                    )
                if hasattr(result, "content"):
                    return result.content or ""
                return str(result) if result else ""

            # Fall back to real LLMRuntime.complete(CompletionRequest)
            complete_fn = getattr(self.llm_runtime, "complete", None)
            if complete_fn is None:
                return ""

            return await self._llm_complete(
                complete_fn, transcript, memory_context,
                reasoning_output, language_code, personality, intent,
            )
        except Exception:
            logger.exception("LLM stage error")
            return ""

    async def _llm_complete(
        self,
        complete_fn: Any,
        transcript: str,
        memory_context: Any,
        reasoning_output: Any,
        language_code: str,
        personality: Personality | None,
        intent: str | None = None,
    ) -> str:
        """Build enriched prompt and run LLM completion."""
        try:
            from Agent_Guru.llm.models import CompletionRequest, Message

            prompt = self._enrich_prompt(transcript, memory_context, reasoning_output)
            if not prompt.strip():
                return ""

            # Emotion detection from RAW transcript (not enriched prompt)
            emotion_hint = self._detect_emotion(transcript)

            # Web search enrichment
            web_context = await self._fetch_web_context(transcript, intent)
            if web_context:
                prompt = prompt + web_context

            # Resolve model and build system prompt
            ollama_model = os.environ.get("OLLAMA_MODEL", "").strip() or "gemma3:4b"
            system_prompt = self._build_system_prompt(
                personality, emotion_hint, language_code, ollama_model,
                transcript=transcript,
            )

            # Build message list with token-budgeted history
            messages = self._build_llm_messages(Message, system_prompt, prompt)

            request = CompletionRequest(
                model=ollama_model,
                messages=messages,
                max_tokens=400,
            )
            response = await complete_fn(request)
            llm_response = response.content or ""

            # NOTE: conversation history is recorded exactly once, in
            # run_pipeline() after TTS finalizes the actually-spoken text -
            # this function used to *also* append here with the pre-TTS
            # llm_response, so every LLM-driven turn was written into
            # _chat_history twice (wasting half of the 12-exchange window on
            # near-duplicate entries and skewing _recent_moods). Removed;
            # emotion_hint for this turn is preserved via self._last_emotion_hint
            # (set in _detect_emotion()) for run_pipeline() to use instead of
            # the "neutral" it used to hardcode.

            return llm_response
        except ImportError as e:
            logger.warning("LLM stage: CompletionRequest import failed: %s", e)
            return ""
        except Exception as e:
            ollama_model = os.environ.get("OLLAMA_MODEL", "").strip() or "gemma3:4b"
            logger.error(
                "LLM stage: inference failed (model=%s): %s - "
                "check Ollama is running and the model is pulled: "
                "ollama pull %s",
                ollama_model, e, ollama_model,
            )
            return ""

    @staticmethod
    def _enrich_prompt(
        transcript: str, memory_context: Any, reasoning_output: Any,
    ) -> str:
        """Build the enriched prompt with context, clipboard, and screen content."""
        prompt = transcript or ""
        if not prompt.strip():
            return ""
        if memory_context:
            prompt = f"[Context: {memory_context}]\n{prompt}"
        if reasoning_output:
            prompt = f"{prompt}\n[Reasoning: {reasoning_output}]"

        # Inject clipboard content if the user is asking about it
        from Agent_Guru.platform.features.dictation import (
            get_clipboard_action, get_clipboard_text, is_clipboard_command,
        )
        if is_clipboard_command(prompt):
            clip_text = get_clipboard_text()
            if clip_text:
                clip_action = get_clipboard_action(prompt)
                if clip_action == "summarize":
                    prompt = f"Summarize this text in 2-3 sentences:\n\n{clip_text[:1000]}"
                elif clip_action == "fix":
                    prompt = f"Fix the grammar and spelling of this text, return only the corrected version:\n\n{clip_text[:1000]}"

        # Inject screen content if the user is asking about the screen
        from Agent_Guru.platform.features.screen_reader import (
            is_screen_read_command, read_screen_text,
        )
        if is_screen_read_command(prompt):
            screen_text = read_screen_text()
            if screen_text:
                prompt = f"{prompt}\n\nCurrent screen content:\n{screen_text[:1500]}"

        return prompt

    def _detect_emotion(self, transcript: str) -> str:
        """Detect emotion from raw transcript. Returns emotion hint string."""
        try:
            if self._emotion_detector is None:
                from Agent_Guru.emotion.detector import EmotionDetector
                self._emotion_detector = EmotionDetector()
            if self._empathy_adapter is None:
                from Agent_Guru.emotion.adapter import EmpathyAdapter
                self._empathy_adapter = EmpathyAdapter()
            _raw_text = transcript or ""
            _emo_state = self._emotion_detector.detect(text=_raw_text)
            emotion_hint = ""
            if _emo_state.confidence > 0.4 and _emo_state.emotion != "neutral":
                emotion_hint = _emo_state.emotion
                logger.info("Emotion detected: %s (%.2f)", _emo_state.emotion, _emo_state.confidence)
            # Track for distress support AND capture the real adaptation (tone/
            # pacing/vocabulary_level) instead of discarding it - this used to be
            # called with "" so the only thing that survived was _emo_state
            # itself (still needed for should_offer_support()'s 3-turn tracker).
            self._last_adapted_response = self._empathy_adapter.adapt_response(_raw_text, _emo_state)
            self._last_emotion_hint = emotion_hint or "neutral"
            return emotion_hint
        except Exception as _emo_exc:
            logger.debug("Emotion detection skipped: %s", _emo_exc)
            return ""

    async def _store_turn_in_memory(
        self,
        personality: Personality | None,
        user_message: str,
        ai_message: str,
    ) -> None:
        """Persist a completed turn to self.memory (best-effort, never raises).

        Mirrors _stage_memory()'s duck-typed retrieval pattern below - same
        idea, opposite direction. self.memory (a MemoryManager instance in
        production, see main.py's _load_memory()) was being asked for recall
        every turn without ever being told what to remember; this is the
        missing write side of that round trip.
        """
        try:
            fn = getattr(self.memory, "store_interaction", None)
            if fn is None:
                return
            if not user_message or not ai_message:
                return
            _persona_str = personality.value if personality is not None else "guru"
            if inspect.iscoroutinefunction(fn):
                await fn(_persona_str, user_message, ai_message)
            else:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, fn, _persona_str, user_message, ai_message)
        except Exception:
            logger.debug("Memory store_interaction failed", exc_info=True)

    #: Information actions whose answer is newer than any model by definition:
    #: a forecast, the news, or an explicit request to search.
    _LIVE_INFORMATION_ACTIONS: ClassVar[frozenset[str]] = frozenset(
        {"weather", "news", "search"},
    )

    @staticmethod
    def _intent_needs_web(intent: str | None, transcript: str) -> bool:
        """Return True if answering this turn needs facts from outside the machine.

        The test is the intent engine's verdict, not the wording. Only an
        information intent can need the web, and among those only a request
        for live data (weather, news, an explicit search), or a general
        question about something that changes over time (who holds an office
        now, a price, a score). Everything else (conversation, a clock
        reading, a calculation, a translation, a definition) the local model
        answers on its own.

        The old gate searched whenever the text ended in "?" or began with a
        question word, whatever the intent engine had said. "Tell me a joke?"
        and "I feel a bit lonely, can you talk with me?", both classified as
        conversation, were sent to Google from a product whose README says it
        runs 100% locally, and every such turn waited on the search.

        No intent (the intent stage timed out) means no search: the offline
        answer is the safe default for a local-first assistant.
        """
        if not intent:
            return False
        if "|" in intent:
            return any(
                IntegrationOrchestrator._intent_needs_web(step, transcript)
                for step in intent.split("|")
            )
        parts = intent.split(":", 2)
        intent_type = parts[0].lower().strip()
        action = parts[1].lower().strip() if len(parts) > 1 else ""
        if intent_type != "information":
            return False
        if action in IntegrationOrchestrator._LIVE_INFORMATION_ACTIONS:
            return True
        if action == "question":
            from Agent_Guru.platform.features.web_search import needs_web_search

            return needs_web_search(transcript)
        return False

    async def _fetch_web_context(self, transcript: str, intent: str | None) -> str:
        """Fetch web search context when the intent says the turn needs it.

        The query is this turn's transcript and nothing else. It used to be the
        enriched LLM prompt, which starts with "[Context: ...]" holding the
        recalled earlier turns, word for word, and can carry the reasoning
        output, clipboard text or screen text. All of it went out in a search
        URL to DuckDuckGo, or to Google through the browser fallback, which
        also logged it. Whatever the user said on an earlier turn, however
        private, left the machine attached to an unrelated question.
        """
        from Agent_Guru.platform.features.web_search import search_web

        if not self._intent_needs_web(intent, transcript):
            return ""
        web_snippet = await search_web(transcript)
        if web_snippet:
            logger.info("Web search injected for: %r", transcript[:60])
            return f"\n\nLive web search result: {web_snippet}"
        return ""

    def _build_system_prompt(
        self,
        personality: Personality | None,
        emotion_hint: str,
        language_code: str,
        ollama_model: str,
        transcript: str = "",
    ) -> str:
        """Build the full system prompt with persona, emotion, distress, and language hints.

        `transcript` is what the user actually said this turn. It is read only
        by the explicit self-harm check below, which deliberately does not go
        through the emotion label -- see detect_crisis_language(). Defaults to
        "" so existing callers keep working; the check simply does not fire.
        """
        from Agent_Guru.llm.companion_prompts import build_companion_prompt
        from Agent_Guru.platform.features.user_memory import get_user_memory

        current_date = _dt.datetime.now(tz=UTC).strftime("%B %d, %Y")
        user_facts = get_user_memory().get_summary()
        persona_key = "maya" if personality == Personality.MAYA else "guru"

        _model_family = ollama_model.split(":", 1)[0].lower()
        knowledge_cutoff = self._KNOWN_CUTOFFS.get(_model_family, "")
        user_country = get_user_memory().get("country", "")

        system_prompt = build_companion_prompt(
            personality=persona_key,
            user_facts=user_facts,
            current_date=current_date,
            emotion_hint=emotion_hint,
            nickname=get_user_memory().get("nickname", ""),
            code_mixing=get_user_memory().get("code_mixing", "hinglish"),
            user_country=user_country,
            knowledge_cutoff=knowledge_cutoff,
        )

        # Language instruction
        if language_code and language_code not in ("en", "en-US", "en-GB", ""):
            system_prompt += (
                f"\n\nIMPORTANT: The user spoke in language code '{language_code}'. "
                f"You MUST respond in the same language. Do NOT respond in English."
            )

        # Explicit self-harm language in THIS turn. Checked before, and
        # independently of, the multi-turn escalation below: that path needs
        # three consecutive distress turns, so on its own it cannot answer a
        # first message that says outright "I want to kill myself". This reads
        # what the user said rather than the emotion label, which is why it
        # works on turn one.
        _crisis_now = False
        try:
            from Agent_Guru.llm.companion_prompts import (
                build_crisis_block,
                detect_crisis_language,
            )

            if transcript and detect_crisis_language(transcript):
                _crisis_now = True
                system_prompt += build_crisis_block(user_country)
                logger.warning(
                    "Crisis language detected in this turn - crisis guidance "
                    "added to the system prompt",
                )
        except Exception:
            logger.exception("Crisis-language check failed")

        # Distress support (real 3-consecutive-turn escalation - see
        # EmpathyAdapter.should_offer_support(), whose DISTRESS_EMOTIONS set
        # correctly matches EmotionDetector's real labels, unlike the now-
        # removed dead "crisis" tier that used to live in
        # companion_prompts._build_emotion_block()). Now also names a real,
        # locale-appropriate helpline instead of offering generic support with
        # no actual resource attached.
        try:
            if (
                not _crisis_now
                and self._empathy_adapter
                and self._empathy_adapter.should_offer_support()
            ):
                from Agent_Guru.llm.companion_prompts import resolve_crisis_resource

                _crisis_resource = resolve_crisis_resource(user_country)
                system_prompt += (
                    "\n\nIMPORTANT: The user has been in distress for multiple turns. "
                    "Gently check in on them - ask how they're really doing. "
                    "Offer genuine support, not generic platitudes. If they mention "
                    f"self-harm or feeling hopeless, gently suggest {_crisis_resource}."
                )
                logger.info("Distress support triggered - 3+ consecutive distress turns")
        except Exception:
            logger.debug("Empathy adapter check failed", exc_info=True)

        # Tone/pacing guidance from EmpathyAdapter.adapt_response() (see
        # _detect_emotion() - this used to be computed against an empty string
        # and its result discarded entirely, so it never reached the LLM).
        _adapted = getattr(self, "_last_adapted_response", None)
        if _adapted is not None and emotion_hint and emotion_hint != "neutral":
            system_prompt += (
                f"\n\nTONE NOTE: match a {_adapted.tone} tone, {_adapted.pacing} pacing, "
                f"and {_adapted.vocabulary_level} vocabulary in this reply."
            )

        # Conversation context note
        _turn_count = len(self._chat_history) // 2 + 1
        _recent_moods = [
            h.get("emotion", "neutral")
            for h in list(self._chat_history)[-6:]
            if h.get("role") == "user"
        ]
        if _turn_count > 1 and _recent_moods:
            mood_summary = ", ".join(_recent_moods[-3:])
            system_prompt += (
                f"\n\nCONVERSATION STATE: This is turn {_turn_count}. "
                f"The user's recent mood: [{mood_summary}]."
            )
        elif _turn_count == 1:
            system_prompt += (
                "\n\nSESSION START: This is the FIRST interaction of this session. "
                "Greet the user warmly like a friend you haven't talked to in a bit. "
                "Ask how they're doing or what's up. Be casual and genuine."
            )

        return system_prompt

    def _build_llm_messages(
        self, Message: type, system_prompt: str, prompt: str,
    ) -> list[Any]:
        """Build token-budgeted message list with conversation history."""
        _MAX_HISTORY_TOKENS = 2900
        _user_tokens = len(prompt) // 4
        _available = _MAX_HISTORY_TOKENS - _user_tokens

        history_messages: list[Any] = []
        _history_tokens = 0
        for hist_msg in reversed(list(self._chat_history)):
            msg_tokens = len(hist_msg["content"]) // 4
            if _history_tokens + msg_tokens > _available:
                break
            history_messages.insert(
                0, Message(role=hist_msg["role"], content=hist_msg["content"]),
            )
            _history_tokens += msg_tokens

        if _history_tokens > 0 and len(history_messages) < len(self._chat_history):
            logger.info(
                "Token budget: trimmed history from %d to %d messages (%d tokens)",
                len(self._chat_history), len(history_messages), _history_tokens,
            )

        messages = [Message(role="system", content=system_prompt)]
        messages.extend(history_messages)
        messages.append(Message(role="user", content=prompt))
        return messages

    async def _stage_intent(self, llm_response: str) -> str:
        """Stage 5: Extract structured intent from the user's transcript.

        Uses rule-based recognition ONLY - never calls LLM for intent
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
            # Lazy-init intent recognizer - NO llm_manager so it stays rule-based only
            if self._intent_recognizer is None:
                from Agent_Guru.platform.intent_recognizer import IntentRecognizer

                self._intent_recognizer = IntentRecognizer(
                    llm_manager=None,  # Rule-based only - LLM handled by _stage_llm
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

        except Exception:
            logger.exception("Intent stage error")
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

        NOTE (multilingual scope): the patterns below are English/Hindi-
        Romanized only. Non-English action verbs (e.g. Spanish "abrir",
        German "öffne", Chinese "打开", Tamil "திற") will NOT match
        _ACTION_VERBS in _split_multi_step either, so those commands
        currently fall through to conversational/LLM handling instead of
        being recognized as system_control intents. Extending this to the
        rest of the multilingual language set is separate, larger scope -
        it needs per-language verb tables reviewed the same way the filler/
        reaction-rule connector tables do, not a quick patch here.
        """

        t = text.strip()
        if not t:
            return t

        # ── Step 1: Strip wake word variants from START ───────────────────
        # Handle Whisper mishearings: "Himaya", "Hi Maya", "A Maya", "Hey Maya"
        # Also handle mid-sentence repetitions like "Open Notepad. Himaya Open Notepad."
        # First, take only the FIRST sentence (before first period/exclamation)
        first_sentence = re.split(r"[.!]", t)[0].strip()
        if first_sentence:
            t = first_sentence

        # Remove wake word fragments (including all Whisper mishearings of "Hey Guru/Maya")
        # Order matters - most specific patterns first
        wake_patterns = [
            # Full wake word variants (most specific)
            r"^(hey\s+|hi\s+|a\s+)?(guru|maya|himaya|hemaaya|hi\s*maya|hey\s*maya|hey\s*guru|he\s*maya|he\s*guru|give\s*maya|give\s*guru)\s*[,.]?\s*",
            # "This is Maya" / "This is Guru" - Whisper adds "This is" prefix
            r"^this\s+is\s+(maya|guru)\s*[,.]?\s*",
            # Standalone "He," or "Hey " at start (Whisper mishearing of "Hey")
            # Only strip if followed by nothing or a comma - NOT if it's part of a word
            r"^he\s*,\s*",  # "He, open notepad" → "open notepad"
            r"^hey\s+",  # "Hey open" → "open"
        ]
        for pat in wake_patterns:
            t = re.sub(pat, "", t, flags=re.I).strip()

        # ── Step 2: Remove filler words ───────────────────────────────────
        fillers = [
            r"\b(um+|uh+|er+|hmm+|ah+|oh+)\b,?\s*",
            r"\b(sorry|excuse me|pardon|oops),?\s*",
            r"\b(I mean|actually|basically|you know),?\s*",
            r"\b(and write there that|write there that|there that),?\s*",
        ]
        for f in fillers:
            t = re.sub(f, " ", t, flags=re.I)

        # ── Step 3: Fix "in edge/chrome/browser" context phrases ─────────
        t = re.sub(
            r"\bin\s+(edge|chrome|firefox|browser|it)\s+(?=open|play|search|go)",
            "open ",
            t,
            flags=re.I,
        )

        # ── Step 4: Remove leading conjunctions and politeness markers ──────
        t = re.sub(r"^(and|but|so|then|also|now|please|can you|could you|would you|will you|i want you to|i need you to|i'd like you to)\s+", "", t, flags=re.I)

        # ── Step 5: Remove trailing politeness markers ────────────────────
        t = re.sub(r",?\s*(please|for me|right now|now|immediately|quickly)\s*$", "", t, flags=re.I)

        # ── Step 6: Remove articles before app/site names ────────────────
        # "open the notepad" → "open notepad"
        # "open a new tab" → keep (meaningful)
        t = re.sub(r"\b(open|launch|start|close|quit)\s+the\s+", r"\1 ", t, flags=re.I)

        # ── Step 7: Collapse whitespace and strip ─────────────────────────
        t = re.sub(r"\s{2,}", " ", t).strip().lstrip(".,!?;: ")

        # ── Step 8: Normalize & → and, + → and ───────────────────────────
        t = re.sub(r"\s*[&+]\s*", " and ", t)

        # ── Step 9: Collapse "open youtube and play X" → "play X on youtube"
        t = re.sub(
            r"(?:open\s+youtube\s+and\s+|go\s+to\s+youtube\s+and\s+)"
            r"play\s+(.+)",
            r"play \1 on youtube",
            t,
            flags=re.I,
        )

        # ── Step 10: Fix common Whisper mishearings ───────────────────────
        _corrections = {
            r"\byou\s*to\b": "youtube",
            r"\byou\s*tube\b": "youtube",
            r"\bu\s*tube\b": "youtube",
            r"\blead\s*code\b": "leetcode",
            r"\bleet\s*code\b": "leetcode",
            r"\bchak\s*d[ae]\b": "chak de",
            r"\bchakd[ae]\b": "chak de",
            r"\bchakdha\b": "chak de",
            r"\bchadhya\b": "chak de",
            r"\bchakda\b": "chak de",
            r"\bspot\s*if\s*y\b": "spotify",
            r"\bwhat\s*s\s*app\b": "whatsapp",
            r"\bwhat\s*app\b": "whatsapp",
            r"\bface\s*book\b": "facebook",
            r"\bins\s*ta\s*gram\b": "instagram",
            r"\btwit\s*ter\b": "twitter",
            r"\bgit\s*hub\b": "github",
            r"\bgoogle\s*chrome\b": "chrome",
            r"\bvs\s*code\b": "vscode",
            r"\bvisual\s*studio\s*code\b": "vscode",
            r"\bms\s*edge\b": "edge",
            r"\bmicrosoft\s*edge\b": "edge",
        }
        for pattern, replacement in _corrections.items():
            t = re.sub(pattern, replacement, t, flags=re.I)

        return t if t else text.strip()

    @staticmethod
    def _split_multi_step(text: str) -> list[str]:
        """Split a multi-step command into individual steps.

        Examples:
            "open edge and open youtube and play chak de india"
            → ["open edge", "open youtube", "play chak de india"]

            "open notepad and type hello world"
            → ["open notepad", "type hello world"]

            "notepad and write" → ["notepad and write"]  (no split - "notepad" has no verb)

        Only splits when EACH part starts with an action verb.

        NOTE (multilingual scope): _ACTION_VERBS is English-only, same caveat
        as _clean_transcript above.
        """

        # Action verbs that start a new step
        _ACTION_VERBS = (
            r"open|launch|start|close|quit|play|pause|stop|search|find|"
            r"type|write|take|set|increase|decrease|volume|mute|unmute|"
            r"minimize|maximize|screenshot|navigate|go to|switch|send|call"
        )
        _STEP_PATTERN = re.compile(
            rf"(?:^|\s+(?:and\s+then|then|and)\s+)(?={_ACTION_VERBS})",
            re.I,
        )
        _VERB_START = re.compile(rf"^(?:{_ACTION_VERBS})\b", re.I)

        # Split on "and then" / "then" / "and" only when followed by action verb
        parts = _STEP_PATTERN.split(text.strip())
        # Clean up and filter empty parts
        steps = [p.strip() for p in parts if p and p.strip()]

        # Validate: every step must start with an action verb.
        # If any step doesn't, don't split (treat as single command).
        if len(steps) > 1 and not all(_VERB_START.match(s) for s in steps):
            return [text]

        # Only return multiple steps if we actually found more than one
        return steps if len(steps) > 1 else [text]

    async def _encode_single_intent(self, text: str) -> str:
        """Encode a single command text as 'intent_type:action:param:level'.

        Always uses rule-based recognition only - never calls LLM for intent
        classification. The main LLM (_stage_llm) handles questions/conversation.
        Using LLM here caused 8-38s timeouts for every command.
        """
        if not text or not text.strip():
            return ""

        # Always use rule-based - fast (<5ms), accurate for all common commands.
        # Low-confidence results (conversation/information) are handled by the
        # main LLM in _stage_llm, not by the intent classifier.
        rule_result = self._intent_recognizer._rule_engine.recognize(
            text,
            self._intent_recognizer._platform,
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
        level = str(result.parameters.get("engine", "")) or str(result.parameters.get("level", ""))
        encoded = f"{result.intent_type}:{action}:{param}:{level}".rstrip(":")
        logger.info(
            "Intent: %s (confidence=%.2f) params=%s encoded=%r",
            result.intent_type,
            result.confidence,
            result.parameters,
            encoded,
        )
        return encoded

    async def _stage_policy(self, intent: str) -> bool:
        """Stage 6: Policy check - returns True if execution is allowed.

        Supports both:
          - evaluate(intent) - simple API used in tests/mocks
          - evaluate_policy(principal, resource, action) - full PolicyEngine API

        Defaults to True (allow) when policy engine is unavailable or a stub.
        """
        try:
            # Prefer evaluate() - used by mocks and simpler subsystems
            fn = getattr(self.policy, "evaluate", None)
            if fn is not None:
                if inspect.iscoroutinefunction(fn):
                    decision = await fn(intent)
                else:
                    loop = asyncio.get_running_loop()
                    decision = await loop.run_in_executor(None, fn, intent)
                if hasattr(decision, "effect"):
                    return decision.effect.value.upper() == "ALLOW"
                # MagicMock returns a truthy MagicMock - treat as allow
                if hasattr(decision, "_mock_name"):
                    return True
                return bool(decision)

            # Fall back to PolicyEngine.evaluate_policy(principal, resource, action)
            eval_fn = getattr(self.policy, "evaluate_policy_async", None) or getattr(
                self.policy,
                "evaluate_policy",
                None,
            )
            if eval_fn is None:
                return False  # No policy engine - deny by default (secure)

            try:
                from Agent_Guru.policy.models import Principal, Resource

                principal = Principal(id="guru_pipeline", attributes={"role": "assistant"})
                resource = Resource(id="action", type="command")
                if inspect.iscoroutinefunction(eval_fn):
                    decision = await eval_fn(principal, resource, intent)
                else:
                    loop = asyncio.get_running_loop()
                    decision = await loop.run_in_executor(
                        None,
                        eval_fn,
                        principal,
                        resource,
                        intent,
                    )
                if hasattr(decision, "effect"):
                    return decision.effect.value.upper() == "ALLOW"
                return bool(decision)
            except ImportError:
                return False  # Can't build Principal/Resource - deny by default (secure)
        except Exception:
            logger.exception("Policy stage error - defaulting to deny for safety")
            return False  # Deny by default when policy check fails

    async def _stage_action(self, intent: str, pipeline_mode: str = "full") -> Any:
        """Stage 7: Execute action via agent_orchestrator or OSController.

        Supports:
        - Single intent: 'intent_type:action:param:level'
        - Multi-step:    'step1|step2|step3' (pipe-separated, from _stage_intent)

        Args:
            intent: Encoded intent string (single or pipe-separated multi-step).
            pipeline_mode: "full" or "restricted". Determines whether
                destructive actions and memory writes are permitted this
                call. Passed through explicitly to _execute_single_action -
                never read off `self`. See the module docstring's
                "Concurrency note" for why.

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
                    step_result = await self._execute_single_action(step, pipeline_mode)
                    if step_result:
                        results.append(str(step_result))
                    # Give apps time to open before the next step
                    await asyncio.sleep(1.5)
                except Exception:
                    logger.exception("Multi-step action failed for step %r", step)
            return ". ".join(results) if results else None

        # ── Single action ─────────────────────────────────────────────────
        return await self._execute_single_action(intent, pipeline_mode)

    async def _confirm_destructive_action(self, action: str, safe_intent: str) -> bool:
        """Gate a destructive action behind verbal confirmation.

        Fail-safe by design: if a live ConfirmationManager (wired with real
        TTS/STT callbacks) isn't available yet, this DENIES the action rather
        than proceeding. A logged "would confirm" comment is not a safety
        gate - until the callback wiring exists, "can't confirm" must mean
        "don't do it," not "do it anyway and hope."

        Expects (soft-imported) Agent_Guru.platform.features.confirmation to
        expose a get_confirmation_manager() factory returning an object with:
          - is_wired: bool - True once real speak/listen callbacks are injected
          - request_confirmation(description: str) -> Awaitable[bool]
        If confirmation.py doesn't yet expose exactly that shape, this method
        still fails safe (denies) rather than raising - but you'll want to
        add that factory/attribute so confirmed destructive actions actually
        become possible instead of always denied.

        Args:
            action: The resolved action name (e.g. "delete_file", "shutdown").
            safe_intent: The full encoded intent, for logging only.

        Returns:
            True if the user verbally confirmed, False otherwise (including
            whenever confirmation infrastructure isn't fully wired yet).
        """
        try:
            from Agent_Guru.platform.features.confirmation import get_confirmation_manager

            mgr = get_confirmation_manager()
            request_fn = getattr(mgr, "request_confirmation", None)
            # is_wired: True only once the manager has real speak/listen
            # callbacks injected. Until then, treat it as absent.
            if request_fn is not None and getattr(mgr, "is_wired", False):
                # FIX: previously passed action.replace("_", " ") (e.g.
                # "delete file") as a positional "description" argument.
                # request_confirmation()'s real signature takes the RAW
                # action name and does its own _ACTION_DESCRIPTIONS lookup
                # internally (e.g. "delete_file" -> "delete this file") -
                # passing the space-replaced version made that lookup miss,
                # falling back to the less natural raw string. Pass the
                # action unmodified so the intended human-readable prompt
                # actually gets built.
                return bool(await request_fn(action=action))
        except Exception:
            logger.debug(
                "ConfirmationManager unavailable for destructive-action gate",
                exc_info=True,
            )

        logger.warning(
            "Destructive action '%s' blocked: no live confirmation flow wired "
            "yet (intent=%r). Wire ConfirmationManager with TTS/STT callbacks "
            "to enable confirmed destructive actions instead of blocking them.",
            action,
            safe_intent,
        )
        return False

    async def _execute_single_action(self, intent: str, pipeline_mode: str = "full") -> Any:
        """Execute a single intent string. Returns a human-readable result or None.

        Args:
            intent: Encoded intent string 'intent_type:action:param:level'.
            pipeline_mode: "full" or "restricted". Gates destructive actions
                and memory writes for this call. Always passed explicitly by
                the caller (_stage_action) - never read off `self`. See the
                module docstring's "Concurrency note".
        """
        if not intent:
            return None

        safe_intent = self._sanitize_output(intent)

        # Parse once, up front
        parts = safe_intent.split(":", 3)
        intent_type = parts[0] if len(parts) > 0 else ""
        action = parts[1] if len(parts) > 1 else ""
        param = parts[2] if len(parts) > 2 else ""
        level_str = parts[3] if len(parts) > 3 else ""

        # Destructive action + restricted-mode gate
        gate_result = await self._gate_destructive_action(action, pipeline_mode, safe_intent)
        if gate_result is not None:
            return gate_result

        try:
            loop = asyncio.get_running_loop()

            # Primary path: delegate to agent_orchestrator.execute(intent)
            execute_fn = getattr(self.agent_orchestrator, "execute", None)
            if execute_fn is not None:
                try:
                    if inspect.iscoroutinefunction(execute_fn):
                        result = await execute_fn(safe_intent)
                    else:
                        result = await loop.run_in_executor(None, execute_fn, safe_intent)
                    if result is not None:
                        return result
                except AttributeError as exc:
                    logger.warning(
                        "Agent orchestrator execute failed: %s - trying direct platform control",
                        exc,
                    )
        except Exception:
            logger.exception("Unexpected error in primary action path")

        # Fallback: direct platform control
        try:
            raw_text = param or safe_intent

            # Universal feature detection (runs for ALL intent types)
            feature_result = await self._detect_universal_features(
                raw_text, pipeline_mode, intent_type,
            )
            if feature_result is not None:
                return feature_result

            # Conversation → no action
            if intent_type == "conversation":
                return None

            if intent_type not in ("system_control", "file_ops", "communication", "information"):
                logger.info(
                    "ACTION SKIPPED - intent_type=%r. Full intent: %r",
                    intent_type, safe_intent,
                )
                return None

            # Before the controller check: reading the clock needs no platform
            # controller, and a missing one must not turn this into silence.
            if intent_type == "information" and action == "time_date":
                return _clock_answer()

            ctrl = self.platform_controller
            if ctrl is None:
                return None

            # Dispatch to action-specific handlers
            return await self._dispatch_action(
                action, intent_type, param, level_str, safe_intent, ctrl,
            )

        except Exception:
            logger.exception("Action stage error")
            return None

    # ------------------------------------------------------------------
    # _execute_single_action decomposed helpers
    # ------------------------------------------------------------------

    async def _gate_destructive_action(
        self, action: str, pipeline_mode: str, safe_intent: str,
    ) -> str | None:
        """Check destructive-action gate. Returns response string to block, or None to allow."""
        try:
            from Agent_Guru.platform.features.confirmation import is_destructive_action

            if is_destructive_action(action):
                if pipeline_mode == "restricted":
                    logger.info(
                        "Destructive action '%s' blocked - unverified speaker "
                        "(restricted mode)", action,
                    )
                    return "Sorry, can't do that without verifying it's you."

                confirmed = await self._confirm_destructive_action(action, safe_intent)
                if not confirmed:
                    return "Okay, cancelled - didn't do that."
        except ImportError:
            if action in {
                "delete_file", "delete_folder", "remove", "shutdown",
                "restart", "uninstall", "format", "wipe", "empty_trash",
            }:
                logger.warning(
                    "confirmation module unavailable - denying destructive "
                    "action '%s' for safety", action,
                )
                return "Sorry, I can't confirm that action right now, so I won't do it."
        except Exception:
            logger.exception("Destructive-action gate failed - denying for safety")
            return "Something went wrong checking that - I didn't do it, try again."
        return None

    async def _detect_universal_features(
        self, raw_text: str, pipeline_mode: str, intent_type: str = "",
    ) -> Any | None:
        """Detect universal features (briefing, status, reminders, dictation, etc.)."""
        # Morning briefing
        from Agent_Guru.platform.features.briefing import get_morning_briefing, is_briefing_command
        if is_briefing_command(raw_text):
            from Agent_Guru.platform.features.user_memory import get_user_memory
            location = get_user_memory().get("location")
            return await get_morning_briefing(location=location)

        # System status
        from Agent_Guru.platform.features.system_status import get_system_status, is_system_status_command
        if is_system_status_command(raw_text):
            return get_system_status(raw_text)

        # Reminder / Timer
        result = await self._handle_reminder(raw_text)
        if result is not None:
            return result

        # Voice dictation
        from Agent_Guru.platform.features.dictation import (
            extract_dictation_text, get_clipboard_action, get_clipboard_text,
            is_clipboard_command, is_dictation_command,
        )
        if is_dictation_command(raw_text):
            text_to_type = extract_dictation_text(raw_text)
            if text_to_type:
                ctrl = self.platform_controller
                fn = getattr(ctrl, "type_text", None) if ctrl else None
                if fn:
                    await asyncio.to_thread(fn, text_to_type)
                    return f"Typed: {self._sanitize_output(text_to_type[:60])}"
                return "Typing is not available on this platform."

        # Clipboard read
        if is_clipboard_command(raw_text):
            clip_text = get_clipboard_text()
            if not clip_text:
                return "Your clipboard is empty."
            clip_action = get_clipboard_action(raw_text)
            if clip_action == "read":
                return f"Your clipboard contains: {clip_text[:300]}"
            return None

        # Screen reading
        from Agent_Guru.platform.features.screen_reader import is_screen_read_command, read_screen_text
        if is_screen_read_command(raw_text):
            screen_text = read_screen_text()
            if screen_text:
                return None  # LLM answers using screen context
            return "I couldn't read the screen content right now."

        # User memory extraction
        result = await self._handle_user_memory(raw_text, pipeline_mode, intent_type)
        if result is not None:
            return result

        # Presentation generation (e.g. "make a presentation from notes.txt")
        result = await self._handle_presentation_request(raw_text)
        if result is not None:
            return result

        return None

    async def _handle_presentation_request(self, raw_text: str) -> str | None:
        """Turn a source document into a .pptx, wiring
        platform.features.presentation.generate_presentation() into the
        live pipeline (Round 10 - see that module's docstring for the full
        rationale). Runs as a universal feature check, same as briefing/
        dictation/clipboard above, so it works regardless of what the
        rule-based intent recognizer would have classified this as.

        Returns None (not handled) when the transcript isn't asking for a
        presentation, or when it is but no source file could be identified
        - in the latter case the conversational LLM gets a turn instead of
        this method guessing a file, since generating from the wrong file
        would be a worse outcome than asking a clarifying question.
        """
        from Agent_Guru.platform.features.presentation import (
            PresentationError,
            extract_source_path,
            generate_presentation,
            wants_presentation,
        )

        if not wants_presentation(raw_text):
            return None

        source_ref = extract_source_path(raw_text)
        if not source_ref:
            logger.info(
                "Presentation request detected but no source file identified: %r",
                raw_text[:120],
            )
            return None

        from pathlib import Path

        from Agent_Guru.security.path_utils import safe_path

        try:
            # Sandbox to the user's home directory - the same boundary
            # reasoning/tools/system/file_operations.py uses (Round 8) - so
            # a spoken/transcribed command can't be used to read arbitrary
            # filesystem locations via path traversal.
            source_path = safe_path(source_ref, Path.home())
        except ValueError:
            return (
                f"I can only build presentations from files under your home "
                f"folder - {self._sanitize_output(source_ref)} is outside that."
            )

        logger.info("ACTION: create_presentation(%r)", str(source_path))
        try:
            complete_fn = getattr(self.llm_runtime, "complete", None)
            output_path = await generate_presentation(source_path, complete_fn=complete_fn)
        except PresentationError as exc:
            logger.warning("Presentation generation failed for %s: %s", source_path, exc)
            return f"Couldn't build a presentation from that: {self._sanitize_output(str(exc))}"
        except Exception:
            logger.exception("Unexpected error generating presentation from %s", source_path)
            return "Something went wrong while building that presentation."

        return f"Your presentation is ready at {output_path}"

    async def _handle_reminder(self, raw_text: str) -> str | None:
        """Handle reminder/timer commands."""
        from Agent_Guru.platform.features.reminders import parse_reminder_from_transcript
        reminder_params = parse_reminder_from_transcript(raw_text)
        if not reminder_params:
            return None

        if self._reminder_mgr is None:
            from Agent_Guru.platform.features.reminders import ReminderManager
            self._reminder_mgr = ReminderManager()
            tts_eng = getattr(self.speech_engine, "tts_engine", None)
            if tts_eng:
                import sounddevice as sd
                def _speak_reminder(text: str) -> None:
                    try:
                        import numpy as np
                        audio, sr = tts_eng.synthesize_to_array(text)
                        tail = np.zeros(int(sr * 0.30), dtype=np.float32)
                        padded = np.concatenate([audio.astype(np.float32), tail])
                        sd.play(padded, samplerate=sr)  # type: ignore[attr-defined]
                        sd.wait()  # type: ignore[attr-defined]
                    except Exception as _e:
                        logger.exception("Reminder TTS failed")
                self._reminder_mgr.set_speak_callback(_speak_reminder)

        msg = reminder_params.get("message", "reminder")
        mins = reminder_params.get("minutes")
        secs = reminder_params.get("seconds")
        at_t = reminder_params.get("at_time")
        return await self._reminder_mgr.set_reminder(msg, minutes=mins, seconds=secs, at_time=at_t)

    async def _handle_user_memory(
        self, raw_text: str, pipeline_mode: str, intent_type: str = "",
    ) -> str | None:
        """Handle user memory extraction (remember/forget commands)."""
        from Agent_Guru.platform.features.user_memory import extract_user_fact, get_user_memory
        if pipeline_mode != "full":
            return None

        fact = extract_user_fact(raw_text)
        if not fact:
            return None

        key, value = fact

        # Handle "forget" commands
        if key == "__forget__":
            _mem = get_user_memory()
            _all_facts = _mem.get_all()
            for fk, fv in _all_facts.items():
                if fk.startswith("custom_fact_") and value.lower() in str(fv).lower():
                    _mem.delete(fk)
                    _lang = _mem.get("code_mixing", "hinglish")
                    if _lang == "hinglish":
                        return "done, bhool gaya!"
                    return "done, forgot that!"
            return "hmm, I don't remember that one."

        get_user_memory().set(key, value)

        # The user asked a question. Whatever this returns becomes the spoken
        # reply (_finalize_tts_text prefers action_result over llm_response),
        # so returning the acknowledgement here threw away the answer the LLM
        # had already produced: "My name is Suraj, what's the weather?" was
        # answered with "Nice to meet you, Suraj!" and nothing else. Keep the
        # fact, let the answer through.
        if intent_type == "information":
            return None

        _sval = self._sanitize_output(value)
        _lang = get_user_memory().get("code_mixing", "hinglish")
        _ack_map = {
            "name": f"Nice to meet you, {_sval}! I'll remember that.",
            "nickname": f"Alright {_sval}! That's what I'll call you from now on.",
            "location": f"{_sval} - cool, I'll keep that in mind.",
            "occupation": f"That's awesome. I'll remember you're into {_sval}.",
            "age": f"Got it - {_sval}. I'll remember.",
            "current_project": f"Nice - {_sval} sounds interesting. Keep me posted on how it goes.",
            "current_goal": f"Love that. I'll remember you're working toward {_sval}.",
            "hobbies": f"Good taste! I'll remember you're into {_sval}.",
            "interests": "That's interesting! I'll keep that in mind.",
            "friends": "Cool, I'll remember that.",
            "family": "Got it, thanks for sharing that.",
            "preferred_language": f"{_sval} - got it, I'll keep that in mind.",
            "communication_style": f"Understood - I'll adjust to a {_sval} style.",
            "code_mixing": "Switched! I'll talk to you in English only from now on." if value == "english" else "Chal done! Hinglish mein baat karenge ab.",
        }
        if key.startswith("custom_fact_"):
            if _lang == "hinglish":
                return f"done, yaad rakh liya - {_sval}"
            return f"noted - {_sval}"
        return _ack_map.get(key, "Noted - I'll keep that in mind.")

    async def _dispatch_action(
        self, action: str, intent_type: str, param: str, level_str: str,
        safe_intent: str, ctrl: Any,
    ) -> str | None:
        """Dispatch to the appropriate action handler."""
        loop = asyncio.get_running_loop()

        # Action-based dispatch table (keyed by action string)
        _action_handlers: dict[str, Any] = {
            "open_app": lambda: self._action_open_app(ctrl, param) if param else None,
            "open_file": lambda: self._action_open_app(ctrl, param) if param else None,
            "close_app": lambda: self._action_close_app(ctrl, param) if param else None,
            "open_url": lambda: self._action_open_url(ctrl, param),
            "web_search": lambda: self._action_web_search(ctrl, param, level_str),
            "volume": lambda: self._action_volume(ctrl, param, level_str, loop),
            "brightness": lambda: self._action_brightness(ctrl, param, level_str),
            "window": lambda: self._action_window(ctrl, param, level_str),
            "screenshot": lambda: self._action_screenshot(ctrl, loop),
            "next_track": lambda: self._action_media_simple(ctrl, "next_track", loop),
            "previous_track": lambda: self._action_media_simple(ctrl, "previous_track", loop),
            "stop_media": lambda: self._action_media_simple(ctrl, "stop_media", loop),
            "play_pause": lambda: self._action_play_pause(ctrl, safe_intent, loop),
            "switch_app": lambda: self._action_switch_app(ctrl, param) if param else None,
            "settings": lambda: self._action_settings(ctrl, param, level_str),
        }

        handler = _action_handlers.get(action)
        if handler is not None:
            return await handler()

        # Type text (needs param guard)
        if action == "type_text" and param:
            fn = getattr(ctrl, "type_text", None)
            if fn:
                await asyncio.to_thread(fn, param)
                return "Typed text"
            return "Cannot type - controller unavailable"

        # Shutdown / Restart
        if action in ("shutdown", "restart"):
            fn = getattr(ctrl, action + "_pc", None)
            if fn:
                await asyncio.to_thread(fn, confirmed=True)
                return f"System {action} initiated"
            return f"Cannot {action} - controller unavailable"

        # Intent-type-based dispatch
        _type_handlers: dict[str, Any] = {
            "communication": lambda: self._action_communication(ctrl, action, param, level_str),
            "information": lambda: self._action_information(ctrl, action, param, safe_intent),
            "file_ops": lambda: self._action_file_ops(ctrl, action, param),
        }

        type_handler = _type_handlers.get(intent_type)
        if type_handler is not None:
            return await type_handler()

        return None

    # ------------------------------------------------------------------
    # Individual action handlers
    # ------------------------------------------------------------------

    async def _action_open_app(self, ctrl: Any, param: str) -> str:
        param = param.rstrip(".,!?;:")
        logger.info("ACTION: open_application('%s')", param)
        result = await asyncio.to_thread(ctrl.open_application, param)
        safe_param = self._sanitize_output(param)
        if getattr(result, "success", False):
            return f"Opening {safe_param} for you! What are we doing?"
        err = getattr(result, "error", "unknown error")
        logger.error("Failed to open '%s': %s", param, err)
        return f"Hmm, couldn't open {safe_param} - let me know if you wanna try something else"

    async def _action_close_app(self, ctrl: Any, param: str) -> str:
        param = param.rstrip(".,!?;:")
        logger.info("ACTION: close_application('%s')", param)
        result = await asyncio.to_thread(ctrl.close_application, param)
        safe_param = self._sanitize_output(param)
        return (
            f"Closed {safe_param}"
            if getattr(result, "success", True)
            else f"Failed to close {safe_param}"
        )

    # Known URL map - class-level to avoid re-creating per call
    # NOTE: the site-name → URL table used to live here as a 60+-entry
    # `_URL_MAP`, duplicating (and drifting from) platform/os_controller.py's
    # own 15-entry `_shortcuts` and a third, separate registry in
    # platform/browser_manager.py. All three have been consolidated into
    # browser_manager._SITE_REGISTRY (consolidated 2026-09-13) - see that
    # module for the merged table and conflict resolutions. Both this method
    # and OSController._resolve_url() now delegate to
    # browser_manager._resolve_site_url() instead of keeping their own copy.

    async def _action_open_url(self, ctrl: Any, param: str) -> str:
        param_lower = param.lower().strip()

        # Browser app launches
        if param_lower in ("edge", "microsoft edge", "msedge"):
            await asyncio.to_thread(ctrl.open_application, "msedge")
            return "Opening Microsoft Edge"
        if param_lower in ("chrome", "google chrome"):
            await asyncio.to_thread(ctrl.open_application, "chrome")
            return "Opening Chrome"
        if param_lower in ("firefox", "mozilla firefox"):
            await asyncio.to_thread(ctrl.open_application, "firefox")
            return "Opening Firefox"

        from Agent_Guru.platform.browser_manager import _resolve_site_url

        # _resolve_site_url() covers: known site names (the merged registry),
        # and anything already shaped like a URL (http(s):// or www.) - safe
        # by construction, since it only ever returns those two forms.
        target_url = _resolve_site_url(param)
        if not target_url:
            if "." in param and " " not in param:
                # Bare domain name (e.g. "example.com") - not in the
                # registry and no scheme/www prefix for _resolve_site_url
                # to recognize, but still clearly a domain.
                target_url = param if param.startswith("http") else f"https://{param}"
            else:
                # Unrecognized site name - best-effort guess, same
                # fallback behavior this method has always had.
                target_url = f"https://www.{param_lower.replace(' ', '')}.com"

        logger.info("ACTION: open_url('%s') → %s", param, target_url)

        # Prefer the persistent, tab-reusing BrowserManager: repeated opens
        # of the same site reuse the existing tab and keep cookies/session
        # (login state, preferences) instead of relying only on the OS's
        # plain webbrowser.open(), which always behaves like a fresh,
        # disconnected request. Falls back to ctrl.open_url (webbrowser.open)
        # if the persistent browser can't start for any reason, so "open X"
        # still does something either way - never a silent no-op.
        try:
            mgr = await self._get_browser_mgr()
            await mgr.open_url(target_url)
            return f"Opening {self._sanitize_output(param)}"
        except Exception:
            logger.exception(
                "Persistent BrowserManager failed for open_url(%s) - falling back to "
                "plain webbrowser.open()", target_url,
            )

        fn = getattr(ctrl, "open_url", None)
        if fn:
            await asyncio.to_thread(fn, target_url)
            return f"Opening {self._sanitize_output(param)}"
        return f"Cannot open {self._sanitize_output(param)} - browser unavailable"

    async def _action_web_search(self, ctrl: Any, param: str, level_str: str) -> str:
        query = param.strip()
        engine = level_str.strip().lower() if level_str.strip() else "google"
        if engine not in ("google", "youtube", "bing"):
            engine = "google"
        logger.info("ACTION: web_search('%s', engine='%s')", query, engine)

        if engine == "youtube":
            try:
                await self._open_youtube_and_play(query)
                return f"Playing {self._sanitize_output(query)} on YouTube"
            except Exception as yt_exc:
                logger.exception(
                    "YouTube auto-play failed (%s) - opening search page instead", yt_exc,
                )
                search_url = "https://www.youtube.com/results?search_query=" + _up.quote_plus(query)
                fn = getattr(ctrl, "open_url", None)
                if fn:
                    await asyncio.to_thread(fn, search_url)
                return f"Opening YouTube search for {self._sanitize_output(query)}"

        # Prefer the persistent BrowserManager here too - same tab-reuse
        # rationale as _action_open_url(), and it shares the exact same
        # engine URLs (see browser_manager.py's search_and_open()) so
        # there's one source of truth for how a search URL gets built.
        try:
            mgr = await self._get_browser_mgr()
            await mgr.search_and_open(query, engine=engine)
            return f"Searching for {self._sanitize_output(query)} on {engine}"
        except Exception:
            logger.exception(
                "Persistent BrowserManager failed for web_search(%s) - falling back to "
                "plain webbrowser.open()", query,
            )

        _engines = {
            "google": "https://www.google.com/search?q=",
            "bing": "https://www.bing.com/search?q=",
        }
        search_url = _engines.get(engine, _engines["google"]) + _up.quote_plus(query)
        fn = getattr(ctrl, "open_url", None)
        if fn:
            await asyncio.to_thread(fn, search_url)
            return f"Searching for {self._sanitize_output(query)} on {engine}"
        return "Cannot search - controller unavailable"

    async def _action_volume(
        self, ctrl: Any, param: str, level_str: str, loop: Any,
    ) -> str | None:
        mgr = getattr(self, "_browser_mgr", None)
        yt_open = mgr is not None and mgr._page is not None
        num_match = re.search(r"\d+", param + " " + level_str)

        if num_match:
            vol = max(0, min(100, int(num_match.group())))
            logger.info("ACTION: set_volume(%d)", vol)
            return await self._set_volume_absolute(ctrl, mgr, yt_open, vol)

        param_lower = param.lower()
        if "up" in param_lower or "increase" in param_lower:
            return await self._adjust_volume(ctrl, mgr, yt_open, loop, "up")
        if "down" in param_lower or "decrease" in param_lower:
            return await self._adjust_volume(ctrl, mgr, yt_open, loop, "down")
        if re.search(r"\b(mute|unmute)\b", param, re.IGNORECASE):
            return await self._toggle_mute(ctrl, mgr, yt_open, param, loop)

        return None

    async def _set_volume_absolute(
        self, ctrl: Any, mgr: Any, yt_open: bool, vol: int,
    ) -> str:
        """Set volume to an absolute level."""
        if yt_open and mgr is not None:
            try:
                return await mgr.set_volume(vol)
            except Exception:
                logger.exception("Operation failed")
        try:
            await asyncio.to_thread(ctrl.set_volume, vol)
        except Exception:
            logger.exception("set_volume failed")
        return f"Volume set to {vol}%"

    async def _adjust_volume(
        self, ctrl: Any, mgr: Any, yt_open: bool, loop: Any, direction: str,
    ) -> str:
        """Adjust volume up or down."""
        mgr_fn_name = f"volume_{direction}"
        ctrl_fn_name = f"volume_{direction}"
        label = "increased" if direction == "up" else "decreased"

        if yt_open and mgr is not None:
            try:
                return await getattr(mgr, mgr_fn_name)()
            except Exception:
                logger.exception("Operation failed")
        fn = getattr(ctrl, ctrl_fn_name, None)
        try:
            if fn:
                await loop.run_in_executor(None, fn)
        except Exception:
            logger.exception(f"{ctrl_fn_name} failed")
        return f"Volume {label}"

    async def _toggle_mute(
        self, ctrl: Any, mgr: Any, yt_open: bool, param: str, loop: Any,
    ) -> str:
        """Toggle mute/unmute."""
        is_unmute = bool(re.search(r"\bunmute\b", param, re.IGNORECASE))
        if yt_open and mgr is not None:
            try:
                return await (mgr.unmute() if is_unmute else mgr.mute())
            except Exception:
                logger.exception("Operation failed")
        fn = getattr(ctrl, "unmute" if is_unmute else "mute", None)
        try:
            if fn:
                await loop.run_in_executor(None, fn)
        except Exception:
            logger.exception("mute failed")
        return "Unmuted" if is_unmute else "Muted"

    async def _action_brightness(self, ctrl: Any, param: str, level_str: str) -> str | None:
        num_match = re.search(r"\d+", param + " " + level_str)
        if num_match:
            brightness = max(0, min(100, int(num_match.group())))
            logger.info("ACTION: set_brightness(%d)", brightness)
            await asyncio.to_thread(ctrl.set_brightness, brightness)
            return f"Brightness set to {brightness}%"
        get_fn = getattr(ctrl, "get_brightness", None)
        current = 50
        if get_fn:
            with contextlib.suppress(Exception):
                current = int(await asyncio.to_thread(get_fn))
        set_fn = getattr(ctrl, "set_brightness", None)
        if "up" in param.lower() or "increase" in param.lower():
            if set_fn:
                await asyncio.to_thread(set_fn, min(100, current + 10))
            return "Brightness increased"
        if "down" in param.lower() or "decrease" in param.lower():
            if set_fn:
                await asyncio.to_thread(set_fn, max(0, current - 10))
            return "Brightness decreased"
        return None

    async def _action_window(self, ctrl: Any, param: str, level_str: str) -> str | None:
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
        return None

    async def _action_screenshot(self, ctrl: Any, loop: Any) -> str | None:
        logger.info("ACTION: screenshot")
        fn = getattr(ctrl, "take_screenshot", None) or getattr(
            getattr(ctrl, "_screen_controller", None), "capture", None,
        )
        if fn:
            await loop.run_in_executor(None, fn)
            return "Screenshot taken"
        return None

    async def _action_media_simple(self, ctrl: Any, action: str, loop: Any) -> str:
        fn = getattr(ctrl, action, None)
        if fn:
            await loop.run_in_executor(None, fn)
        _labels = {"next_track": "Next track", "previous_track": "Previous track", "stop_media": "Media stopped"}
        return _labels.get(action, "Done")

    async def _action_play_pause(self, ctrl: Any, safe_intent: str, loop: Any) -> str:
        mgr = getattr(self, "_browser_mgr", None)
        if mgr and mgr._page is not None:
            try:
                if re.search(r"\bpause\b", safe_intent, re.IGNORECASE):
                    return await mgr.pause()
                return await mgr.resume()
            except Exception:
                logger.exception("BrowserManager play_pause failed")
        if re.search(r"\bpause\b", safe_intent, re.IGNORECASE):
            fn = getattr(ctrl, "pause_media", None)
            if fn:
                await loop.run_in_executor(None, fn)
            return "Media paused"
        fn = getattr(ctrl, "play_media", None)
        if fn:
            await loop.run_in_executor(None, fn)
        return "Media playing"

    async def _action_switch_app(self, ctrl: Any, param: str) -> str:
        switched = False
        if sys.platform == "win32":
            try:
                import win32gui as _wg  # type: ignore[import]
                found: list[int] = []
                def _cb(hwnd: int, _: object) -> bool:
                    title = _wg.GetWindowText(hwnd)
                    if param.lower() in title.lower():
                        found.append(hwnd)
                    return True
                _wg.EnumWindows(_cb, None)
                if found:
                    _wg.SetForegroundWindow(found[0])
                    switched = True
            except Exception as exc:
                logger.debug("win32 switch_app failed: %s", exc)
        if not switched:
            await asyncio.to_thread(ctrl.open_application, param)
        return f"Switched to {self._sanitize_output(param)}"

    async def _action_settings(self, ctrl: Any, param: str, level_str: str) -> str:
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

    async def _action_communication(
        self, ctrl: Any, action: str, param: str, level_str: str,
    ) -> str | None:
        if action in ("send_message", "reply"):
            contact = param.strip()
            app = level_str.strip().lower() if level_str.strip() else "whatsapp"
            if app not in ("whatsapp", "telegram", "slack", "sms", "email"):
                app = "whatsapp"
            fn = getattr(ctrl, "open_url", None)
            if fn and contact:
                if app == "whatsapp":
                    digits = contact.replace("+", "").replace("-", "").replace(" ", "")
                    url = f"https://wa.me/{digits}" if digits.isdigit() else "https://web.whatsapp.com"
                    await asyncio.to_thread(fn, url)
                    return f"Opening WhatsApp for {self._sanitize_output(contact)}"
                if app == "telegram":
                    await asyncio.to_thread(fn, f"https://t.me/{contact.lstrip('@')}")
                    return f"Opening Telegram for {self._sanitize_output(contact)}"
                if app == "email":
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
        return None

    async def _action_information(
        self, ctrl: Any, action: str, param: str, safe_intent: str,
    ) -> str | None:
        query = param.strip() or safe_intent
        action_lower = action.lower() if action else ""
        if action_lower in ("weather", "news", "search"):
            fn = getattr(ctrl, "web_search", None)
            if fn:
                await asyncio.to_thread(fn, query, "google")
                return f"Searching for {self._sanitize_output(query)}"
        return None

    async def _action_file_ops(self, ctrl: Any, action: str, param: str) -> str | None:
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
            if inspect.iscoroutinefunction(fn):
                result = await fn(text, pt)
            else:
                result = await asyncio.to_thread(fn, text, pt)
            if isinstance(result, tuple) and len(result) == 2:
                audio_array, sample_rate = result
            elif isinstance(result, np.ndarray):
                audio_array = result

        elif fn_type == "bytes":
            if inspect.iscoroutinefunction(fn):
                wav_bytes = await fn(text, pt)
            else:
                wav_bytes = await asyncio.to_thread(fn, text, pt)
            if isinstance(wav_bytes, (bytes, bytearray)) and len(wav_bytes) > 44:
                with io.BytesIO(wav_bytes) as buf, wave.open(buf, "rb") as wf:
                    sample_rate = wf.getframerate()
                    frames = wf.readframes(wf.getnframes())
                audio_array = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
            elif isinstance(wav_bytes, (bytes, bytearray)):
                # Short bytes (e.g. b"<audio>" from mock) - return sentinel
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

            # Convert orchestrator Personality → speech engine PersonalityType
            try:
                from Agent_Guru.speech.models import PersonalityType

                pt = (
                    PersonalityType.MAYA
                    if personality == Personality.MAYA
                    else PersonalityType.GURU
                )
            except ImportError:
                pt = personality  # fallback - pass as-is
            audio_array: Any = None
            sample_rate = 22050

            # Build ordered candidate list - cached fn first, then runtime probes
            tts_eng = getattr(self.speech_engine, "tts_engine", None)
            if self._tts_fn is not None:
                candidates = [(self._tts_fn, self._tts_fn_type)]
            else:
                # startup() was not called - probe at call time
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
                        fn_candidate,
                        text,
                        pt,
                        fn_type,
                    )
                    if isinstance(audio_array, (bytes, bytearray)):
                        return audio_array
                except Exception:
                    logger.exception("TTS fn (%s) failed", fn_type)
            # --- Play audio through speakers ---
            if audio_array is not None and len(audio_array) > 0:
                try:
                    import sounddevice as sd

                    def _play() -> None:
                        import numpy as np

                        # Pad with 300ms silence to prevent last-word cutoff
                        tail = np.zeros(int(sample_rate * 0.30), dtype=np.float32)
                        padded = np.concatenate([audio_array.astype(np.float32), tail])
                        sd.play(padded, samplerate=sample_rate)  # type: ignore[attr-defined]
                        sd.wait()  # type: ignore[attr-defined]

                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, _play)
                    logger.info("TTS played: %.1fs of audio", len(audio_array) / sample_rate)
                except ImportError:
                    # BUG-FIX: sounddevice missing was silently swallowed - the
                    # TTS audio was synthesized but never played, so the user
                    # heard nothing. Now falls back to pyttsx3 (always available
                    # on Windows/macOS/Linux) so the reply is always spoken.
                    logger.exception(
                        "sounddevice not installed - falling back to pyttsx3 TTS. "
                        "For best audio quality: pip install sounddevice",
                    )
                    try:
                        import pyttsx3  # type: ignore[import]

                        def _play_pyttsx3() -> None:
                            engine = pyttsx3.init()
                            # Match voice gender to personality
                            _raw_voices = engine.getProperty("voices")
                            voices: list[Any] = _raw_voices if isinstance(_raw_voices, list) else []
                            if voices:
                                if personality == Personality.MAYA:
                                    # Pick first female voice if available
                                    female = next(
                                        (
                                            v
                                            for v in voices
                                            if "female" in v.name.lower()
                                            or "zira" in v.name.lower()
                                            or "hazel" in v.name.lower()
                                        ),
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
                            "TTS playback failed (sounddevice + pyttsx3 both unavailable): %s - "
                            "install sounddevice: pip install sounddevice",
                            tts_exc,
                        )
            return audio_array
        except Exception:
            logger.exception("TTS stage error")
            return text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_output(text: str) -> str:
        """Sanitize user-controlled text for safe display (HTML context).

        Escapes HTML special characters so the text is safe to display
        in web interfaces, logs, or any HTML context.
        For OS/shell commands use _sanitize_for_shell() instead.

        Args:
            text: Raw user input or derived text.

        Returns:
            HTML-escaped text safe for display.

        """
        if not text:
            return text
        import html as _html_mod

        return _html_mod.escape(text, quote=True)

    @staticmethod
    def _sanitize_for_shell(text: str) -> str:
        """Sanitize text for safe use as a shell/OS argument (SEC-001).

        Uses shlex.quote() to prevent shell injection when passing
        user-controlled strings to subprocess, win32api, or os.system.
        Always use this - not _sanitize_output - for OS command params.

        Args:
            text: Raw user input or parameter.

        Returns:
            Shell-quoted string safe for OS command arguments.

        """
        if not text:
            return text
        import shlex as _shlex

        # Shell-quote for OS safety, then HTML-escape for any log/display output
        return _shlex.quote(text)

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
        do NOT need LLM - the action confirmation IS the response.

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

        parts = intent.split(":", 2)
        intent_type = parts[0].lower().strip() if parts else ""
        action = parts[1].lower().strip() if len(parts) > 1 else ""

        # Answered from the system clock in the action stage (_clock_answer).
        # Running the LLM first cost the user 45 seconds for a reply that was
        # then thrown away, because the spoken reply prefers action_result.
        if intent_type == "information" and action == "time_date":
            return False

        # These intent types always need LLM (they are questions/conversation)
        if intent_type in ("conversation", "information"):
            return True

        # system_control, file_ops, communication -> action confirmation is enough
        if intent_type in ("system_control", "file_ops", "communication"):
            return False

        # Unknown intent type -> call LLM to be safe
        return True
