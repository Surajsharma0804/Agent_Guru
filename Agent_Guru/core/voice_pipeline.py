"""
Module: Agent_Guru.core.voice_pipeline
Purpose: End-to-end voice pipeline state machine

Wires together:
  wake word → STT → intent → action/LLM → TTS → playback

State machine:
  IDLE → LISTENING → PROCESSING → RESPONDING → IDLE

Supports:
- "stop listening" command to pause
- "exit" / "goodbye" commands to quit
- Wake word re-activation after response
- Manual activation as fallback

Performance:
    - State transitions: O(1)
    - End-to-end latency: <2.5s target

Author: Agent Guru Team
Date: 2026-03-19
Version: 1.0.0
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Commands that control pipeline flow
_STOP_COMMANDS = {"stop listening", "pause", "stop"}
_EXIT_COMMANDS = {"exit", "goodbye", "bye", "quit", "shutdown"}


class PipelineState(str, Enum):
    """Voice pipeline states."""
    IDLE = "idle"               # Waiting for wake word
    LISTENING = "listening"     # Capturing speech after wake word
    PROCESSING = "processing"   # Running STT + intent + action/LLM
    RESPONDING = "responding"   # Playing TTS response
    PAUSED = "paused"           # Explicitly paused by user
    STOPPED = "stopped"         # Terminated


class PipelineEvent(str, Enum):
    """Events that drive state transitions."""
    WAKE_WORD_DETECTED = "wake_word_detected"
    SPEECH_CAPTURED = "speech_captured"
    INTENT_RESOLVED = "intent_resolved"
    RESPONSE_READY = "response_ready"
    PLAYBACK_COMPLETE = "playback_complete"
    STOP_COMMAND = "stop_command"
    EXIT_COMMAND = "exit_command"
    MANUAL_ACTIVATE = "manual_activate"
    ERROR = "error"


# Valid state transitions: {current_state: {event: next_state}}
_TRANSITIONS: dict[PipelineState, dict[PipelineEvent, PipelineState]] = {
    PipelineState.IDLE: {
        PipelineEvent.WAKE_WORD_DETECTED: PipelineState.LISTENING,
        PipelineEvent.MANUAL_ACTIVATE: PipelineState.LISTENING,
        PipelineEvent.EXIT_COMMAND: PipelineState.STOPPED,
    },
    PipelineState.LISTENING: {
        PipelineEvent.SPEECH_CAPTURED: PipelineState.PROCESSING,
        PipelineEvent.STOP_COMMAND: PipelineState.PAUSED,
        PipelineEvent.EXIT_COMMAND: PipelineState.STOPPED,
        PipelineEvent.ERROR: PipelineState.IDLE,
    },
    PipelineState.PROCESSING: {
        PipelineEvent.INTENT_RESOLVED: PipelineState.RESPONDING,
        PipelineEvent.RESPONSE_READY: PipelineState.RESPONDING,
        PipelineEvent.STOP_COMMAND: PipelineState.PAUSED,
        PipelineEvent.EXIT_COMMAND: PipelineState.STOPPED,
        PipelineEvent.ERROR: PipelineState.IDLE,
    },
    PipelineState.RESPONDING: {
        PipelineEvent.PLAYBACK_COMPLETE: PipelineState.IDLE,
        PipelineEvent.STOP_COMMAND: PipelineState.PAUSED,
        PipelineEvent.EXIT_COMMAND: PipelineState.STOPPED,
        PipelineEvent.ERROR: PipelineState.IDLE,
    },
    PipelineState.PAUSED: {
        PipelineEvent.WAKE_WORD_DETECTED: PipelineState.LISTENING,
        PipelineEvent.MANUAL_ACTIVATE: PipelineState.LISTENING,
        PipelineEvent.EXIT_COMMAND: PipelineState.STOPPED,
    },
    PipelineState.STOPPED: {},  # Terminal state
}


class VoicePipeline:
    """
    End-to-end voice pipeline state machine.

    Coordinates all voice assistant components through a well-defined
    state machine. Each state has clear entry/exit actions and valid
    transitions.

    Example:
        >>> pipeline = VoicePipeline()
        >>> pipeline.start()
        >>> # Pipeline runs: IDLE → LISTENING → PROCESSING → RESPONDING → IDLE
        >>> pipeline.stop()

    State Machine:
        IDLE: Waiting for wake word or manual activation
        LISTENING: Capturing user speech
        PROCESSING: STT + intent parsing + action/LLM
        RESPONDING: TTS synthesis + audio playback
        PAUSED: User said "stop listening"
        STOPPED: Terminal state

    Performance:
        - State transition: O(1)
        - Event dispatch: O(k) where k = number of listeners
    """

    def __init__(self) -> None:
        """Initialize the voice pipeline."""
        self._state = PipelineState.IDLE
        self._lock = threading.Lock()
        self._state_listeners: list[Callable[[PipelineState, PipelineState], None]] = []
        self._event_listeners: list[Callable[[PipelineEvent, Any], None]] = []
        self._last_transcript: str | None = None
        self._last_response: str | None = None
        self._error_count = 0

        logger.info("VoicePipeline initialized in IDLE state")

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def get_state(self) -> PipelineState:
        """Return current pipeline state."""
        return self._state

    def dispatch(self, event: PipelineEvent, data: Any = None) -> bool:
        """
        Dispatch an event to drive a state transition.

        Time Complexity: O(1) for transition lookup + O(k) for listeners

        Args:
            event: The event to dispatch
            data: Optional event data

        Returns:
            True if transition occurred, False if event not valid in current state
        """
        with self._lock:
            current = self._state
            transitions = _TRANSITIONS.get(current, {})
            next_state = transitions.get(event)

            if next_state is None:
                logger.debug(f"Event {event.value} ignored in state {current.value}")
                return False

            self._state = next_state
            logger.info(f"Pipeline: {current.value} → {next_state.value} (event: {event.value})")

        # Notify listeners outside lock
        for listener in self._state_listeners:
            try:
                listener(current, next_state)
            except Exception as e:
                logger.error(f"State listener error: {e}")

        for listener in self._event_listeners:
            try:
                listener(event, data)
            except Exception as e:
                logger.error(f"Event listener error: {e}")

        return True

    def on_state_change(self, callback: Callable[[PipelineState, PipelineState], None]) -> None:
        """Register a callback for state changes.

        Args:
            callback: Called with (old_state, new_state) on each transition
        """
        self._state_listeners.append(callback)

    def on_event(self, callback: Callable[[PipelineEvent, Any], None]) -> None:
        """Register a callback for events.

        Args:
            callback: Called with (event, data) on each dispatch
        """
        self._event_listeners.append(callback)

    # ------------------------------------------------------------------
    # Convenience methods for pipeline stages
    # ------------------------------------------------------------------

    def wake_word_detected(self) -> bool:
        """Signal that wake word was detected."""
        return self.dispatch(PipelineEvent.WAKE_WORD_DETECTED)

    def manual_activate(self) -> bool:
        """Manually activate listening (button press fallback)."""
        return self.dispatch(PipelineEvent.MANUAL_ACTIVATE)

    def speech_captured(self, transcript: str) -> bool:
        """Signal that speech was captured and transcribed.

        Args:
            transcript: STT transcription result
        """
        self._last_transcript = transcript

        # Check for flow control commands
        normalized = transcript.strip().lower()
        if normalized in _EXIT_COMMANDS:
            return self.dispatch(PipelineEvent.EXIT_COMMAND, transcript)
        if normalized in _STOP_COMMANDS:
            return self.dispatch(PipelineEvent.STOP_COMMAND, transcript)

        return self.dispatch(PipelineEvent.SPEECH_CAPTURED, transcript)

    def intent_resolved(self, intent: str, response: str | None = None) -> bool:
        """Signal that intent was resolved and action taken.

        Args:
            intent: Resolved intent name
            response: Optional response text for TTS
        """
        self._last_response = response
        return self.dispatch(PipelineEvent.INTENT_RESOLVED, {"intent": intent, "response": response})

    def response_ready(self, response: str) -> bool:
        """Signal that LLM response is ready for TTS.

        Args:
            response: LLM response text
        """
        self._last_response = response
        return self.dispatch(PipelineEvent.RESPONSE_READY, response)

    def playback_complete(self) -> bool:
        """Signal that TTS playback finished. Returns to IDLE."""
        return self.dispatch(PipelineEvent.PLAYBACK_COMPLETE)

    def report_error(self, error: str) -> bool:
        """Signal an error occurred. Returns to IDLE.

        Args:
            error: Error description
        """
        self._error_count += 1
        logger.error(f"Pipeline error: {error}")
        return self.dispatch(PipelineEvent.ERROR, error)

    def stop(self) -> bool:
        """Stop the pipeline (terminal state)."""
        return self.dispatch(PipelineEvent.EXIT_COMMAND)

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_idle(self) -> bool:
        """Return True if pipeline is in IDLE state."""
        return self._state == PipelineState.IDLE

    def is_listening(self) -> bool:
        """Return True if pipeline is in LISTENING state."""
        return self._state == PipelineState.LISTENING

    def is_processing(self) -> bool:
        """Return True if pipeline is in PROCESSING state."""
        return self._state == PipelineState.PROCESSING

    def is_responding(self) -> bool:
        """Return True if pipeline is in RESPONDING state."""
        return self._state == PipelineState.RESPONDING

    def is_paused(self) -> bool:
        """Return True if pipeline is in PAUSED state."""
        return self._state == PipelineState.PAUSED

    def is_stopped(self) -> bool:
        """Return True if pipeline is in STOPPED (terminal) state."""
        return self._state == PipelineState.STOPPED

    def is_active(self) -> bool:
        """Return True if pipeline is not stopped."""
        return self._state != PipelineState.STOPPED

    @property
    def last_transcript(self) -> str | None:
        """Last STT transcript."""
        return self._last_transcript

    @property
    def last_response(self) -> str | None:
        """Last response text."""
        return self._last_response

    @property
    def error_count(self) -> int:
        """Total number of errors encountered."""
        return self._error_count
