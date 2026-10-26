"""Agent_Guru/integration/orchestrator.py.

IntegrationOrchestrator - wires all Agent Guru subsystems into a single unified
pipeline and manages concurrent async startup.

End-to-end pipeline (stages numbered as in PipelineResult.stages_completed):
  1. STT          - speech_engine.transcribe(audio)
  2. Memory       - memory.retrieve(transcript)
  3. (removed)    - the ReasoningEngine used to run here; see run_pipeline()
  4. LLM          - llm_runtime.infer(transcript, memory_context)
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
import contextvars
import dataclasses
import datetime as _dt
import inspect
import logging
import os
import re
import sys
import time
import urllib.parse as _up
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC
from enum import Enum, StrEnum
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple

from Agent_Guru.reasoning.llm.generation import ollama_model as _configured_ollama_model
from Agent_Guru.integration.turn_trace import StageTiming, TurnRecord, TurnTraceStore
from Agent_Guru.security.audit.logger import AuditLogger, EventType

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    from Agent_Guru.integration.gpu_pool import GPUResourcePool
    from Agent_Guru.integration.mcp_tools import MCPToolbox, ServerConfig
    from Agent_Guru.integration.tool_loop import ToolLoop
    from Agent_Guru.platform.features.documents import DocumentStore

logger = logging.getLogger(__name__)


def _accepts_device_cfg(init: Callable[..., Any]) -> bool:
    """True if initialize() takes a device_cfg keyword, read from its signature."""
    try:
        params = inspect.signature(init).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        p.name == "device_cfg" or p.kind is inspect.Parameter.VAR_KEYWORD for p in params
    )


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
    #: A typed turn: the text stands in for the transcript, and nothing is
    #: spoken. See IntegrationOrchestrator.run_text_turn().
    text: str | None = None


#: True while a typed turn runs. Set per task, so a voice turn running at the
#: same time is not silenced by it.
_TEXT_TURN: contextvars.ContextVar[bool] = contextvars.ContextVar("agent_guru_text_turn", default=False)
#: The model that wrote this turn's answer when routing chose another than
#: OLLAMA_MODEL; reset at the start of each turn, read by the turn record.
_ROUTED_MODEL: contextvars.ContextVar[str] = contextvars.ContextVar("agent_guru_routed_model", default="")


@dataclass
class VisionEvent:
    """Event emitted when a video frame is available for processing."""

    frame: Any  # numpy.ndarray in production


class ActionStatus(StrEnum):
    """What an action actually did, as far as the assistant could tell."""

    SUCCESS = "success"          # done, and what the controller returned says so
    FAILED = "failed"            # tried, and it did not work (or raised)
    DENIED = "denied"            # not attempted: the policy or the speaker check refused it
    CANCELLED = "cancelled"      # not done: the user said no
    UNVERIFIED = "unverified"    # tried, but nothing returned says whether it worked


class ActionOutcome(NamedTuple):
    """An action's spoken reply and its status.

    The action stage used to return only the reply, so a refusal, a failure
    or an exception reached the reply as nothing, which was spoken "Done.".
    """

    text: str | None
    status: ActionStatus | None


#: Spoken when an action produced no reply of its own. Before, every such
#: turn was answered "Done.", including actions the policy refused, actions
#: that raised, and commands nothing handled.
_STATUS_REPLIES: dict[ActionStatus | None, str] = {
    ActionStatus.SUCCESS: "Done.",
    ActionStatus.FAILED: "Sorry, that didn't work.",
    ActionStatus.DENIED: "I can't do that - it isn't allowed in my current settings.",
    ActionStatus.CANCELLED: "Okay, I cancelled that.",
    ActionStatus.UNVERIFIED: "I tried, but I couldn't confirm that it worked.",
    None: "Sorry, I couldn't do that.",
}


def _call_status(value: Any) -> ActionStatus:
    """What one controller call's return value says about whether it worked.

    OSController returns OperationResult, whose success is the answer; a
    plain bool is read the same way. None says nothing, so the call is
    unverified, and so is a success given as words ("yes", "done"), which
    is not read as a claim. Anything else the call returned (a screenshot's
    data) is taken as done. Results that need reading, such as messaging's
    outcome strings, are read by their handler, which returns an
    ActionOutcome of its own.
    """
    success = getattr(value, "success", None)
    if isinstance(success, bool):
        return ActionStatus.SUCCESS if success else ActionStatus.FAILED
    if isinstance(success, str):
        return ActionStatus.UNVERIFIED
    if isinstance(value, bool):
        return ActionStatus.SUCCESS if value else ActionStatus.FAILED
    if value is None:
        return ActionStatus.UNVERIFIED
    return ActionStatus.SUCCESS


class _ControllerCalls:
    """The platform controller as an action handler sees it, noting what each call returned.

    Most handlers call the controller and then return a fixed reply: "Window
    minimized" whether minimize_window succeeded or not, "Done" for media
    keys, "Screenshot taken". The controller's OperationResult was dropped
    on the floor. Every call made through this wrapper records its status,
    so the action stage knows what happened without each handler having to.
    Sub-controllers reached through it (ctrl._screen_controller) are wrapped
    too. Calls that raise are recorded as failed and still raise.
    """

    __slots__ = ("_record", "_target")

    def __init__(self, target: Any, record: list[ActionStatus] | None = None) -> None:
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_record", record if record is not None else [])

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._target, name)
        record = self._record
        if inspect.iscoroutinefunction(value):
            async def acall(*args: Any, **kwargs: Any) -> Any:
                try:
                    out = await value(*args, **kwargs)
                except Exception:
                    record.append(ActionStatus.FAILED)
                    raise
                record.append(_call_status(out))
                return out
            return acall
        if callable(value) and not isinstance(value, type):
            def call(*args: Any, **kwargs: Any) -> Any:
                try:
                    out = value(*args, **kwargs)
                except Exception:
                    record.append(ActionStatus.FAILED)
                    raise
                record.append(_call_status(out))
                return out
            return call
        if type(value).__module__.startswith("Agent_Guru."):
            return _ControllerCalls(value, record)
        return value

    def __bool__(self) -> bool:
        return self._target is not None


def _outcome(reply: Any, calls: list[ActionStatus]) -> ActionOutcome:
    """The outcome of a handler that returned a plain reply, from its controller calls.

    A handler's own reply is kept when nothing contradicts it. If a call
    failed, or none of its calls said whether it worked, the reply cannot be
    trusted as a claim of success and is replaced; a handler that checks its
    results returns an ActionOutcome instead and is taken at its word.
    """
    if isinstance(reply, ActionOutcome):
        return reply
    if ActionStatus.FAILED in calls:
        status: ActionStatus | None = ActionStatus.FAILED
    elif ActionStatus.UNVERIFIED in calls:
        status = ActionStatus.UNVERIFIED
    elif calls or reply:
        status = ActionStatus.SUCCESS
    else:
        status = None
    if status in (ActionStatus.FAILED, ActionStatus.UNVERIFIED):
        if reply:
            logger.info("Action reply %r replaced: its controller calls were %s", reply, status.value)
        return ActionOutcome(_STATUS_REPLIES[status], status)
    return ActionOutcome(reply if isinstance(reply, str) else (str(reply) if reply else None), status)


def _intent_steps(intent: str) -> list[str]:
    """The steps the action stage runs for *intent*, and so the steps the policy must allow.

    Steps are joined with "|", but a message's text is the owner's own words
    in the last field. The policy used to read the whole string and the action
    stage to split it, so "send a message to John saying hi|system_control:
    type_text:pwned" was allowed as a message, sent "hi", then typed "pwned"
    into whatever window was in front. A message is one step, its text whole;
    anything else is split, and each part is checked and run on its own.
    """
    if intent.startswith(("communication:send_message:", "communication:reply:")):
        return [intent]
    return [s.strip() for s in intent.split("|") if s.strip()]


_STATUS_SEVERITY = [ActionStatus.FAILED, ActionStatus.UNVERIFIED, ActionStatus.DENIED,
                    ActionStatus.CANCELLED, ActionStatus.SUCCESS]


@dataclass
class PipelineResult:
    """Result of a complete end-to-end pipeline run.

    Attributes:
        stages_completed: Number of pipeline stages that completed (max 8).
        transcript: STT output from stage 1.
        memory_context: Retrieved memory context from stage 2.
        llm_response: LLM response text from stage 4.
        intent: Recognised intent string from stage 5.
        policy_allowed: Whether the policy check (stage 6) allowed execution.
        action_result: Result of action execution from stage 7.
        tts_response: TTS audio/text from stage 8.
        personality: Personality used for this interaction.
        action_status: What the action did (ActionStatus), or None if no
            action was attempted. The reply is chosen from it when the
            action gave none of its own.
        awaiting_reply: True when the reply asked the user something this
            turn's action is waiting on (a message draft); the caller can
            listen for the answer without a wake word.
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
    llm_response: str | None = None
    intent: str | None = None
    policy_allowed: bool = False
    action_result: Any | None = None
    tts_response: Any | None = None
    personality: Personality = Personality.GURU
    pipeline_mode: str = "full"
    error: str | None = None
    awaiting_reply: bool = False
    action_status: ActionStatus | None = None
    # (stage name, wall-clock start, seconds) in the order the stages ran.
    # Sources the turn's research tools returned, as cited in the answer:
    # id, kind, title, url and how much of each was read.
    sources: list[dict[str, Any]] = field(default_factory=list)
    # Nothing measured a stage before: only wake-to-first-speech, and only
    # on two shortcut paths, so "which stage was slow" had no answer.
    stage_timings: list[tuple[str, float, float]] = field(default_factory=list)
    # Each tool loop step and tool call, with what it did; the turn record
    # keeps them among the stages, in time order.
    tool_stages: list[StageTiming] = field(default_factory=list)
    # What the model reported about a streamed answer: prompt tokens it
    # processed, tokens it wrote, its timings, and when the first text came.
    llm_stats: dict[str, float] = field(default_factory=dict)
    # GPU counters when the turn started (platform/hardware/nvml.py); the
    # turn record keeps what the turn cost the GPU, {} without an NVIDIA GPU.
    gpu_before: dict[str, float] = field(default_factory=dict)
    # The model that wrote the answer when routing chose another than
    # OLLAMA_MODEL (llm/model_router/turn_routing.py); "" when it did not.
    routed_model: str = ""


_RATING_INTENT = "feedback:rating"

# Whole utterances only. "that's wrong, the capital is Delhi" is a
# correction to act on, not a rating, so a sentence that merely contains
# one of these is left to the rest of the turn.
_RATED_WRONG = re.compile(
    r"(?:(?:that|it|this)\s*(?:'s|was|is)\s*(?:a\s+)?(?:wrong|not right|incorrect)(?:\s+answer)?"
    r"|(?:wrong|bad|incorrect) answer|you got (?:that|it) wrong"
    r"|(?:ye|yeh|yah)?\s*galat(?: jawab)?(?: hai| tha)?)",
)
_RATED_RIGHT = re.compile(
    r"(?:(?:that|it|this)\s*(?:'s|was|is)\s*(?:a\s+)?(?:right|correct|good)(?:\s+answer)?"
    r"|(?:good|right|correct) answer|well done"
    r"|(?:bilkul\s+)?sahi(?: jawab)?(?: hai| tha)?)",
)


def _spoken_rating(transcript: str) -> float | None:
    """1.0 when the whole utterance says the last answer was right, 0.0 wrong, else None."""
    text = re.sub(r"[^a-z' ]+", " ", transcript.lower())
    text = re.sub(r"^\s*(?:hey\s+)?(?:guru|maya)\b", " ", text)
    text = " ".join(text.split())
    if _RATED_WRONG.fullmatch(text):
        return 0.0
    if _RATED_RIGHT.fullmatch(text):
        return 1.0
    return None


@contextlib.contextmanager
def _timed(result: PipelineResult, stage: str) -> Iterator[None]:
    """Record how long *stage* took on *result*, also when it raises or returns early."""
    wall, start = time.time(), time.perf_counter()
    try:
        yield
    finally:
        result.stage_timings.append((stage, wall, time.perf_counter() - start))


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
INTENT_TIMEOUT_S = _env_seconds("AGENT_GURU_INTENT_TIMEOUT", 5.0)
LLM_TIMEOUT_S = _env_seconds("AGENT_GURU_LLM_TIMEOUT", 60.0)
POLICY_TIMEOUT_S = _env_seconds("AGENT_GURU_POLICY_TIMEOUT", 5.0)
TTS_TIMEOUT_S = _env_seconds("AGENT_GURU_TTS_TIMEOUT", 30.0)
MEMORY_WRITE_TIMEOUT_S = _env_seconds("AGENT_GURU_MEMORY_WRITE_TIMEOUT", 10.0)
# Writing the turn's trace happens after the reply, before main.py listens
# for a follow-up; a stalled disk must not hold that up.
TRACE_WRITE_TIMEOUT_S = _env_seconds("AGENT_GURU_TRACE_WRITE_TIMEOUT", 2.0)

#: Spoken when the LLM exceeds its budget. Saying nothing leaves the user
#: staring at a silent assistant; falling through to the generic "Done."
#: would be worse still, because it claims an action succeeded.
LLM_TIMEOUT_REPLY = "Sorry, that took too long for me to work out. Could you ask me again?"

#: How long a message draft waits for its answer. After that the next
#: utterance is an ordinary command again, so a question left unanswered
#: cannot turn a later, unrelated sentence into a message to someone.
MESSAGE_DRAFT_TTL_S = _env_seconds("AGENT_GURU_MESSAGE_DRAFT_TTL", 60.0)

#: Said instead of the missing recipient or text, the whole utterance and
#: nothing else, to drop a draft. Matched whole: a message may well contain
#: "no" or "stop" ("No rush, stop by later").
_DRAFT_CANCEL = frozenset({
    "cancel", "never mind", "nevermind", "forget it", "no", "nope", "nothing",
    "stop", "nahi", "rehne do", "chhodo", "mat bhejo",
})


def _local_now() -> _dt.datetime:
    """The system clock in the machine's own time zone (a seam for tests)."""
    return _dt.datetime.now().astimezone()


#: How a spoken command to open or close something begins, once the wake word is gone.
_OPEN_VERBS = re.compile(r"(?:open|launch|start|run|close|quit|exit|go to|visit|bring up|show me)\b", re.IGNORECASE)

#: Longest app or site name, in words, taken as said. Measured on 50 synthesized utterances
#: (scratchpad conf_measure.py, 2026-10-26): every clean command named at most 2 words ("file
#: explorer", "vs code"); the background speech the rule engine also routed to open_url named 5
#: ("door when the guests arrive"). 3 leaves room for "visual studio code".
_MAX_OPEN_TARGET_WORDS = 3

_BROWSER_NAMES = frozenset({"edge", "microsoft edge", "msedge", "chrome", "google chrome", "firefox", "mozilla firefox"})


def _open_command_doubt(transcript: str, action: str, target: str) -> str | None:
    """A question to ask instead of opening, when the words do not look like a command to open *target*; else None.

    The rule engine routes any sentence with "open" in it to open_app or open_url: speech heard
    after a false wake, "I opened the window in the morning" or "Guru, Open Note Packed", opened
    a browser on www.window.com or www.notepacked.com. Neither confidence could tell those apart:
    measured on 50 utterances, the rule engine gives every open_app 0.75 and every open_url 0.80,
    and Whisper was as sure of the background speech (mean log-probability -0.36 to -0.91) as of
    clean commands (-0.38 to -1.07, under noise). What did separate them: a command starts with
    its verb and names a short target, and a website the assistant does not know is a guess.
    """
    name = (target or "").strip()
    words = IntegrationOrchestrator._clean_transcript(transcript or "") if transcript else ""
    if words and not _OPEN_VERBS.match(words):
        return f"Did you want me to open {name}? If so, say it again as a command, like \"open {name}\"."
    if len(name.split()) > _MAX_OPEN_TARGET_WORDS:
        return f"I'm not sure \"{name}\" is something to open. Say just its name, like \"open notepad\"."
    if action == "open_url":
        from Agent_Guru.platform.browser_manager import _resolve_site_url

        lowered = name.lower()
        if lowered not in _BROWSER_NAMES and not _resolve_site_url(name) and not ("." in name and " " not in name):
            return (f"I don't know a website called {name}, so I won't guess one. "
                    f"Say its address, like {lowered.replace(' ', '')}.com, or the app's name.")
    return None


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
        *,
        trace_store: TurnTraceStore | None = None,
        audit_logger: AuditLogger | None = None,
        reminder_store: Path | None = None,
        learn_facts: bool = False,
        document_store: DocumentStore | None = None,
        mcp_servers: list[ServerConfig] | None = None,
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
        # Given by main.py. None (tests, embedders) records nothing, so a
        # test turn is never written into the user's own trace database.
        self.trace_store = trace_store
        # The last answer recorded, so "that was wrong" knows what it means.
        self._last_turn_id: str | None = None
        # Where reminders are kept between runs; from main.py. None keeps
        # them in memory, as tests need.
        self._reminder_store = reminder_store
        # What happened in the assistant, for the local API, channels and
        # anything else that reacts to it (integration/events.py).
        from Agent_Guru.integration.events import EventBus

        self.events = EventBus()
        # Chooses the model for each answer when AGENT_GURU_ROUTER = "auto";
        # built in startup(), None until then and when routing is off.
        self._turn_router: Any = None
        # Learn lasting facts about the owner from conversation, after each
        # answer (owner's choice, 2026-10-07). On from main.py only, so tests
        # never write into the owner's memory. Tasks are kept referenced so
        # none is collected mid-flight.
        self._learn_facts = learn_facts
        self._learning_tasks: set[asyncio.Task[None]] = set()
        # The owner's documents, searched for passages that answer a
        # question; from main.py. None (tests) searches nothing.
        self._documents = document_store
        # Tools on MCP servers the owner configured; from main.py. With none
        # configured nothing about MCP is loaded or started, and no turn is
        # offered tools.
        self._mcp_servers = list(mcp_servers or [])
        self._toolbox: MCPToolbox | None = None
        self._tools_starting: asyncio.Task[Any] | None = None
        # A call that changes things, waiting for the owner's yes.
        self._tool_pending: dict[str, Any] | None = None

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

        # Records every pipeline execution. main.py gives one kept on disk;
        # the default lives in memory, so tests never write to the owner's
        # audit log. It used to be the only kind: the whole trail was lost
        # whenever the app exited.
        self._audit_logger: AuditLogger = audit_logger or AuditLogger()

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

        # A message waiting for its recipient, its text or the user's yes:
        # {"app", "contact", "message", "expires"}. See _continue_message_draft.
        self._message_draft: dict[str, Any] | None = None

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
        # Loaded off the startup path: the first turn's GPU reading then
        # costs about 2 ms instead of 1.9 s (platform/hardware/nvml.py).
        from Agent_Guru.platform.hardware import nvml

        nvml.warm()
        from Agent_Guru.llm.model_router import turn_routing

        if turn_routing.enabled():
            router = turn_routing.TurnRouter()
            try:
                if await asyncio.to_thread(router.build, self.trace_store):
                    self._turn_router = router
            except Exception:
                logger.warning("Model routing unavailable", exc_info=True)
        logger.info("IntegrationOrchestrator.startup() - concurrent init begin")
        self._start_tools()

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

        # After the speech engine is up, so a reminder missed while the app
        # was off can be said now.
        if self._reminder_store is not None:
            try:
                await self._reminders().restore()
            except Exception:
                logger.exception("Kept reminders could not be restored")

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
        """Initialise a single subsystem, passing device_cfg if it takes one.

        This used to call initialize(device_cfg=...) and, on any TypeError,
        call initialize() again with nothing. SpeechEngine.initialize() takes
        no device_cfg, so Whisper's GPU allocation was dropped without a log
        line and every command was transcribed on the CPU (1.8 s against
        0.2 s for a 2.5 s command on an RTX 2050). The same except also
        caught TypeErrors raised inside an initialize() that does take the
        config, real bugs, and ran it a second time bare. Whether the config
        is passed is now decided from the signature, a dropped GPU
        allocation is a warning, and any exception is logged once as an
        error with its traceback.
        """
        try:
            init = getattr(subsystem, "initialize", None)
            if init is None:
                return
            kwargs: dict[str, Any] = {}
            if device_cfg is not None:
                if _accepts_device_cfg(init):
                    kwargs["device_cfg"] = device_cfg
                elif getattr(device_cfg, "device", "cpu") != "cpu":
                    logger.warning(
                        "Subsystem '%s' does not accept a device config: its %s "
                        "allocation is not applied and it chooses its own device",
                        name, device_cfg.device,
                    )
                else:
                    logger.info(
                        "Subsystem '%s' does not accept a device config; it chooses its own device",
                        name,
                    )
            if inspect.iscoroutinefunction(init):
                await init(**kwargs)
            else:
                # Synchronous initialize - run in a thread to avoid blocking
                await asyncio.to_thread(init, **kwargs)
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

        typed = wake_event.text is not None
        token = _TEXT_TURN.set(typed)
        # The filler plays while the turn is worked on. It was awaited before
        # STT, so every turn waited for the whole clip (0.58 to 0.84 s
        # measured) before transcription started, although main.py has
        # already recorded the command by the time the pipeline runs.
        # Playback holds the process-wide PortAudio lock, so the reply still
        # cannot start until the filler has finished. A typed turn has none.
        filler = None if typed else asyncio.create_task(self._play_filler(result, _wake_timestamp, _get_um))
        started_at = _time.time()
        # Only when startup() has already loaded NVML (a read then takes about
        # 2 ms). Its first load took 1.9 s here, and loading it during a turn,
        # even on a thread, held the turn by up to 1.6 s (measured in
        # test_filler_concurrency), so a turn never loads it.
        from Agent_Guru.platform.hardware import nvml

        if nvml.ready():
            result.gpu_before = nvml.read()
        _ROUTED_MODEL.set("")
        try:
            turn = await self._run_turn(wake_event, result, _wake_timestamp, _get_um)
            if turn is not result:
                turn.gpu_before = result.gpu_before
            await self._record_trace(turn, started_at, _time.perf_counter() - _wake_timestamp)
            return turn
        finally:
            _TEXT_TURN.reset(token)
            # Never left running unobserved; it is usually long finished.
            if filler is not None:
                with contextlib.suppress(asyncio.CancelledError):
                    await filler

    async def run_text_turn(self, text: str, personality: Personality = Personality.GURU) -> PipelineResult:
        """One typed turn through the same stages as a spoken one, without speech in or out.

        The text is taken as the transcript and the reply is left in the
        result (llm_response or action_result) instead of being spoken.
        Everything else is the voice turn's: memory, documents, intent,
        policy, actions, tools, records.
        """
        wake_word = "Hey Maya" if personality == Personality.MAYA else "Hey Guru"
        return await self.run_pipeline(WakeWordEvent(wake_word=wake_word, text=text))

    async def _run_turn(
        self, wake_event: WakeWordEvent, result: PipelineResult, _wake_timestamp: float, _get_um: Any,
    ) -> PipelineResult:
        """Stages 1 to 8 of run_pipeline, run while the filler plays."""
        _pipeline_mode = "full"
        result.pipeline_mode = _pipeline_mode

        try:
            # Stage 1: STT. On timeout the transcript stays empty, which the
            # existing "nothing was said" path below already handles.
            with _timed(result, "stt"):
                try:
                    if wake_event.text is not None:
                        result.transcript, result.detected_language = wake_event.text.strip(), ""
                    else:
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

            # Speaker verification (opt-in). A typed turn has no voice to
            # check; it comes from code running in this process, as the
            # owner's own (see run_text_turn).
            if wake_event.text is None:
                _pipeline_mode = self._verify_speaker(wake_event, result)

            # The answer to a question the previous turn asked about a
            # message ("What would you like me to send John?"). Before, there
            # was no such state: the answer was taken as a new command, so a
            # message without its text could only open the app. Ahead of the
            # reaction rules, so a rule taught for "yes" cannot answer it.
            with _timed(result, "message_draft"):
                draft_outcome = await self._continue_message_draft(result.transcript)
            if draft_outcome is not None:
                draft_reply = draft_outcome.text or _STATUS_REPLIES[draft_outcome.status]
                result.intent = "communication:message_draft"
                result.action_result, result.action_status = draft_reply, draft_outcome.status
                result.awaiting_reply = self._message_draft is not None
                self._chat_history.append({"role": "user", "content": result.transcript, "emotion": "neutral"})
                self._chat_history.append({"role": "assistant", "content": draft_reply})
                result.stages_completed = 8
                with _timed(result, "tts"):
                    result.tts_response = await self._stage_tts(draft_reply, result.personality)
                return result

            with _timed(result, "tool_confirmation"):
                confirmed = await self._continue_tool_confirmation(result, _pipeline_mode)
            if confirmed:
                return result

            rating = await self._rate_previous_answer(result.transcript, _pipeline_mode)
            if rating is not None:
                result.intent = _RATING_INTENT
                result.action_result, result.action_status = rating.text, rating.status
                result.stages_completed = 8
                with _timed(result, "tts"):
                    result.tts_response = await self._stage_tts(rating.text, result.personality)
                return result

            # Reaction-rule early returns
            with _timed(result, "reaction_rules"):
                early_result = await self._check_reaction_rules(
                    result, _pipeline_mode, _wake_timestamp, _get_um,
                )
            if early_result is not None:
                return early_result

            # Stage 2: Memory context. Recall is an enhancement, never a
            # precondition for answering, so a slow store degrades to "no
            # context" rather than stalling the turn.
            with _timed(result, "memory"):
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

            # There is no stage 3. It ran ReasoningEngine.process() under a
            # 2 s timeout, and for a question that call classifies the intent
            # with the LLM and then writes a whole answer of its own: 4 to 5 s
            # with gemma3:4b on a laptop GPU. So it was cancelled at 2.0 s on
            # every question and its work discarded, and the spoken answer
            # was requested only after that 2 s of waiting. The cancelled
            # classification even kept running in its worker thread. For a
            # rule-matched command it returned at once, and the prompt then
            # carried its repr, a canned answer included, as "[Reasoning:
            # ReasoningResult(...)]". Nothing else read its output. The turn
            # already has its own intent stage and its own answer call below.

            # Stage 5 (before 4): Intent detection - fast path
            with _timed(result, "intent"):
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

            # Facts the owner states about themselves ("I live in Pune",
            # "remember that ...") are read from what was said, before the
            # policy check. They were read inside the action stage from the
            # intent string: such sentences are a plain "conversation" with
            # no text, so the word "conversation" was searched and nothing
            # was ever stored, and the production policy (messaging only)
            # never let that stage run anyway. Like rating an answer, this
            # changes only the assistant's own records, for the verified
            # owner only. Commands are left alone: "send a message to John
            # saying my name is Ravi" is dictation, not a fact about the owner.
            intent_type = (result.intent or "").split(":", 1)[0]
            fact_reply = None
            if intent_type in {"", "conversation", "information"}:
                with _timed(result, "user_facts"):
                    fact_reply = await self._handle_user_memory(result.transcript or "", _pipeline_mode, intent_type)
            if fact_reply is not None:
                result.action_result, result.action_status = fact_reply, ActionStatus.SUCCESS

            # Stage 6: Policy check
            if fact_reply is None:
                with _timed(result, "policy"):
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
            if fact_reply is not None:
                pass  # acknowledged above; there is no action to authorize
            elif result.policy_allowed:
                with _timed(result, "action"):
                    outcome = await self._stage_action(
                        result.intent, pipeline_mode=result.pipeline_mode, transcript=result.transcript or "",
                    )
                result.action_result, result.action_status = outcome.text, outcome.status
            elif result.intent:
                # Refused, not done. This used to leave the reply empty, and
                # an empty reply was spoken "Done.".
                result.action_status = ActionStatus.DENIED
            result.stages_completed = 7

            # Stage 4: LLM inference (only if needed). Stages 6 and 7 now run
            # first: they read only the intent, never the LLM's answer, and
            # whether the action produced a reply decides whether the answer
            # is spoken at all, which must be known before it can be spoken
            # while it is written.
            needs_llm = self._intent_needs_llm(result.intent, result.transcript or "")
            llm_done, streamed_tts = False, None
            if needs_llm and not result.action_result and self._mcp_servers:
                # Tools are offered only when the owner configured some; the
                # answer is then written by the tool loop, spoken as it goes.
                with _timed(result, "answer_tools"):
                    llm_done, streamed_tts = await self._answer_with_tools(result, _pipeline_mode)
            if needs_llm and not result.action_result and not llm_done:
                # Written and spoken together: this stage includes the speech.
                with _timed(result, "answer_spoken"):
                    llm_done, streamed_tts = await self._speak_llm_reply(result)
            if needs_llm and not llm_done:
                with _timed(result, "answer"):
                    try:
                        result.llm_response = await asyncio.wait_for(
                            self._stage_llm(
                                result.transcript, result.memory_context,
                                result.detected_language,
                                personality=result.personality,
                                intent=result.intent,
                            ),
                            timeout=LLM_TIMEOUT_S,
                        )
                    except TimeoutError:
                        logger.warning("LLM stage exceeded %.1fs", LLM_TIMEOUT_S)
                        result.llm_response = LLM_TIMEOUT_REPLY
                        result.error = f"llm_timeout after {LLM_TIMEOUT_S:.1f}s"
            elif not needs_llm:
                result.llm_response = None

            # A draft started by this turn's action, or a tool call this
            # turn's answer asked about, is waiting for an answer.
            result.awaiting_reply = self._message_draft is not None or self._tool_pending is not None

            # Stage 8: TTS
            tts_text = self._finalize_tts_text(result)
            # Not wrapped in one wait_for any more: a streamed reply plays for
            # as long as it is, and a 30 s cap on the whole stage cut a long
            # answer off mid-sentence. _stage_tts bounds every wait for
            # synthesis by TTS_TIMEOUT_S instead, and the whole-reply path
            # keeps its old overall bound.
            try:
                if streamed_tts is not None:
                    result.tts_response = streamed_tts  # already spoken as it was written
                else:
                    with _timed(result, "tts"):
                        result.tts_response = await self._stage_tts(tts_text, result.personality)
            except TimeoutError:
                logger.warning(
                    "TTS stage exceeded %.1fs - no audio for this turn", TTS_TIMEOUT_S,
                )
                result.tts_response = None
                result.error = f"tts_timeout after {TTS_TIMEOUT_S:.1f}s"
            stream_error = getattr(result.tts_response, "error", None)
            if isinstance(stream_error, str):
                result.error = f"tts_incomplete: {stream_error}"
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
                self._learn_from_turn(result, tts_text, fact_reply, _pipeline_mode)

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

    async def _record_trace(self, result: PipelineResult, started_at: float, turn_seconds: float) -> None:
        """Keep what this turn heard, did, said and how long each stage took. Never raises.

        Runs after the reply has been spoken. The write goes to a worker
        thread and is bounded, so a slow or broken disk costs at most
        TRACE_WRITE_TIMEOUT_S before main.py listens again, and costs the
        record, not the turn.
        """
        store = self.trace_store
        try:
            if result.gpu_before:
                from Agent_Guru.platform.hardware import nvml

                gpu = nvml.turn_detail(result.gpu_before, await asyncio.to_thread(nvml.read), turn_seconds)
                if gpu:
                    result.tool_stages.append(StageTiming(name="gpu", started_at=started_at, seconds=turn_seconds, detail=gpu))
            result.routed_model = result.routed_model or _ROUTED_MODEL.get()
            turn = self._turn_record(result, started_at, turn_seconds)
            if self._turn_router is not None and turn.outcome in ("success", "failure"):
                self._turn_router.record(turn.model, turn.heard, turn.outcome == "success", turn_seconds * 1000)
            self.events.publish(
                "turn.finished", turn_id=turn.turn_id, heard=turn.heard, said=turn.said,
                intent=turn.intent, status=turn.action_status, seconds=round(turn_seconds, 2),
            )
            if store is None:
                return
            await asyncio.wait_for(asyncio.to_thread(store.record, turn), timeout=TRACE_WRITE_TIMEOUT_S)
            if result.intent != _RATING_INTENT:
                self._last_turn_id = turn.turn_id
        except TimeoutError:
            logger.warning("Recording this turn exceeded %.1fs - turn not recorded", TRACE_WRITE_TIMEOUT_S)
        except Exception:
            logger.warning("Could not record this turn", exc_info=True)

    def _learn_from_turn(
        self, result: PipelineResult, reply: str, fact_reply: str | None, pipeline_mode: str,
    ) -> None:
        """Start learning lasting facts about the owner from this exchange, in the background.

        Only facts were remembered that the owner stated in a fixed form ("my
        name is", "remember that"); "I'm training for a marathon in December"
        was forgotten. The model reads the exchange after the reply is spoken
        (measured: 0.56 s on gemma4, and the next answer's first words 0.13 s
        later when the owner speaks again at once). Commands, ratings, a turn
        already handled as a stated fact, and an unverified speaker are left
        out.
        """
        if not self._learn_facts or fact_reply is not None or pipeline_mode != "full":
            return
        if (result.intent or "").split(":", 1)[0] not in {"", "conversation", "information"}:
            return
        complete = getattr(self.llm_runtime, "complete", None)
        if complete is None or not inspect.iscoroutinefunction(complete):
            return
        task = asyncio.create_task(self._learn(complete, result.transcript or "", reply))
        self._learning_tasks.add(task)
        task.add_done_callback(self._learning_tasks.discard)

    async def _learn(self, complete: Any, said: str, reply: str) -> None:
        from Agent_Guru.platform.features.user_memory import (
            get_user_memory,
            learn_facts_from_exchange,
        )

        kept, quarantined = await learn_facts_from_exchange(complete, _configured_ollama_model(), said, reply)
        if quarantined:
            logger.warning("Facts quarantined, never recalled: %s", quarantined)
        if kept or quarantined:
            added = await asyncio.to_thread(get_user_memory().add_learned_facts, kept, quarantined)
            if added:
                logger.info("Learned about the owner: %s", kept)

    async def _rate_previous_answer(self, transcript: str, pipeline_mode: str) -> ActionOutcome | None:
        """Mark the last recorded answer right or wrong when that is all the user said; None otherwise.

        Before, there was no way to say an answer was wrong: "that was
        wrong" went to the model as a new question. Handled ahead of the
        policy check because it changes nothing outside the assistant's own
        records, and ahead of reaction rules so a taught rule cannot swallow
        it. Only the verified owner (pipeline_mode "full") can rate.
        """
        score = _spoken_rating(transcript or "")
        if score is None or pipeline_mode != "full":
            return None
        store, turn_id = self.trace_store, self._last_turn_id
        if store is None or turn_id is None:
            return ActionOutcome("There's no earlier answer I can mark.", ActionStatus.FAILED)
        try:
            marked = await asyncio.wait_for(
                asyncio.to_thread(store.rate, turn_id, score), timeout=TRACE_WRITE_TIMEOUT_S,
            )
        except Exception:
            logger.warning("Could not rate turn %s", turn_id, exc_info=True)
            marked = False
        if not marked:
            return ActionOutcome("Sorry, I couldn't mark that answer.", ActionStatus.FAILED)
        if score == 0.0:
            return ActionOutcome("Sorry about that. I've marked that answer as wrong.", ActionStatus.SUCCESS)
        return ActionOutcome("Thanks, I've marked that answer as right.", ActionStatus.SUCCESS)

    @staticmethod
    def _turn_record(result: PipelineResult, started_at: float, turn_seconds: float) -> TurnRecord:
        """The TurnRecord for one turn, from its PipelineResult."""
        status = result.action_status
        if result.error or status is ActionStatus.FAILED:
            outcome: str | None = "failure"
        elif status is ActionStatus.SUCCESS:
            outcome = "success"
        else:
            # An answer may or may not have been right; an unverified,
            # refused or cancelled action is not a success either.
            outcome = None
        said = result.llm_response or (result.action_result if isinstance(result.action_result, str) else "")
        answered = any(name.startswith("answer") for name, _, _ in result.stage_timings)
        details_by_stage = {
            "stt": {"chars": len(result.transcript or ""), "language": result.detected_language},
            "memory": {"recalled": bool(result.memory_context)},
            "intent": {"intent": result.intent},
            "policy": {"allowed": result.policy_allowed},
            "action": {"status": status.value if status else None},
            "answer_spoken": dict(result.llm_stats),
        }
        tts = result.tts_response
        speech_error = getattr(tts, "error", None)
        return TurnRecord(
            started_at=started_at,
            seconds=turn_seconds,
            personality=result.personality.value,
            heard=result.transcript or "",
            said=said or "",
            intent=result.intent,
            action_status=status.value if status else None,
            outcome=outcome,
            model=(result.routed_model or _configured_ollama_model()) if answered else "",
            stages=sorted(
                [
                    StageTiming(name=name, started_at=wall, seconds=seconds, detail=details_by_stage.get(name, {}))
                    for name, wall, seconds in result.stage_timings
                ] + list(result.tool_stages),
                key=lambda stage: stage.started_at,
            ),
            details={
                "policy_allowed": result.policy_allowed,
                "pipeline_mode": result.pipeline_mode,
                "stages_completed": result.stages_completed,
                "awaiting_reply": result.awaiting_reply,
                "error": result.error,
                "first_audio_s": getattr(tts, "first_audio_s", None),
                "audio_seconds": getattr(tts, "audio_seconds", None),
                "speech_error": speech_error if isinstance(speech_error, str) else None,
                "sources": result.sources,
            },
        )

    async def _play_filler(
        self, result: PipelineResult, wake_timestamp: float, _get_um: Any,
    ) -> None:
        """Play filler audio in the post-wake-word pause."""
        try:
            from Agent_Guru.speech.filler_response import get_filler_cache
            _filler_cache = get_filler_cache()
            if not _filler_cache._initialized:
                # Startup normally builds the cache. If it has not, building
                # it now takes seconds (7.0 s measured) and the filler would
                # play after a quick reply, so this turn goes without one and
                # the cache is built for the next.
                if getattr(self, "_filler_warmup", None) is None:
                    self._filler_warmup = asyncio.ensure_future(asyncio.to_thread(_filler_cache.initialize))
                return
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
            # What the action actually did. This was "Done." whatever had
            # happened: a refused action, one that raised, a command nothing
            # handled. "Done." is now said only for a success with no reply.
            tts_text = _STATUS_REPLIES[result.action_status]

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
        """Stage 2: Retrieve memory context.

        MemoryManager.search() is told which turns the chat history already
        holds. It used to be asked with the transcript alone, and as every
        turn is also stored as a memory, it returned this session's earlier
        turns beside the same turns in the history, together with whatever
        else was nearest. That block differed every turn and stopped Ollama
        reusing the previous turn's prompt processing. search() now returns
        only memories relevant to the question and new to the conversation.
        """
        try:
            fn = getattr(self.memory, "retrieve", None)
            kwargs: dict[str, Any] = {}
            if fn is None:
                fn = getattr(self.memory, "search", None)
                kwargs = {"known": self._conversation_turns()}
            if fn is None:
                return None
            if inspect.iscoroutinefunction(fn):
                return await fn(transcript, **kwargs)
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: fn(transcript, **kwargs))
        except Exception:
            logger.exception("Memory stage error")
            return None

    def _conversation_turns(self) -> list[tuple[str, str]]:
        """(user, reply) pairs in the chat history, as _store_turn_in_memory stores them."""
        history = list(self._chat_history)
        return [
            (said["content"], reply["content"])
            for said, reply in zip(history, history[1:], strict=False)
            if said.get("role") == "user" and reply.get("role") == "assistant"
        ]

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
                    result = await fn(transcript, memory_context)
                else:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None, fn, transcript, memory_context,
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
                language_code, personality, intent,
            )
        except Exception:
            logger.exception("LLM stage error")
            return ""

    async def _llm_complete(
        self,
        complete_fn: Any,
        transcript: str,
        memory_context: Any,
        language_code: str,
        personality: Personality | None,
        intent: str | None = None,
    ) -> str:
        """Build enriched prompt and run LLM completion."""
        try:
            built = await self._build_llm_request(
                transcript, memory_context, language_code, personality, intent,
            )
            if built is None:
                return ""
            request, rewrites_clipboard = built
            response = await complete_fn(request)
            llm_response = response.content or ""
            if not rewrites_clipboard and getattr(response, "finish_reason", None) == "length":
                llm_response = self._drop_unfinished_sentence(llm_response)

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
            ollama_model = _configured_ollama_model()
            logger.error(
                "LLM stage: inference failed (model=%s): %s - "
                "check Ollama is running and the model is pulled: "
                "ollama pull %s",
                ollama_model, e, ollama_model,
            )
            return ""

    async def _build_llm_request(
        self,
        transcript: str,
        memory_context: Any,
        language_code: str,
        personality: Personality | None,
        intent: str | None,
        *,
        web_context: bool = True,
    ) -> tuple[Any, bool] | None:
        """The LLM request for this turn and whether it rewrites the clipboard; None if nothing to ask.

        web_context=False leaves out the web search snippet: a tool turn that
        researches the question gets the same results as numbered sources
        instead.

        Shared by the whole answer (_llm_complete) and the answer spoken as it
        is written (_speak_llm_reply), so both ask the model the same thing.
        """
        from Agent_Guru.llm.models import CompletionRequest, Message
        from Agent_Guru.reasoning.llm.generation import spoken_reply_tokens

        prompt = self._enrich_prompt(transcript, memory_context)
        if not prompt.strip():
            return None

        # Emotion detection from RAW transcript (not enriched prompt)
        emotion_hint = self._detect_emotion(transcript)

        # Web search enrichment
        web_snippet = await self._fetch_web_context(transcript, intent) if web_context else ""
        if web_snippet:
            prompt = prompt + web_snippet
        document_context = await self._fetch_document_context(transcript, intent)
        if document_context:
            prompt = prompt + document_context

        # Resolve model and build system prompt
        ollama_model = _configured_ollama_model()
        if self._turn_router is not None:
            routed, why = await self._turn_router.choose(transcript, ollama_model)
            if routed != ollama_model:
                logger.info("Answer routed to %s (%s)", routed, why)
                ollama_model = routed
                _ROUTED_MODEL.set(routed)
        system_prompt = self._build_system_prompt(
            personality, emotion_hint, language_code, ollama_model,
            transcript=transcript,
        )

        # What changes from turn to turn goes in front of the user's words,
        # not in the system prompt. Not at the end of the message: a
        # clipboard or screen prompt ends with the user's own text, and a
        # note after it would read as part of that text.
        turn_note = self._turn_note()
        if turn_note:
            prompt = f"{turn_note}\n{prompt}"

        # Build message list with token-budgeted history
        messages = self._build_llm_messages(Message, system_prompt, prompt)

        # A spoken reply is capped (see spoken_reply_tokens() for the
        # measurements). A clipboard rewrite is not spoken, it is written
        # back for the user to paste, and a capped one would silently lose
        # the end of their text, so it keeps the old budget.
        rewrites_clipboard = self._rewrites_clipboard(transcript)
        request = CompletionRequest(
            model=ollama_model,
            messages=messages,
            max_tokens=(
                self._CLIPBOARD_REWRITE_MAX_TOKENS
                if rewrites_clipboard
                else spoken_reply_tokens()
            ),
        )
        return request, rewrites_clipboard

    async def _speak_llm_reply(self, result: PipelineResult) -> tuple[bool, Any]:
        """Speak the LLM's answer while it is being written.

        The answer used to be spoken only after the model had finished it.
        With gemma4 and Kokoro on the development laptop the first sentence
        of a question's answer was complete about 2.1 s after the request
        and the whole answer about 5 s after it. Here each sentence is
        synthesised and played as soon as it is complete
        (speech/tts/streaming.py). Measured with the real models, median
        time to first audio for a question fell from 8.87 s to 6.17 s (6
        turns each, ranges 8.35-9.13 s and 5.69-6.72 s). During a period
        when the laptop ran Kokoro 4 to 5 times slower than usual it fell
        only from 12.26 s to 11.04 s, because synthesising the first
        sentence then took longer than the generation it overlaps.

        Only for turns where the LLM's answer is what will be spoken, so the
        reply is unchanged: no action result (it would replace the answer),
        not a clipboard command (it changes what is said), a runtime with
        stream() and complete(), and an array synthesiser to stream into.

        Returns (llm_done, tts_response):
          (False, None)  not streamed, or failed before any text was
                         spoken; the usual LLM and TTS stages run, so a
                         failure keeps complete()'s retries.
          (True, stream) spoken; result.llm_response holds the answer.
          (True, None)   no text arrived in time; result.llm_response is
                         the usual timeout reply, for the TTS stage to say.
        """
        from Agent_Guru.platform.features.dictation import is_clipboard_command

        llm = self.llm_runtime
        stream_fn = getattr(llm, "stream", None)
        tts_fn = self._streamable_tts_fn()
        if (
            getattr(llm, "infer", None) is not None
            or getattr(llm, "complete", None) is None
            or stream_fn is None
            or tts_fn is None
            or is_clipboard_command(result.transcript or "")
        ):
            return False, None
        try:
            built = await self._build_llm_request(
                result.transcript or "", result.memory_context, result.detected_language,
                result.personality, result.intent,
            )
        except Exception:
            logger.debug("Streamed reply: request could not be built", exc_info=True)
            return False, None
        if built is None:
            return False, None
        request, _ = built
        finish: dict[str, str] = {}
        parts: list[str] = []

        stats = result.llm_stats

        async def chunks() -> Any:
            asked = time.perf_counter()
            arrivals: list[float] = []
            async for chunk in stream_fn(request):
                if chunk.finish_reason:
                    finish["reason"] = chunk.finish_reason
                if chunk.content:
                    arrivals.append(time.perf_counter())
                    stats.setdefault("first_text_s", arrivals[-1] - asked)
                    parts.append(chunk.content)
                    yield chunk.content
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    stats["prompt_tokens"] = usage.prompt_tokens
                    stats["output_tokens"] = usage.completion_tokens
                stats.update(getattr(chunk, "timings", None) or {})
            if stats.get("output_tokens") and stats.get("decode_s"):
                stats["tokens_per_s"] = stats["output_tokens"] / stats["decode_s"]
            from Agent_Guru.llm.telemetry import inter_token_stats

            stats.update(inter_token_stats(arrivals))

        def capped() -> bool:
            return finish.get("reason") == "length"

        try:
            spoken = await self._speak_streaming(
                tts_fn, chunks(), result.personality, capped=capped, text_timeout_s=LLM_TIMEOUT_S,
            )
        except Exception:
            logger.warning(
                "Streamed reply failed before its first sentence - answering the usual way",
                exc_info=True,
            )
            return False, None
        if spoken.spoken == 0:
            if parts or spoken.error is None:
                # Text came but none of it could be spoken, or none came at
                # all: the usual path answers (and retries) instead.
                return False, None
            logger.warning("LLM stage: no text within %.1fs", LLM_TIMEOUT_S)
            result.llm_response = LLM_TIMEOUT_REPLY
            result.error = f"llm_timeout after {LLM_TIMEOUT_S:.1f}s"
            return True, None
        answer = "".join(parts)
        result.llm_response = self._drop_unfinished_sentence(answer) if capped() else answer
        return True, spoken

    #: Reply budget for a clipboard "fix", which returns up to 1000 characters
    #: of the user's text rewritten (_enrich_prompt() caps the input there).
    _CLIPBOARD_REWRITE_MAX_TOKENS: ClassVar[int] = 400

    @staticmethod
    def _rewrites_clipboard(transcript: str) -> bool:
        """True if this turn's reply is written back to the clipboard, not spoken."""
        from Agent_Guru.platform.features.dictation import (
            get_clipboard_action,
            is_clipboard_command,
        )

        return bool(transcript) and is_clipboard_command(transcript) and (
            get_clipboard_action(transcript) == "fix"
        )

    @staticmethod
    def _drop_unfinished_sentence(text: str) -> str:
        """Cut a reply that hit the token cap back to its last full sentence.

        Without this, the cap would end speech mid-word ("the Indus Valley
        Civilization was one of the"). If the reply has no sentence end at
        all, it is kept whole: half an answer is better than silence.
        """
        stripped = text.rstrip()
        last_end = max(stripped.rfind(mark) for mark in ".!?")
        if last_end <= 0:
            return stripped
        return stripped[: last_end + 1]

    @staticmethod
    def _enrich_prompt(transcript: str, memory_context: Any) -> str:
        """Build the enriched prompt with context, clipboard, and screen content."""
        prompt = transcript or ""
        if not prompt.strip():
            return ""
        if memory_context:
            prompt = f"[Context: {memory_context}]\n{prompt}"

        # Inject clipboard content if the user is asking about it
        from Agent_Guru.llm.security import guard_external_text
        from Agent_Guru.platform.features.dictation import (
            get_clipboard_action, get_clipboard_text, is_clipboard_command,
        )
        if is_clipboard_command(prompt):
            # Copied from anywhere, so it may carry instructions meant for
            # the model; see guard_external_text().
            clip_text = guard_external_text(get_clipboard_text() or "", "clipboard")
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
            screen_text = guard_external_text(read_screen_text() or "", "screen")
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
        # The same steps the action stage runs (_intent_steps). Splitting a message's text here made
        # "...saying my bank pin is 4321|information:news" search the web with the dictated words.
        steps = _intent_steps(intent)
        if len(steps) > 1:
            return any(IntegrationOrchestrator._intent_needs_web(step, transcript) for step in steps)
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
        from Agent_Guru.llm.security import guard_external_text_async
        from Agent_Guru.platform.features.web_search import search_web

        if not self._intent_needs_web(intent, transcript):
            return ""
        web_snippet = await guard_external_text_async(await search_web(transcript) or "", "web search")
        if web_snippet:
            logger.info("Web search injected for: %r", transcript[:60])
            return f"\n\nLive web search result: {web_snippet}"
        return ""

    async def _fetch_document_context(self, transcript: str, intent: str | None) -> str:
        """Passages from the owner's documents that answer this turn, named by document.

        Only for conversation and questions, and not for live information
        (weather, news, a search): "what is the weather in Pune today" found
        the Goa itinerary's Pune flight at 0.49 in the calibration set, and
        the forecast is what was asked for. Each passage passes the
        injection guard, since its text was written by someone else.
        """
        if self._documents is None or not transcript.strip():
            return ""
        intent_type = (intent or "").split(":", 1)[0].lower().strip()
        if intent_type not in {"", "conversation", "information"} or self._intent_needs_web(intent, transcript):
            return ""
        from Agent_Guru.llm.security import guard_external_text_async

        try:
            passages = await asyncio.wait_for(self._documents.search(transcript), timeout=MEMORY_TIMEOUT_S)
        except TimeoutError:
            logger.warning("Document search exceeded %.1fs - answering without documents", MEMORY_TIMEOUT_S)
            return ""
        except Exception:
            logger.exception("Document search failed - answering without documents")
            return ""
        kept = [
            f"[{p.document}] {text}"
            for p in passages
            if (text := await guard_external_text_async(p.text, f"document {p.document}"))
        ]
        if not kept:
            return ""
        logger.info("Document passages for %r: %s", transcript[:60], [p.document for p in passages])
        return "\n\nFrom the owner's documents:\n" + "\n".join(kept)

    def _build_system_prompt(
        self,
        personality: Personality | None,
        emotion_hint: str,
        language_code: str,
        ollama_model: str,
        transcript: str = "",
    ) -> str:
        """Build the full system prompt with persona, emotion, distress, and language hints.

        The turn number and recent moods are not here; see _turn_note(). They
        changed on every turn, so the system prompt did too, and Ollama, which
        reuses a previous request's prompt processing only up to where the new
        request first differs, processed the whole request again: 2.0 to 2.5 s
        before the first word of each answer with gemma4, 2,000 to 2,800
        tokens.

        This turn's emotion and its tone note stay here although they change
        when the user's tone does, which costs that reuse on those turns. Sent
        beside the user's words instead, the guidance was followed literally:
        "And roughly how many people live there?" (misread as frustrated)
        was answered in 5 of 5 tries with the guidance's own example ("ugh,
        that it keeps failing on you is genuinely annoying") and no number;
        with the guidance here, 4 of 4 answers gave the population.

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

        # Guidance the owner's own mistakes taught, kept only after it passed
        # the evaluation gate (self_improvement/prompt_tuning.py). The same
        # text every turn, so it does not cost Ollama's prompt reuse.
        from Agent_Guru.self_improvement.prompt_tuning import current_guidance

        guidance = current_guidance()
        if guidance:
            system_prompt += "\n\nGuidance learned from earlier mistakes:\n" + guidance

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

        return system_prompt

    def _turn_note(self) -> str:
        """The turn number and recent moods, sent at the head of the user's message.

        These lines used to end the system prompt (see _build_system_prompt()
        for why they no longer do). Their wording is unchanged.
        """
        lines: list[str] = []

        # Conversation context note
        _turn_count = len(self._chat_history) // 2 + 1
        _recent_moods = [
            h.get("emotion", "neutral")
            for h in list(self._chat_history)[-6:]
            if h.get("role") == "user"
        ]
        if _turn_count > 1 and _recent_moods:
            mood_summary = ", ".join(_recent_moods[-3:])
            lines.append(
                f"CONVERSATION STATE: This is turn {_turn_count}. "
                f"The user's recent mood: [{mood_summary}].",
            )
        elif _turn_count == 1:
            # This used to tell the model to greet and ask what's up on every
            # first turn, so a first question was answered only after a
            # sentence of small talk: measured with gemma4, the answer began
            # 128 characters in (median of 10), spoken before the user heard
            # what they asked for.
            lines.append(
                "SESSION START: This is the FIRST interaction of this session. "
                "If the user is greeting you or just chatting, greet them warmly like a friend "
                "you haven't talked to in a bit. If they asked something or want something done, "
                "start your reply with the answer and do not open with a greeting; "
                "a few friendly words after the answer are fine.",
            )
        if not lines:
            return ""
        return "[Notes for this reply, not said by the user:\n" + "\n".join(lines) + "]"

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

            # A message is encoded from the transcript as spoken. Cleaning
            # drops filler words and the multi-step splitter cuts at "and",
            # so "send a message to John saying I'm late and sorry" reached
            # the action as "I'm late and". The text after the recipient is
            # what the user wants sent, so it must arrive unchanged; it rides
            # in the last field, which the action stage splits off whole.
            spoken = self._intent_recognizer._rule_engine.recognize(
                llm_response.strip(), self._intent_recognizer._platform,
            )
            p = spoken.parameters
            if (
                spoken.intent_type == "communication"
                and p.get("action") in ("send_message", "reply")
                and (p.get("message") or p.get("clarification"))
            ):
                logger.info("Intent: %s to %r via %s", p["action"], p.get("contact", ""), p.get("level") or "whatsapp")
                return (
                    f"communication:{p['action']}:{p.get('contact', '')}:"
                    f"{p.get('level') or 'whatsapp'}:{p.get('message', '')}"
                )

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

        A multi-step intent is allowed only when every step is: the action
        stage runs each step on its own (see _intent_steps).
        """
        steps = _intent_steps(intent or "")
        if len(steps) > 1:
            for step in steps:
                if not await self._stage_policy(step):
                    logger.info("Policy denied step %r of a %d-step intent", step[:80], len(steps))
                    return False
            return True
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

    async def _stage_action(self, intent: str, pipeline_mode: str = "full", transcript: str = "") -> ActionOutcome:
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
            return ActionOutcome(None, None)

        # ── Multi-step execution ──────────────────────────────────────────
        # The steps' replies are joined; the status is the worst of theirs,
        # so one failed step is not hidden behind the others' success.
        steps = _intent_steps(intent)
        if len(steps) > 1:
            results = []
            statuses: list[ActionStatus] = []
            for step in steps:
                try:
                    step_outcome = await self._execute_single_action(step, pipeline_mode)
                    if step_outcome.text:
                        results.append(step_outcome.text)
                    if step_outcome.status is not None:
                        statuses.append(step_outcome.status)
                    # Give apps time to open before the next step
                    await asyncio.sleep(1.5)
                except Exception:
                    logger.exception("Multi-step action failed for step %r", step)
                    statuses.append(ActionStatus.FAILED)
            status = next((st for st in _STATUS_SEVERITY if st in statuses), None)
            return ActionOutcome(". ".join(results) if results else None, status)

        # ── Single action ─────────────────────────────────────────────────
        return await self._execute_single_action(intent, pipeline_mode, transcript=transcript)

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

    async def _execute_single_action(
        self, intent: str, pipeline_mode: str = "full", transcript: str = "",
    ) -> ActionOutcome:
        """Execute a single intent string. Returns a human-readable result or None.

        Args:
            intent: Encoded intent string 'intent_type:action:param:level'.
            pipeline_mode: "full" or "restricted". Gates destructive actions
                and memory writes for this call. Always passed explicitly by
                the caller (_stage_action) - never read off `self`. See the
                module docstring's "Concurrency note".
        """
        if not intent:
            return ActionOutcome(None, None)

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
                    if isinstance(result, str) and result:
                        return ActionOutcome(result, ActionStatus.SUCCESS)
                    if isinstance(getattr(result, "success", None), bool):
                        return _outcome(getattr(result, "message", None) or None, [_call_status(result)])
                    # None hands over to platform control; anything else
                    # (a stub's MagicMock) says nothing and is not spoken.
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
            # The intent for these two carries no parameter, only a label:
            # "good morning" arrived here as "system_control:briefing" and
            # "what's my battery level" as "system_control:system_status",
            # which no feature check matches, so both fell through to
            # platform control and were answered "Sorry, I couldn't do
            # that." They are decided on the owner's own words instead.
            if action in ("briefing", "system_status") and transcript:
                raw_text = transcript
            feature_result = await self._detect_universal_features(
                raw_text, pipeline_mode, intent_type, action=action,
            )
            if isinstance(feature_result, ActionOutcome):
                return feature_result
            if feature_result is not None:
                # An answer the feature worked out (a briefing, the screen,
                # a reminder set), not a claim about a controller call.
                return ActionOutcome(str(feature_result), ActionStatus.SUCCESS)

            # Conversation → no action
            if intent_type == "conversation":
                return ActionOutcome(None, None)

            if intent_type not in ("system_control", "file_ops", "communication", "information"):
                logger.info(
                    "ACTION SKIPPED - intent_type=%r. Full intent: %r",
                    intent_type, safe_intent,
                )
                return ActionOutcome(None, None)

            # Before the controller check: reading the clock needs no platform
            # controller, and a missing one must not turn this into silence.
            if intent_type == "information" and action == "time_date":
                return ActionOutcome(_clock_answer(), ActionStatus.SUCCESS)

            # Asked, not done, when the words do not read as a command to open this (see
            # _open_command_doubt): garbled or overheard speech used to open guessed websites.
            if action in ("open_app", "open_url"):
                doubt = _open_command_doubt(transcript, action, param)
                if doubt is not None:
                    logger.info("Not opening %r: the request was unclear", param[:80])
                    return ActionOutcome(doubt, ActionStatus.CANCELLED)

            ctrl = self.platform_controller
            if ctrl is None:
                return ActionOutcome(None, None)

            # Dispatch to action-specific handlers, through a wrapper that
            # notes what each controller call returned (see _ControllerCalls).
            calls = _ControllerCalls(ctrl)
            reply = await self._dispatch_action(
                action, intent_type, param, level_str, safe_intent, calls,
            )
            return _outcome(reply, calls._record)

        except Exception:
            # An action that raised did not work. It used to return None,
            # which was spoken "Done.".
            logger.exception("Action stage error")
            return ActionOutcome(None, ActionStatus.FAILED)

    # ------------------------------------------------------------------
    # _execute_single_action decomposed helpers
    # ------------------------------------------------------------------

    async def _gate_destructive_action(
        self, action: str, pipeline_mode: str, safe_intent: str,
    ) -> ActionOutcome | None:
        """Check destructive-action gate. Returns the outcome to block with, or None to allow."""
        try:
            from Agent_Guru.platform.features.confirmation import is_destructive_action

            if is_destructive_action(action):
                if pipeline_mode == "restricted":
                    logger.info(
                        "Destructive action '%s' blocked - unverified speaker "
                        "(restricted mode)", action,
                    )
                    return ActionOutcome("Sorry, can't do that without verifying it's you.", ActionStatus.DENIED)

                confirmed = await self._confirm_destructive_action(action, safe_intent)
                if not confirmed:
                    return ActionOutcome("Okay, cancelled - didn't do that.", ActionStatus.CANCELLED)
        except ImportError:
            if action in {
                "delete_file", "delete_folder", "remove", "shutdown",
                "restart", "uninstall", "format", "wipe", "empty_trash",
            }:
                logger.warning(
                    "confirmation module unavailable - denying destructive "
                    "action '%s' for safety", action,
                )
                return ActionOutcome(
                    "Sorry, I can't confirm that action right now, so I won't do it.", ActionStatus.DENIED,
                )
        except Exception:
            logger.exception("Destructive-action gate failed - denying for safety")
            return ActionOutcome("Something went wrong checking that - I didn't do it, try again.", ActionStatus.FAILED)
        return None

    #: The intent actions each feature belongs to. A feature runs only for its own action, so the
    #: action the policy checked is the one that happens. The features used to be matched on the
    #: text of whatever intent was allowed: "open dictate pwned" was allowed as open_url and then
    #: typed "pwned" into the window in front, "open input del C:\x" typed "del C", and "open my
    #: clipboard" read the clipboard aloud, though typing and the clipboard are refused as actions.
    _FEATURE_ACTIONS: ClassVar[dict[str, frozenset[str]]] = {
        "briefing": frozenset({"briefing"}),
        "system_status": frozenset({"system_status"}),
        "reminder": frozenset({"reminder"}),
        "dictation": frozenset({"dictate", "type_text"}),
        "clipboard": frozenset({"clipboard"}),
        "screen_read": frozenset({"screen_read"}),
    }

    async def _detect_universal_features(
        self, raw_text: str, pipeline_mode: str, intent_type: str = "", *, action: str,
    ) -> Any | None:
        """Run the feature the authorized *action* names (briefing, status, reminders, dictation, etc.)."""

        def owns(feature: str) -> bool:
            return action in self._FEATURE_ACTIONS[feature]

        # Morning briefing
        from Agent_Guru.platform.features.briefing import get_morning_briefing, is_briefing_command
        if owns("briefing") and is_briefing_command(raw_text):
            from Agent_Guru.platform.features.user_memory import get_user_memory
            location = get_user_memory().get("location")
            # Today's reminders and, where connected, calendar and tasks:
            # the briefing used to promise reminders and say none.
            connectors = next((s.local for s in self._mcp_servers if s.name == "connectors"), None)
            try:
                pending = self._reminders().list_reminders()
            except Exception:
                pending = []
            return await get_morning_briefing(location=location, reminders=pending, connectors=connectors)

        # System status
        from Agent_Guru.platform.features.system_status import get_system_status, is_system_status_command
        if owns("system_status") and is_system_status_command(raw_text):
            return get_system_status(raw_text)

        # Reminder / Timer
        result = await self._handle_reminder(raw_text) if owns("reminder") else None
        if result is not None:
            return result

        # Voice dictation
        from Agent_Guru.platform.features.dictation import (
            extract_dictation_text, get_clipboard_action, get_clipboard_text,
            is_clipboard_command, is_dictation_command,
        )
        if owns("dictation") and is_dictation_command(raw_text):
            text_to_type = extract_dictation_text(raw_text)
            if text_to_type:
                ctrl = self.platform_controller
                fn = getattr(ctrl, "type_text", None) if ctrl else None
                if fn:
                    # "Typed: ..." was said whatever type_text returned.
                    typed = await asyncio.to_thread(fn, text_to_type)
                    return _outcome(f"Typed: {self._sanitize_output(text_to_type[:60])}", [_call_status(typed)])
                return ActionOutcome("Typing is not available on this platform.", ActionStatus.FAILED)

        # Clipboard read
        if owns("clipboard") and is_clipboard_command(raw_text):
            clip_text = get_clipboard_text()
            if not clip_text:
                return "Your clipboard is empty."
            clip_action = get_clipboard_action(raw_text)
            if clip_action == "read":
                return f"Your clipboard contains: {clip_text[:300]}"
            return None

        # Screen questions are answered here, by the vision model, and the
        # answer is what gets spoken. This used to return None ("the LLM
        # answers using screen context"), but screen_read intents skip the
        # LLM, so "describe my screen" was answered "Done." and nothing
        # visual could be answered from extracted text at all.
        from Agent_Guru.platform.features.screen_reader import (
            answer_screen_question, is_screen_read_command,
        )
        if owns("screen_read") and is_screen_read_command(raw_text):
            return await answer_screen_question(raw_text, self.platform_controller)

        # Presentation generation (e.g. "make a presentation from notes.txt"), which the intent
        # engine calls a conversation; never from the text of a device command.
        result = await self._handle_presentation_request(raw_text) if intent_type == "conversation" else None
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

        msg = reminder_params.get("message", "reminder")
        mins = reminder_params.get("minutes")
        secs = reminder_params.get("seconds")
        at_t = reminder_params.get("at_time")
        return await self._reminders().set_reminder(msg, minutes=mins, seconds=secs, at_time=at_t)

    def _reminders(self) -> Any:
        """The one ReminderManager, made on first use, speaking through the speech engine."""
        if self._reminder_mgr is None:
            from Agent_Guru.platform.features.reminders import ReminderManager
            self._reminder_mgr = ReminderManager(store_path=self._reminder_store)
            tts_eng = getattr(self.speech_engine, "tts_engine", None)
            if tts_eng:
                import sounddevice  # noqa: F401 - checks PortAudio is present before wiring the speaker
                def _speak_reminder(text: str) -> None:
                    try:
                        import numpy as np
                        audio, sr = tts_eng.synthesize_to_array(text)
                        tail = np.zeros(int(sr * 0.30), dtype=np.float32)
                        padded = np.concatenate([audio.astype(np.float32), tail])
                        # Under the PortAudio lock, like every other playback:
                        # a reminder fires on its own timer thread, possibly
                        # while the mic recovery path is running.
                        from Agent_Guru.speech.audio.portaudio_lock import play_and_wait

                        play_and_wait(padded, sr)
                    except Exception as _e:
                        logger.exception("Reminder TTS failed")
                self._reminder_mgr.set_speak_callback(_speak_reminder)
            # Checks and actions call tools the one way any tool is called,
            # so the policy is asked again at the moment each one runs.
            self._reminder_mgr.set_tool_runner(self._run_scheduled_tool)
            self._reminder_mgr.set_audit(self._audit_scheduled_run)
        return self._reminder_mgr

    async def _run_scheduled_tool(self, server: str, tool: str, arguments: dict[str, Any]) -> Any:
        """A scheduled check's or action's tool call, through MCPToolbox.call."""
        if self._toolbox is None:
            from Agent_Guru.integration.mcp_tools import ToolCallResult

            return ToolCallResult(server=server, tool=tool, status=ActionStatus.FAILED, category="unavailable",
                                  error="no tools are configured")
        return await self._toolbox.call(server, tool, arguments)

    def _audit_scheduled_run(self, task_id: str, status: str, details: dict[str, Any]) -> None:
        self._audit_logger.log_event(
            event_type=EventType.SCHEDULED_TASK_RUN, actor_id="scheduler", target_id=task_id,
            outcome=status, details=details,
        )
        self.events.publish("task.ran", task_id=task_id, status=status, **{k: v for k, v in details.items() if k != "arguments"})

    def close_scheduler(self) -> None:
        """Stop scheduled tasks and release the store's lock; called by main.py at shutdown."""
        if self._reminder_mgr is not None:
            self._reminder_mgr.close()

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
    ) -> ActionOutcome | str | None:
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

    #: How long an opened application gets to show up, and a closed one to
    #: go. Measured on Windows 11: Notepad's process appeared 0.46 s after
    #: the request, Calculator's 5.6 s (its first launch route fails and a
    #: second one is tried); closes finished within 0.1 s. Looks stop as
    #: soon as the expected state is seen.
    _APP_OPEN_VERIFY_S: ClassVar[float] = 10.0
    _APP_CLOSE_VERIFY_S: ClassVar[float] = 5.0
    _APP_POLL_S: ClassVar[float] = 0.1

    @staticmethod
    async def _app_instances(ctrl: Any, name: str) -> dict[int, bool] | None:
        """The application's running instances ({pid: shows a window}), or None if unknown."""
        fn = getattr(ctrl, "app_instances", None)
        if fn is None:
            return None
        found = await asyncio.to_thread(fn, name)
        return found if isinstance(found, dict) else None

    async def _action_open_app(self, ctrl: Any, param: str) -> ActionOutcome:
        """Open an application and report what is then running, not what the launcher said.

        open_application() reports that the launch was requested. On Windows
        11 "open paint" reported success and no Paint process ever appeared,
        so "Opening paint for you!" was said about nothing.
        """
        param = param.rstrip(".,!?;:")
        safe_param = self._sanitize_output(param)
        before = await self._app_instances(ctrl, param)
        if before:
            # Already running: launching again only adds a duplicate window.
            logger.info("ACTION: %s is already running (%d instance(s)); not launching", param, len(before))
            return ActionOutcome(f"{safe_param} is already open.", ActionStatus.SUCCESS)
        logger.info("ACTION: open_application('%s')", param)
        result = await asyncio.to_thread(ctrl.open_application, param)
        if _call_status(result) is not ActionStatus.SUCCESS:
            err = getattr(result, "error", "unknown error")
            logger.error("Failed to open '%s': %s", param, err)
            return ActionOutcome(
                f"Hmm, couldn't open {safe_param} - let me know if you wanna try something else",
                ActionStatus.FAILED,
            )
        unconfirmed = ActionOutcome(
            f"I started {safe_param}, but I couldn't confirm that it opened.", ActionStatus.UNVERIFIED,
        )
        if before is None:
            return unconfirmed
        deadline = asyncio.get_running_loop().time() + self._APP_OPEN_VERIFY_S
        while True:
            now = await self._app_instances(ctrl, param)
            if now:
                return ActionOutcome(f"Opening {safe_param} for you! What are we doing?", ActionStatus.SUCCESS)
            if asyncio.get_running_loop().time() >= deadline:
                logger.warning("'%s' was launched but no instance appeared in %.1fs", param, self._APP_OPEN_VERIFY_S)
                return unconfirmed
            await asyncio.sleep(self._APP_POLL_S)

    @staticmethod
    async def _app_awaiting_user(ctrl: Any, name: str) -> bool | None:
        """Whether the application waits for the user to answer it ("Save changes?"), or None if unknown."""
        fn = getattr(ctrl, "app_awaiting_user", None)
        if fn is None:
            return None
        found = await asyncio.to_thread(fn, name)
        return found if isinstance(found, bool) else None

    async def _action_close_app(self, ctrl: Any, param: str) -> ActionOutcome:
        """Ask an application to close and report what it then did.

        close_application() used to end the process with TerminateProcess:
        an editor holding unsaved text was gone in 0.03 s and never asked
        whether to save. It now asks the application's windows to close and
        returns once they have been asked, so the reply follows what is
        then seen. Closed means none of its processes shows a window any
        more; a helper left running in the background is not the
        application still being open (Windows 11 Notepad runs two).

        An application with unsaved work asks the user first. That is said,
        and nothing is answered or forced for them: not when the question
        is seen, not at the deadline, and not on cancellation. Measured on
        Windows 11: an empty Notepad's window was gone 0.02 to 0.05 s after
        the request, and the question appeared after 0.06 s.
        """
        param = param.rstrip(".,!?;:")
        safe_param = self._sanitize_output(param)
        before = await self._app_instances(ctrl, param)
        if before == {}:
            return ActionOutcome(f"{safe_param} isn't open.", ActionStatus.SUCCESS)
        if before and not any(before.values()):
            # Closing used to kill such a process. With no window there is
            # nothing to ask, and it is not killed instead.
            return ActionOutcome(
                f"{safe_param} is running without a window I can ask to close, so I left it running.",
                ActionStatus.FAILED,
            )
        logger.info("ACTION: close_application('%s')", param)
        loop = asyncio.get_running_loop()
        asked_at = loop.time()
        result = await asyncio.to_thread(ctrl.close_application, param)
        # success defaulted to True here, so a result without one said "Closed".
        if _call_status(result) is not ActionStatus.SUCCESS:
            return ActionOutcome(f"Failed to close {safe_param}", ActionStatus.FAILED)
        logger.info("Asked '%s' to close in %.3fs", param, loop.time() - asked_at)
        unconfirmed = ActionOutcome(
            f"I asked {safe_param} to close, but I couldn't confirm that it closed.", ActionStatus.UNVERIFIED,
        )
        if before is None:
            return unconfirmed
        waiting = ActionOutcome(
            f"I asked {safe_param} to close, but it's waiting for you to confirm, maybe whether to save your work.",
            ActionStatus.UNVERIFIED,
        )
        watched = {pid for pid, shows in before.items() if shows}
        deadline = loop.time() + self._APP_CLOSE_VERIFY_S

        async def look(read: Any) -> Any:
            # A look that hangs must not hold the turn past the deadline.
            try:
                return await asyncio.wait_for(read(ctrl, param), max(deadline - loop.time(), 0) + self._APP_POLL_S)
            except TimeoutError:
                return None

        last: dict[int, bool] | None = None
        one_went_at: float | None = None
        try:
            while True:
                now = await look(self._app_instances)
                if now is not None:
                    last = now
                    remaining = {pid for pid, shows in now.items() if shows}
                    if not remaining:
                        logger.info("'%s' closed %.3fs after it was asked", param, loop.time() - asked_at)
                        return ActionOutcome(f"Closed {safe_param}", ActionStatus.SUCCESS)
                    if watched - remaining:
                        # One instance is asked to close. With several open,
                        # its window going while the rest stay for a second
                        # means one was closed, and that is what is said.
                        one_went_at = one_went_at if one_went_at is not None else loop.time()
                        if loop.time() - one_went_at >= 1.0:
                            return ActionOutcome(
                                f"Closed one {safe_param} window; {len(remaining)} more still open.",
                                ActionStatus.SUCCESS,
                            )
                    elif await look(self._app_awaiting_user):
                        logger.info("'%s' is waiting for the user %.3fs after it was asked", param,
                                    loop.time() - asked_at)
                        return waiting
                if loop.time() >= deadline:
                    if last is None:
                        return unconfirmed
                    still = {pid for pid, shows in last.items() if shows}
                    if watched - still:
                        return ActionOutcome(
                            f"Closed one {safe_param} window; {len(still)} more still open.", ActionStatus.SUCCESS,
                        )
                    # Not forced: why it stayed open is not known, and
                    # killing it could lose what the user has open.
                    logger.warning("'%s' is still open %.1fs after it was asked to close", param,
                                   self._APP_CLOSE_VERIFY_S)
                    return ActionOutcome(f"I asked {safe_param} to close, but it's still open.",
                                         ActionStatus.UNVERIFIED)
                await asyncio.sleep(self._APP_POLL_S)
        except asyncio.CancelledError:
            # The cancellation goes on to whoever cancelled the turn; the
            # application keeps whatever it was asked, and is not forced.
            logger.info("Close of '%s' %s after it was asked; nothing forced", param, ActionStatus.CANCELLED.value)
            raise

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

    #: The status of each send outcome the messaging controller reports. Only
    #: "sent" is a success: "pending" and "unverified" went out without a
    #: confirmation, the rest did not go (the reply says what to do).
    _MESSAGE_STATUS: ClassVar[dict[str | None, ActionStatus]] = {
        "sent": ActionStatus.SUCCESS,
        "pending": ActionStatus.UNVERIFIED,
        "unverified": ActionStatus.UNVERIFIED,
        "not_sent": ActionStatus.FAILED,
        "draft": ActionStatus.FAILED,
        "prefilled": ActionStatus.FAILED,
        None: ActionStatus.FAILED,
    }

    async def _deliver_message(self, ctrl: Any, app: str, contact: str, message: str) -> ActionOutcome:
        """Send through the platform controller and say what happened."""
        outcome = await ctrl.send_message(app, contact, message)
        status = self._MESSAGE_STATUS.get(outcome, ActionStatus.UNVERIFIED)
        return ActionOutcome(self._message_reply(app, contact, outcome), status)

    def _message_reply(self, app: str, contact: str, outcome: str | None) -> str:
        """The reply for a send outcome."""
        label = {"whatsapp": "WhatsApp", "telegram": "Telegram", "slack": "Slack",
                 "sms": "SMS", "email": "email"}[app]
        who = self._sanitize_output(contact)
        # What the app shows after the send (messaging_controller,
        # _send_in_whatsapp_desktop), not just that send was pressed. Every
        # outcome but "sent" said "ready, press send", which was wrong both
        # ways: a message that had gone was reported as waiting, and in a box
        # that also held an old draft "press send" would send the draft too.
        if outcome == "sent":
            return f"Sent your message to {who} on {label}."
        if outcome == "pending":
            return f"I sent your message to {who}, but {label} hasn't confirmed it has gone yet."
        if outcome == "not_sent":
            return (
                f"I pressed send, but your message to {who} is still in {label}'s message box, "
                "so it didn't go. It's there for you to send."
            )
        if outcome == "unverified":
            return f"I pressed send, but I couldn't check that it went. Please look at your chat with {who}."
        if outcome == "draft":
            return (
                f"The chat with {who} already had unsent text in it, so I didn't send anything. "
                "Your message is in the box after that text."
            )
        if outcome:
            return f"Your message to {who} is ready in {label}. Press send to deliver it."
        return (
            f"I couldn't send that to {who} on {label}. If {who} isn't a saved "
            "contact, say their number or address instead."
        )

    def _start_message_draft(self, app: str, contact: str, message: str) -> str:
        """Keep a message that lacks its recipient or text, and ask for it."""
        self._message_draft = {
            "app": app, "contact": contact, "message": message,
            "expires": time.monotonic() + MESSAGE_DRAFT_TTL_S,
        }
        return self._message_draft_question()

    def _message_draft_question(self) -> str:
        draft = self._message_draft
        assert draft is not None  # nosec B101 - only called with a draft
        if not draft["contact"]:
            return "Who should I send it to?"
        who = self._sanitize_output(draft["contact"])
        if not draft["message"]:
            return f"What would you like me to send {who}?"
        return f"Your message to {who} says: {draft['message']}. Send it?"

    async def _continue_message_draft(self, transcript: str) -> ActionOutcome | None:
        """Take this utterance as the answer to a message draft's question.

        Returns the reply, or None when there is no live draft and the
        utterance is an ordinary command. The recipient and the text are
        asked for in turn, then the whole message is read back, and only a
        yes sends it: the answer to "what would you like me to send?" can be
        any sentence, so the user hears exactly what will go before it goes.
        Anything but a yes to the read-back cancels it.
        """
        draft = self._message_draft
        if draft is None:
            return None
        if time.monotonic() > draft["expires"]:
            self._message_draft = None
            logger.info("Message draft to %r expired unanswered", draft["contact"])
            return None
        said = transcript.strip()

        if not draft["contact"] or not draft["message"]:
            if said.lower().strip(" .,!?") in _DRAFT_CANCEL:
                self._message_draft = None
                return ActionOutcome("Okay, I won't send anything.", ActionStatus.CANCELLED)
            if not draft["contact"]:
                from Agent_Guru.platform.intent_recognizer import _RECIPIENT, _SEVERAL_RECIPIENTS

                contact = re.sub(r"^(?:to|for)\s+", "", said.strip(" .,!?"), flags=re.IGNORECASE)
                if not re.fullmatch(_RECIPIENT, contact) or _SEVERAL_RECIPIENTS.search(contact):
                    # The same test the message parser applies: one name,
                    # number or address, or the message could go astray.
                    draft["expires"] = time.monotonic() + MESSAGE_DRAFT_TTL_S
                    return ActionOutcome("Sorry, who should I send it to? Say one name or number.", None)
                draft["contact"] = contact
            else:
                draft["message"] = said
            draft["expires"] = time.monotonic() + MESSAGE_DRAFT_TTL_S
            return ActionOutcome(self._message_draft_question(), None)

        self._message_draft = None
        from Agent_Guru.platform.features.confirmation import _parse_confirmation

        if _parse_confirmation(said) is not True:
            return ActionOutcome("Okay, I didn't send it.", ActionStatus.CANCELLED)
        intent = f"communication:send_message:{draft['contact']}:{draft['app']}:{draft['message']}"
        try:
            allowed = await asyncio.wait_for(self._stage_policy(intent), timeout=POLICY_TIMEOUT_S)
        except TimeoutError:
            allowed = False  # fail closed, as stage 6 does
        if not allowed:
            return ActionOutcome("Sorry, I'm not allowed to send that message.", ActionStatus.DENIED)
        return await self._deliver_message(self.platform_controller, draft["app"], draft["contact"], draft["message"])

    async def _action_communication(
        self, ctrl: Any, action: str, param: str, level_str: str,
    ) -> ActionOutcome | str | None:
        if action in ("send_message", "reply"):
            import html

            # level_str is "<app>:<text>" for a dictated message. The text
            # used to be dropped before this point, so the assistant could
            # only open the app. The intent was HTML-escaped by
            # _sanitize_output, so the text is unescaped: "it's" must not be
            # sent as "it&#x27;s".
            contact = html.unescape(param).strip()
            app, _, message = level_str.partition(":")
            app = app.strip().lower() or "whatsapp"
            message = html.unescape(message).strip()
            if app not in ("whatsapp", "telegram", "slack", "sms", "email"):
                app = "whatsapp"
            send = getattr(ctrl, "send_message", None)
            if send is not None and (not contact or not message) and (contact or message or ":" in level_str):
                # Missing the recipient or the text: ask, and keep what was
                # said. A recipient alone used to open the app with nothing
                # in it, and a question asked was forgotten by the next turn.
                return ActionOutcome(self._start_message_draft(app, contact, message), None)
            if not contact and (message or ":" in level_str):
                return ActionOutcome("Who should I send it to?", None)
            if message and send is not None:
                return await self._deliver_message(ctrl, app, contact, message)
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

    # ------------------------------------------------------------------
    # Tools on MCP servers (integration/tool_loop.py)
    # ------------------------------------------------------------------

    def _start_tools(self) -> None:
        """Start the configured MCP servers in the background, if any are configured and none is starting.

        In the background so the turn that first needs a tool does not wait
        for a server to start (3.1 s for the official test server through
        npx), and so a server that fails to start only takes its own tools
        away.
        """
        if not self._mcp_servers or (self._tools_starting is not None and not self._tools_starting.done()):
            return
        if self._toolbox is None:
            from Agent_Guru.integration.mcp_tools import MCPToolbox

            self._toolbox = MCPToolbox(
                self._mcp_servers, policy_check=self._stage_policy, audit_logger=self._audit_logger,
            )
        self._tools_starting = asyncio.create_task(self._discover_and_warm(), name="mcp-start")

    async def _discover_and_warm(self) -> Any:
        """Discover the tools, then queue the injection classifier on their descriptions (see tool_loop)."""
        if self._toolbox is None:
            return []
        tools = await self._toolbox.discover()
        try:
            from Agent_Guru.integration.tool_loop import warm_tool_descriptions

            warm_tool_descriptions(tools)
        except Exception:
            logger.debug("Could not queue tool descriptions for the injection classifier", exc_info=True)
        return tools

    async def close_tools(self) -> None:
        """End every MCP server this assistant started; called by main.py at shutdown."""
        if self._tools_starting is not None and not self._tools_starting.done():
            self._tools_starting.cancel()
            with contextlib.suppress(BaseException):
                await self._tools_starting
        if self._toolbox is not None:
            await self._toolbox.close()

    async def _answer_with_tools(self, result: PipelineResult, pipeline_mode: str) -> tuple[bool, Any]:
        """Answer this turn through the tool loop; (False, None) when no tool is offered.

        Offered only to the verified owner, for conversation and questions
        (a command has its own handler), with a model Ollama reports as
        taking tools, and only the tools that could run right now. Anything
        else answers as before, unchanged.
        """
        if self._toolbox is None or pipeline_mode != "full":
            return False, None
        if (result.intent or "").split(":", 1)[0] not in {"", "conversation", "information"}:
            return False, None
        llm = self.llm_runtime
        supports = getattr(llm, "supports_tool_calling", None)
        if supports is None or getattr(llm, "complete", None) is None or getattr(llm, "infer", None) is not None:
            return False, None
        if not await supports(_configured_ollama_model()):
            return False, None
        tools = await self._toolbox.available_now()
        if not tools:
            self._start_tools()  # a server that stopped is started again for a later turn
            return False, None
        # A question the intent rules say needs live data (an office holder,
        # a price, the news) is researched before the model's first step:
        # gemma4 offered the research tools answered "who is the current
        # prime minister" from memory in every run, without a source. The
        # search runs through the loop like a call the model made.
        from Agent_Guru.llm.models import ToolCall

        research_call = ToolCall(name="guru__web_research", arguments={"query": (result.transcript or "")[:300]})
        prefetch = self._intent_needs_web(result.intent, result.transcript or "") and any(
            f"{t.server}__{t.name}" == research_call.name for t in tools
        )
        built = await self._build_llm_request(
            result.transcript or "", result.memory_context, result.detected_language,
            result.personality, result.intent, web_context=not prefetch,
        )
        if built is None:
            return False, None
        request, _ = built
        # Read from the module at call time, so an evaluation can try
        # another guidance or temperature without a restart.
        from Agent_Guru.integration import tool_loop

        request = dataclasses.replace(request, temperature=tool_loop.TOOL_TEMPERATURE)
        # The owner's next words answer a "Should I ...?" (_continue_tool_confirmation), so this loop
        # can ask; only the verified owner reaches it (pipeline_mode "full").
        loop = tool_loop.ToolLoop(self._toolbox, tools, stages=result.tool_stages, can_ask_owner=True)
        messages = list(request.messages)
        messages[0] = dataclasses.replace(messages[0], content=f"{messages[0].content}\n\n{tool_loop.TOOL_GUIDANCE}")
        self._fit_tool_prompt(messages, loop)
        return await self._run_tool_loop(result, request, loop, messages, None, prefetch=research_call if prefetch else None)

    def _fit_tool_prompt(self, messages: list[Any], loop: ToolLoop) -> None:
        """Drop the oldest history until the prompt, the tools and their output fit the context window.

        A spoken prompt holds up to 2,900 tokens of history; with tool
        definitions and up to 1,500 tokens of tool output it could pass the
        6,144-token window, and Ollama then drops the start of the prompt,
        which is the system prompt.
        """
        import json as _json

        from Agent_Guru.reasoning.llm.generation import context_window, spoken_reply_tokens

        tool_tokens = len(_json.dumps([dataclasses.asdict(f) for f in loop.functions()])) // 4
        reserve = tool_tokens + loop.budget.max_output_chars // 4 + spoken_reply_tokens() + 300
        while len(messages) > 2 and sum(len(m.content) for m in messages) // 4 + reserve > context_window():
            messages.pop(1)

    async def _run_tool_loop(
        self, result: PipelineResult, request: Any, loop: ToolLoop, messages: list[Any], pending: Any,
        *, prefetch: Any = None,
    ) -> tuple[bool, Any]:
        """Run (or, with *pending*, resume) the tool loop and put its answer in *result*."""
        from Agent_Guru.integration import research

        spoken: list[Any] = []
        step = self._tool_model_step(result, request, spoken, loop)
        register, token = research.begin_turn()
        try:
            if prefetch is not None:
                await loop.prefetch(messages, prefetch)
            if pending is None:
                outcome = await loop.run(messages, step)
            else:
                outcome = await loop.resume(pending, messages, step)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Tool loop failed")
            outcome = loop.outcome
            outcome.stop_reason = "error"
            outcome.answer = "Sorry, I couldn't finish that."
        finally:
            research.end_turn(token)
        checked = None
        if register.sources and outcome.model_answer and outcome.answer:
            # Held to what the turn's tools actually returned: unknown ids
            # and URLs removed, unmatched numbers noted, sources listed.
            checked = research.check_answer(outcome.answer, register)
            outcome.answer = checked.text if not spoken else checked.spoken
            result.sources = [
                {"id": s.id, "kind": s.kind, "title": s.title, "url": s.url, "read": s.read} for s in checked.cited
            ]
            if checked.unknown_ids or checked.removed_urls or checked.unmatched:
                logger.warning(
                    "Answer held to its sources: unknown ids %s, URLs removed %s, unmatched sentences %d",
                    checked.unknown_ids, checked.removed_urls, len(checked.unmatched),
                )
                loop.note_check(checked)
        if outcome.pending is not None:
            self._tool_pending = {
                "pending": outcome.pending, "loop": loop, "messages": messages, "request": request,
                "expires": time.monotonic() + MESSAGE_DRAFT_TTL_S,
            }
            result.awaiting_reply = True
        if outcome.calls:
            result.action_status = outcome.status
        answer = (outcome.answer or "").strip()
        extra = " ".join(outcome.notes)
        if outcome.pending is not None or not spoken:
            # Nothing was spoken while it was written (a typed turn, the
            # confirmation question, or text that never streamed): the
            # whole reply is said by the TTS stage.
            if not answer and not extra and not outcome.calls:
                return False, None
            result.llm_response = " ".join(t for t in (answer, extra) if t) or _STATUS_REPLIES[result.action_status]
            return True, None
        if not answer and not outcome.calls:
            # Nothing written and nothing run (a step that wrote only
            # thinking, say): the usual answer path answers instead of a
            # status sentence that would not fit a question.
            return False, None
        result.llm_response = " ".join(t for t in (answer, extra) if t)
        tts = spoken[-1]
        # What the model did not say itself as it wrote: the loop's own
        # answer (NOT_DONE, an error), the notes on unconfirmed changes, and
        # the sources check's note when a detail did not match.
        mismatch = " I couldn't match every detail of that to my sources." if checked and checked.unmatched else ""
        unsaid = " ".join(t for t in ("" if outcome.model_answer else answer, extra + mismatch) if t)
        if unsaid:
            tts = await self._stage_tts(unsaid, result.personality) or tts
        return True, tts

    def _tool_model_step(self, result: PipelineResult, request: Any, spoken: list[Any], loop: ToolLoop) -> Any:
        """One model step for the tool loop: spoken as it is written on a voice turn, collected on a typed one.

        Spoken sentence by sentence, each checked first: a sentence saying
        something was done while no tool has changed anything this turn is
        not spoken (the loop then corrects the model), and the rest of the
        step is read but not spoken, so its tool calls are still seen.
        """
        from Agent_Guru.integration.research import strip_citations
        from Agent_Guru.integration.tool_loop import ModelStep
        from Agent_Guru.speech.tts.streaming import stream_sentences

        llm = self.llm_runtime

        async def step(messages: list[Any], functions: list[Any] | None) -> ModelStep:
            ask = dataclasses.replace(request, messages=list(messages), functions=functions)
            tts_fn = self._streamable_tts_fn()
            if tts_fn is None or getattr(llm, "stream", None) is None:
                response = await asyncio.wait_for(llm.complete(ask), timeout=LLM_TIMEOUT_S)
                return ModelStep(text=response.content or "", tool_calls=list(response.tool_calls or []))
            calls: list[Any] = []
            parts: list[str] = []
            withheld = False

            async def chunks() -> Any:
                async for chunk in llm.stream(ask):
                    if chunk.tool_calls:
                        calls.extend(chunk.tool_calls)
                    if chunk.content:
                        parts.append(chunk.content)
                        yield chunk.content

            async def checked() -> Any:
                nonlocal withheld
                async for sentence in stream_sentences(chunks()):
                    if withheld or loop.claims_unbacked(sentence):
                        withheld = True
                        continue
                    # Source ids and URLs are for the screen, not for speech.
                    said = strip_citations(sentence).strip()
                    if said:
                        yield said + " "

            played = await self._speak_streaming(tts_fn, checked(), result.personality, text_timeout_s=LLM_TIMEOUT_S)
            if getattr(played, "spoken", 0):
                spoken.append(played)
            return ModelStep(text="".join(parts), tool_calls=calls, withheld=withheld)

        return step

    async def _continue_tool_confirmation(self, result: PipelineResult, pipeline_mode: str) -> bool:
        """Take this turn as the owner's answer to "Should I run ...?"; True when it was.

        Only the owner's own next words confirm: a yes runs exactly the call
        that was read back, through the same checks as any call, and the
        loop goes on with the budget it had. Anything else cancels it, as a
        message draft is cancelled, and nothing runs. A restricted speaker
        cannot confirm.
        """
        waiting = self._tool_pending
        if waiting is None:
            return False
        self._tool_pending = None
        if time.monotonic() > waiting["expires"]:
            logger.info("Tool confirmation for %s expired unanswered", waiting["pending"].name)
            return False
        from Agent_Guru.platform.features.confirmation import _parse_confirmation

        pending = waiting["pending"]
        result.intent = "external:tool_confirmation"
        if pipeline_mode != "full" or _parse_confirmation(result.transcript or "") is not True:
            reply = f"Okay, I won't run {pending.tool}."
            result.action_result, result.action_status = reply, ActionStatus.CANCELLED
        else:
            loop = waiting["loop"]
            loop.record_into(result.tool_stages)  # this turn's record, not the asking turn's
            _, tts = await self._run_tool_loop(result, waiting["request"], loop, waiting["messages"], pending)
            if tts is not None:
                result.tts_response = tts
                result.stages_completed = 8
                self._chat_history.append({"role": "user", "content": result.transcript or "", "emotion": "neutral"})
                self._chat_history.append({"role": "assistant", "content": result.llm_response or ""})
                return True
        result.stages_completed = 8
        reply = result.action_result or result.llm_response or ""
        self._chat_history.append({"role": "user", "content": result.transcript or "", "emotion": "neutral"})
        self._chat_history.append({"role": "assistant", "content": reply})
        with _timed(result, "tts"):
            result.tts_response = await self._stage_tts(reply, result.personality)
        return True

    async def _stage_tts(self, text: str, personality: Personality) -> Any:
        """Stage 8: speak the reply, streamed sentence by sentence when possible.

        This used to synthesise the whole reply and then play it, inside one
        30 s budget. Kokoro on the development laptop's CPU is at or slower
        than real time (17.3 s to synthesise a 211-character reply in "Best
        power efficiency"), so the user heard nothing until all of it was
        ready, and a reply over about 200 characters overran the budget and
        was logged as no audio. Now the first sentence plays as soon as it is
        synthesised and the rest are synthesised while it plays
        (speech/tts/streaming.py). TTS_TIMEOUT_S bounds each wait for
        synthesis, the silence the user hears, not the length of the reply.

        Streaming needs a synchronous synthesiser that returns an array, which
        Kokoro's is. Anything else, or a first sentence that cannot be
        synthesised, takes the whole-reply path below, bounded as before.
        Returns the StreamResult when streamed.
        """
        if not text or not text.strip():
            return text
        if _TEXT_TURN.get():
            return None  # a typed turn is answered in writing
        stream_fn = self._streamable_tts_fn()
        if stream_fn is not None:
            try:
                return await self._speak_streaming(stream_fn, text, personality)
            except ImportError:
                pass  # no sounddevice: the whole-reply path's pyttsx3 fallback speaks
            except Exception:
                logger.exception(
                    "Streamed TTS could not synthesise the first sentence - "
                    "trying whole-reply synthesis",
                )
        return await asyncio.wait_for(
            self._stage_tts_whole(text, personality), timeout=TTS_TIMEOUT_S,
        )

    def _streamable_tts_fn(self) -> Any:
        """The array-returning synchronous synthesiser, or None if there is none (or the turn is typed)."""
        if _TEXT_TURN.get():
            return None
        fn = self._tts_fn if self._tts_fn_type == "array" else None
        if fn is None and self._tts_fn is None:
            tts_eng = getattr(self.speech_engine, "tts_engine", None)
            fn = getattr(self.speech_engine, "synthesize_to_array", None) or (
                tts_eng and getattr(tts_eng, "synthesize_to_array", None)
            )
        if fn is None or inspect.iscoroutinefunction(fn):
            return None
        return fn

    async def _speak_streaming(
        self, fn: Any, text: Any, personality: Personality, *,
        capped: Any = None, text_timeout_s: float | None = None,
    ) -> Any:
        """Stream text (a string, or chunks as they are generated) through fn under the PortAudio lock."""
        import numpy as np
        import sounddevice  # noqa: F401 - its ImportError selects the pyttsx3 fallback

        from Agent_Guru.speech.audio.portaudio_lock import play_and_wait
        from Agent_Guru.speech.tts.streaming import speak_streaming

        try:
            from Agent_Guru.speech.models import PersonalityType

            pt: Any = PersonalityType.MAYA if personality == Personality.MAYA else PersonalityType.GURU
        except ImportError:
            pt = personality

        def synthesize(sentence: str) -> tuple[Any, int]:
            out = fn(sentence, pt)
            audio, rate = out if isinstance(out, tuple) and len(out) == 2 else (out, 22050)
            return np.asarray(audio, dtype=np.float32), int(rate)

        result = await speak_streaming(
            text, synthesize, play_and_wait, synth_timeout_s=TTS_TIMEOUT_S,
            text_timeout_s=text_timeout_s, capped=capped or (lambda: False),
        )
        logger.info(
            "TTS played: %.1fs of audio in %d/%d sentences, first audio after %.2fs",
            result.audio_seconds, result.spoken, result.sentences, result.first_audio_s or 0.0,
        )
        return result

    async def _stage_tts_whole(self, text: str, personality: Personality) -> Any:
        """Synthesise the whole reply, then play it: the path before streaming.

        Converts the orchestrator's Personality enum to the speech engine's
        PersonalityType enum before calling synthesis methods.
        """
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
                    import sounddevice  # noqa: F401 - its ImportError selects the pyttsx3 fallback below

                    def _play() -> None:
                        import numpy as np

                        # Pad with 300ms silence to prevent last-word cutoff
                        tail = np.zeros(int(sample_rate * 0.30), dtype=np.float32)
                        padded = np.concatenate([audio_array.astype(np.float32), tail])
                        # Under the process-wide PortAudio lock. The mic
                        # recovery path used to re-initialise PortAudio on the
                        # listen thread mid-answer: the answer stopped while
                        # sd.wait() reported success, and repeated, the
                        # process died. The `import sounddevice` above stays:
                        # its ImportError is what selects the pyttsx3 fallback.
                        from Agent_Guru.speech.audio.portaudio_lock import play_and_wait

                        play_and_wait(padded, sample_rate)

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
                            # Under the playback lock like every other reply,
                            # because the filler now plays while the turn is
                            # worked on: without it this fallback voice could
                            # speak over a filler that has not finished.
                            from Agent_Guru.speech.audio.portaudio_lock import portaudio_in_use

                            with portaudio_in_use():
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
        steps = _intent_steps(intent)
        if len(steps) > 1:
            return any(IntegrationOrchestrator._intent_needs_llm(step, transcript) for step in steps)

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
