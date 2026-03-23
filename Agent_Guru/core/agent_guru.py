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
from collections.abc import Callable
from typing import Any, Optional

from Agent_Guru.core.voice_pipeline import PipelineState, VoicePipeline

logger = logging.getLogger(__name__)

_PLATFORM = platform.system().lower()


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
        self._auth_manager: Optional[Any] = None
        self._policy_manager: Optional[Any] = None
        self._memory_manager: Optional[Any] = None

        # Callbacks for platform-specific integrations
        self._on_wake: Optional[Callable[[str], None]] = None
        self._on_response: Optional[Callable[[str], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize all subsystems.

        Loads managers lazily to avoid import errors on platforms
        where optional dependencies are not installed.
        """
        logger.info("Initializing AgentGuru (platform=%s, personality=%s)",
                    _PLATFORM, self.personality)

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

        # Register signal handlers (desktop only)
        if _PLATFORM in ("windows", "darwin", "linux"):
            signal.signal(signal.SIGTERM, self._handle_signal)
            signal.signal(signal.SIGINT, self._handle_signal)

        logger.info("AgentGuru background service started")

        try:
            self._service_loop()
        finally:
            self._running = False
            logger.info("AgentGuru background service stopped")

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
        """Main service loop — runs until stop event is set."""
        while not self._stop_event.is_set() and self._pipeline.is_active():
            # In production, wake word detection runs in a separate thread.
            # This loop just keeps the service alive and handles housekeeping.
            time.sleep(0.1)

    def _on_state_change(
        self, old_state: PipelineState, new_state: PipelineState
    ) -> None:
        """Log pipeline state transitions."""
        logger.debug("State: %s → %s", old_state.value, new_state.value)

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handle OS signals for graceful shutdown."""
        logger.info("Received signal %d — shutting down", signum)
        self.shutdown()

    def _init_auth(self) -> None:
        """Lazily initialize auth manager."""
        try:
            from Agent_Guru.security.auth_manager import AuthManager
            self._auth_manager = AuthManager()
            self._auth_manager.initialize()
            logger.info("AuthManager initialized")
        except Exception as exc:
            logger.warning("AuthManager unavailable: %s", exc)

    def _init_policy(self) -> None:
        """Lazily initialize policy manager."""
        try:
            from Agent_Guru.policy.policy_manager import PolicyManager
            self._policy_manager = PolicyManager()
            self._policy_manager.initialize()
            logger.info("PolicyManager initialized")
        except Exception as exc:
            logger.warning("PolicyManager unavailable: %s", exc)

    def _init_memory(self) -> None:
        """Lazily initialize memory manager."""
        try:
            from Agent_Guru.memory.memory_manager import MemoryManager
            self._memory_manager = MemoryManager()
            logger.info("MemoryManager initialized")
        except Exception as exc:
            logger.warning("MemoryManager unavailable: %s", exc)

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("AgentGuru not initialized. Call initialize() first.")
