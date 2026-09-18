"""Multi-platform main application loop for Agent Guru.

Wires together all subsystems into an always-on background service:
  wake word → STT → intent → action/LLM → TTS → playback

Platform support:
  - Desktop (Windows/macOS/Linux): Background service, auto-start on boot
  - Android: Foreground service with notification
  - iOS: Background audio + VoIP modes

Sleep/wake cycle:
  - IDLE: Low-power wake word detection only
  - ACTIVE: Full pipeline processing
  - Returns to IDLE after each response

Performance targets:
  - End-to-end latency: <4s (95th percentile)
  - Battery (mobile sleep): <5%/hour
  - Battery (mobile active): <10%/hour
"""

from __future__ import annotations

import logging
import platform
import signal
import threading
import time
from typing import TYPE_CHECKING, Any

from Agent_Guru.core.voice_pipeline import PipelineState, VoicePipeline

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_PLATFORM = platform.system().lower()

# Service-loop timings. Module-level rather than function-local so they can be
# tuned per deployment and driven directly by tests -- with them buried inside
# _service_loop() the 60s housekeeping interval made the loop's error handling
# untestable without waiting a real minute.
IDLE_POLL_S = 0.5  # low-power poll while waiting for a wake word
ACTIVE_POLL_S = 0.05  # fast poll during active processing
HOUSEKEEP_S = 60.0  # how often to log housekeeping stats


class AgentGuru:
    """Main Agent Guru application.

    Coordinates all subsystems through the VoicePipeline state machine.
    Designed to run as a background service on all platforms.

    Example:
        >>> app = AgentGuru()
        >>> app.initialize()
        >>> app.run_as_background_service()  # blocks until stopped
        >>> # Or stop programmatically:
        >>> app.shutdown()

    State machine (delegated to VoicePipeline):
        IDLE → LISTENING → PROCESSING → RESPONDING → IDLE

    Performance:
        - State transitions: O(1)
        - End-to-end latency: <4s target

    """

    def __init__(
        self,
        personality: str = "guru",
        enable_auth: bool = True,
        enable_policy: bool = True,
    ) -> None:
        """Initialize AgentGuru.

        Args:
            personality: Active personality ("guru" or "maya").
            enable_auth: Enable biometric authentication.
            enable_policy: Enable policy/permission checks.

        """
        self.personality = personality
        self.enable_auth = enable_auth
        self.enable_policy = enable_policy

        self._pipeline = VoicePipeline()
        self._initialized = False
        self._running = False
        self._stop_event = threading.Event()

        # Optional subsystem references (lazy-loaded)
        self._auth_manager: Any | None = None
        self._policy_manager: Any | None = None
        self._memory_manager: Any | None = None

        # Callbacks for platform-specific integrations
        self._on_wake: Callable[[str], None] | None = None
        self._on_response: Callable[[str], None] | None = None
        self._on_error: Callable[[str], None] | None = None

        # BUG-008: wake word listener thread (optional — registered by caller)
        # When set, _service_loop() starts this in a daemon thread so it runs
        # concurrently with the housekeeping loop.
        self._wake_word_listener: Callable[[], None] | None = None
        self._wake_thread: threading.Thread | None = None

        # Signal handlers this instance installed, so they can be put back.
        # Installing handlers is process-global: an app that embeds AgentGuru
        # had its own SIGINT/SIGTERM handling silently and permanently
        # replaced by ours the first time run_as_background_service() ran.
        self._prev_signal_handlers: dict[int, Any] = {}
        #: Signal number that requested shutdown, logged once we are off the
        #: signal handler's stack (logging there is not re-entrancy-safe).
        self._pending_signal: int | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize all subsystems.

        Loads managers lazily to avoid import errors on platforms
        where optional dependencies are not installed.
        """
        logger.info(
            "Initializing AgentGuru (platform=%s, personality=%s)",
            _PLATFORM,
            self.personality,
        )

        if self.enable_auth:
            self._init_auth()

        if self.enable_policy:
            self._init_policy()

        self._init_memory()

        # Wire pipeline state change logging
        self._pipeline.on_state_change(self._on_state_change)

        self._initialized = True
        logger.info("AgentGuru initialized successfully")

    def run_as_background_service(self) -> None:
        """Run as an always-on background service.

        Blocks until shutdown() is called or SIGTERM/SIGINT received.
        Registers signal handlers for graceful shutdown on desktop.
        """
        self._ensure_initialized()
        self._running = True
        self._stop_event.clear()

        self._install_signal_handlers()

        logger.info("AgentGuru background service started")

        try:
            self._service_loop()
        finally:
            self._restore_signal_handlers()
            # The loop can also end because the pipeline reached STOPPED (an
            # "exit"/"goodbye" utterance, or the consecutive-error cap). In
            # that case nothing had set the stop event, so a registered
            # wake-word listener -- documented to loop until it is set -- kept
            # listening after the user had said goodbye. Settle it here so
            # every exit path shuts the whole service down.
            self._stop_event.set()
            self._running = False
            logger.info("AgentGuru background service stopped")

    def _install_signal_handlers(self) -> None:
        """Install SIGTERM/SIGINT handlers, if this is the main thread.

        signal.signal() raises ValueError anywhere but the main thread, which
        would have taken down a perfectly serviceable call to
        run_as_background_service() from a worker thread. Python only delivers
        signals to the main thread anyway, so skipping is the correct
        behaviour there, not a degradation worth failing over.
        """
        if _PLATFORM not in ("windows", "darwin", "linux"):
            return
        if threading.current_thread() is not threading.main_thread():
            logger.info(
                "Not the main thread - skipping signal-handler registration "
                "(signals are delivered to the main thread only). Call "
                "shutdown() to stop the service.",
            )
            return
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                self._prev_signal_handlers[sig] = signal.signal(sig, self._handle_signal)
            except (ValueError, OSError):
                logger.warning("Could not install handler for signal %s", sig, exc_info=True)

    def _restore_signal_handlers(self) -> None:
        """Put back whatever handlers were installed before us."""
        while self._prev_signal_handlers:
            sig, handler = self._prev_signal_handlers.popitem()
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError, TypeError):
                logger.debug("Could not restore handler for signal %s", sig, exc_info=True)

    def shutdown(self) -> None:
        """Gracefully shut down the service."""
        logger.info("AgentGuru shutdown requested")
        self._stop_event.set()
        self._pipeline.stop()
        self._running = False

    # ------------------------------------------------------------------
    # Pipeline event handlers (called by platform-specific integrations)
    # ------------------------------------------------------------------

    def on_wake_word(self, personality: str = "guru") -> None:
        """Called when wake word is detected.

        Args:
            personality: Detected personality ("guru" or "maya").

        """
        self.personality = personality
        logger.info("Wake word detected: %s", personality)
        self._pipeline.wake_word_detected()
        if self._on_wake:
            self._on_wake(personality)

    def on_speech_captured(self, transcript: str) -> None:
        """Called when STT produces a transcript.

        Args:
            transcript: Transcribed speech text.

        """
        logger.info("Speech captured: %r", transcript[:80])
        self._pipeline.speech_captured(transcript)

    def on_response_ready(self, response: str) -> None:
        """Called when LLM/action produces a response.

        Args:
            response: Response text for TTS.

        """
        logger.info("Response ready: %r", response[:80])
        self._pipeline.response_ready(response)
        if self._on_response:
            self._on_response(response)

    def on_playback_complete(self) -> None:
        """Called when TTS playback finishes. Returns pipeline to IDLE."""
        self._pipeline.playback_complete()

    def on_error(self, error: str) -> None:
        """Called on any subsystem error.

        Args:
            error: Error description.

        """
        logger.error("Pipeline error: %s", error)
        self._pipeline.report_error(error)
        if self._on_error:
            self._on_error(error)

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def on_wake_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback invoked when wake word is detected."""
        self._on_wake = callback

    def on_response_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback invoked when response is ready for TTS."""
        self._on_response = callback

    def on_error_callback(self, callback: Callable[[str], None]) -> None:
        """Register callback invoked on errors."""
        self._on_error = callback

    def register_wake_word_listener(self, listener: Callable[[], None]) -> None:
        """Register a synchronous wake-word listener.

        The listener is a blocking callable that waits for a wake word and
        calls ``self.on_wake_word()`` when detected.  It should loop forever
        until ``self._stop_event.is_set()``.

        ``_service_loop()`` starts this listener in a daemon thread so it
        runs concurrently with pipeline housekeeping.

        BUG-008 fix: without this, the sync service loop never triggered
        any detection — the pipeline stayed in IDLE indefinitely.
        """
        self._wake_word_listener = listener

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    @property
    def state(self) -> PipelineState:
        """Current pipeline state."""
        return self._pipeline.get_state()

    @property
    def is_running(self) -> bool:
        """True if background service is running."""
        return self._running

    @property
    def is_idle(self) -> bool:
        """True if pipeline is in IDLE (low-power) state."""
        return self._pipeline.is_idle()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _service_loop(self) -> None:
        """Main service loop — runs until stop event is set.

        BUG-008 fix: the old implementation was a plain ``time.sleep(0.1)``
        busy-wait that never drove any detection.  The pipeline started in
        IDLE and nothing ever transitioned it.

        Now:
        1. If a wake-word listener was registered via ``register_wake_word_listener()``,
           it is started in a background daemon thread.  The listener is
           responsible for calling ``self.on_wake_word()`` when triggered.
        2. The main loop handles periodic housekeeping (memory/state logging)
           using a longer poll interval when IDLE to spare the CPU.
        3. A clear warning is emitted if no listener is registered, so
           developers know the sync path needs the listener wired up.
        """
        # --- Start wake-word listener thread if registered ---
        if self._wake_word_listener is not None:
            self._wake_thread = threading.Thread(
                target=self._wake_word_listener,
                daemon=True,
                name="guru-wake-word",
            )
            self._wake_thread.start()
            logger.info("Wake-word listener thread started: %s", self._wake_thread.name)
        else:
            logger.warning(
                "_service_loop: no wake-word listener registered. "
                "Call register_wake_word_listener() before run_as_background_service() "
                "or use the async path in main.py which wires WakeWordManager.",
            )

        last_housekeep = time.monotonic()

        while not self._stop_event.is_set() and self._pipeline.is_active():
            # Periodic housekeeping
            now = time.monotonic()
            if now - last_housekeep >= HOUSEKEEP_S:
                # RELIABILITY FIX: _run_housekeeping() reaches into the memory
                # manager, which can raise (a locked DB, a manager whose shape
                # changed). Unguarded, that exception propagated out of the
                # loop and killed the always-on service outright -- the
                # assistant would simply stop answering -- because a *logging*
                # step failed. Housekeeping is now advisory.
                try:
                    self._run_housekeeping()
                except Exception:
                    logger.exception("Housekeeping failed; service continues")
                last_housekeep = now

            # Adapt poll interval to pipeline state
            state = self._pipeline.get_state()
            poll_s = (
                ACTIVE_POLL_S
                if state in (PipelineState.PROCESSING, PipelineState.RESPONDING)
                else IDLE_POLL_S
            )
            # Use stop_event.wait() so shutdown() wakes us up immediately
            self._stop_event.wait(timeout=poll_s)

        if self._pending_signal is not None:
            logger.info("Received signal %d - shutting down", self._pending_signal)
            self._pending_signal = None

        # Signal the listener thread to stop. It must honour _stop_event, and
        # the loop can exit without it having been set (pipeline reached
        # STOPPED), so set it here before waiting rather than assuming.
        self._stop_event.set()
        self._pipeline.stop()
        if self._wake_thread is not None and self._wake_thread.is_alive():
            self._wake_thread.join(timeout=2.0)
            if self._wake_thread.is_alive():
                # THREAD-LEAK FIX: the reference used to be dropped here
                # unconditionally, so a listener that ignored _stop_event kept
                # running -- still capturing audio -- with nothing left
                # pointing at it. Keep the handle and say so.
                logger.warning(
                    "Wake-word listener %s did not stop within 2s; it is still "
                    "running. Its implementation must return once "
                    "_stop_event is set.",
                    self._wake_thread.name,
                )
            else:
                self._wake_thread = None

    def _on_state_change(self, old_state: PipelineState, new_state: PipelineState) -> None:
        """Log pipeline state transitions."""
        logger.debug("State: %s → %s", old_state.value, new_state.value)

    def _run_housekeeping(self) -> None:
        """Log periodic housekeeping stats (memory, state, uptime)."""
        state = self._pipeline.get_state()
        if self._memory_manager is not None:
            interaction_count = getattr(
                self._memory_manager, "interaction_count", lambda: "n/a"
            )()
        else:
            interaction_count = "n/a (manager not initialized)"
        logger.info(
            "[housekeeping] state=%s personality=%s memory_interactions=%s",
            state.value,
            self.personality,
            interaction_count,
        )

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handle OS signals for graceful shutdown.

        DEADLOCK FIX: this used to call shutdown(), which calls
        VoicePipeline.stop() -> dispatch(), which acquires the pipeline's
        non-reentrant state lock. Signal handlers run *on the main thread*,
        interrupting whatever it was doing -- so a SIGINT that arrived while
        the main thread was already inside dispatch() holding that lock made
        the handler block on a lock only the interrupted frame could release.
        The process would hang forever, on the one code path whose entire job
        is to shut it down. The logging call had the same shape of problem
        (logging takes its own locks, and the interrupted frame may hold them).

        So the handler now does the one thing that is safe here: set the stop
        event. run_as_background_service()'s finally block performs the real
        shutdown once the loop unwinds, on the normal call stack.
        """
        self._pending_signal = signum
        self._stop_event.set()

    def _init_auth(self) -> None:
        """Lazily initialize auth manager."""
        try:
            from Agent_Guru.security.auth_manager import AuthManager

            self._auth_manager = AuthManager()
            self._auth_manager.initialize()
            logger.info("AuthManager initialized")
        except Exception:
            logger.exception("AuthManager unavailable")

    def _init_policy(self) -> None:
        """Lazily initialize policy manager."""
        try:
            from Agent_Guru.policy.policy_manager import PolicyManager

            self._policy_manager = PolicyManager()
            self._policy_manager.initialize()
            logger.info("PolicyManager initialized")
        except Exception:
            logger.exception("PolicyManager unavailable")

    def _init_memory(self) -> None:
        """Lazily initialize memory manager."""
        try:
            from Agent_Guru.memory.memory_manager import MemoryConfig, MemoryManager

            # BUG-028: pass MemoryConfig() so the sync path matches main.py
            # which always passes an explicit config for consistent defaults.
            self._memory_manager = MemoryManager(MemoryConfig())
            logger.info("MemoryManager initialized")
        except Exception:
            logger.exception("MemoryManager unavailable")

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            msg = "AgentGuru not initialized. Call initialize() first."
            raise RuntimeError(msg)
