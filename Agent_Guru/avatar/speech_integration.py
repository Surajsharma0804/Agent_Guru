"""
Module: Agent_Guru.avatar.speech_integration
Purpose: Integration between Avatar system and Agent_Guru.speech.

Handles:
    - Audio stream routing from TTS engine to lip sync
    - Personality switching on wake word detection
    - Audio playback event callbacks (start, stop, error)
    - Ring buffer management for smooth audio delivery

Requirements: Req 6 (Integration with Speech System), Tasks 5 & 16
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Iterator, List, Optional

import numpy as np

from Agent_Guru.avatar.lip_sync.audio_buffer import AudioRingBuffer
from Agent_Guru.avatar.models import LipSyncState, PersonalityType

logger = logging.getLogger("guruvision.avatar.speech_integration")

# Wake word → personality mapping
WAKE_WORD_PERSONALITY: Dict[str, PersonalityType] = {
    "hey guru": PersonalityType.GURU,
    "hey maya": PersonalityType.MAYA,
    "guru": PersonalityType.GURU,
    "maya": PersonalityType.MAYA,
}


class SpeechAvatarBridge:
    """Bridge between Agent_Guru.speech and the avatar system.

    Receives audio from the TTS engine and routes it to the lip sync
    controller. Also handles personality switching on wake word detection.

    Args:
        lip_sync_callback: Called with LipSyncState for each audio chunk.
        personality_callback: Called with PersonalityType on wake word.
        sample_rate: Expected audio sample rate.
        buffer_capacity: Ring buffer capacity in samples.
    """

    def __init__(
        self,
        lip_sync_callback: Callable[[LipSyncState], None],
        personality_callback: Callable[[PersonalityType], None],
        sample_rate: int = 16000,
        buffer_capacity: int = 32768,
    ) -> None:
        self._lip_sync_callback = lip_sync_callback
        self._personality_callback = personality_callback
        self._sample_rate = sample_rate
        self._buffer = AudioRingBuffer(capacity=buffer_capacity)
        self._playback_callbacks: List[Callable[[str, Any], None]] = []
        self._is_playing = False
        self._lock = threading.Lock()

        # Lazy import lip sync controller
        self._lip_sync: Optional[Any] = None

    # ------------------------------------------------------------------
    # Audio input
    # ------------------------------------------------------------------

    def on_audio_chunk(self, audio: np.ndarray, sample_rate: int) -> None:
        """Receive an audio chunk from the TTS engine.

        Args:
            audio: Float32 mono audio samples.
            sample_rate: Sample rate in Hz.
        """
        if audio is None or audio.size == 0:
            return

        # Buffer the audio
        written = self._buffer.write(audio)
        if written < len(audio):
            logger.warning(
                "Audio buffer overflow: dropped %d samples", len(audio) - written
            )

        # Process for lip sync
        self._process_for_lip_sync(audio, sample_rate)

        if not self._is_playing:
            with self._lock:
                self._is_playing = True
            self._fire_playback_event("start", {"sample_rate": sample_rate})

    def on_audio_stream(
        self, audio_stream: Iterator[np.ndarray], sample_rate: int
    ) -> None:
        """Process a streaming audio iterator.

        Args:
            audio_stream: Iterator yielding float32 audio chunks.
            sample_rate: Sample rate in Hz.
        """
        for chunk in audio_stream:
            self.on_audio_chunk(chunk, sample_rate)
        self.on_playback_complete()

    def on_playback_complete(self) -> None:
        """Called when audio playback finishes."""
        with self._lock:
            self._is_playing = False
        self._buffer.clear()
        # Return to neutral lip position
        self._lip_sync_callback(LipSyncState.neutral())
        self._fire_playback_event("stop", {})

    def on_playback_error(self, error: Exception) -> None:
        """Called when audio playback encounters an error."""
        logger.error("Speech playback error: %s", error)
        with self._lock:
            self._is_playing = False
        self._fire_playback_event("error", {"error": str(error)})

    # ------------------------------------------------------------------
    # Wake word / personality switching
    # ------------------------------------------------------------------

    def on_wake_word(self, wake_word: str) -> None:
        """Handle wake word detection and switch personality.

        Args:
            wake_word: Detected wake word string (e.g. "hey guru").
        """
        wake_lower = wake_word.lower().strip()
        personality = WAKE_WORD_PERSONALITY.get(wake_lower)
        if personality is not None:
            logger.info("Wake word '%s' → switching to %s", wake_word, personality.value)
            self._personality_callback(personality)
        else:
            logger.debug("Unknown wake word: '%s'", wake_word)

    # ------------------------------------------------------------------
    # Playback event callbacks
    # ------------------------------------------------------------------

    def register_playback_callback(
        self, callback: Callable[[str, Any], None]
    ) -> None:
        """Register a callback for playback events.

        Args:
            callback: Called with (event_type, data) where event_type is
                      "start", "stop", or "error".
        """
        self._playback_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_for_lip_sync(self, audio: np.ndarray, sample_rate: int) -> None:
        """Process audio chunk for lip sync."""
        if self._lip_sync is None:
            self._init_lip_sync()

        if self._lip_sync is None:
            return

        try:
            state = self._lip_sync.process_audio_chunk(audio, sample_rate)
            self._lip_sync_callback(state)
        except Exception as exc:
            logger.warning("Lip sync processing failed: %s", exc)
            self._lip_sync_callback(LipSyncState.neutral())

    def _init_lip_sync(self) -> None:
        """Lazily initialize the lip sync controller."""
        try:
            from Agent_Guru.avatar.lip_sync.controller import LipSyncController
            self._lip_sync = LipSyncController(
                sync_threshold_ms=50.0,
                buffer_size=self._buffer.capacity,
            )
        except Exception as exc:
            logger.error("Failed to initialize LipSyncController: %s", exc)

    def _fire_playback_event(self, event_type: str, data: Any) -> None:
        for cb in self._playback_callbacks:
            try:
                cb(event_type, data)
            except Exception as exc:
                logger.warning("Playback callback error: %s", exc)
