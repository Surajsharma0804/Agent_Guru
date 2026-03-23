"""
Module: Agent_Guru.avatar.avatar_system
Purpose: Production facade coordinating all avatar sub-components.

GuruAvatarSystem is the single entry-point for:
  - Emotion recognition (27-emotion taxonomy)
  - Lip synchronization with speech audio
  - Dual personality engine (Guru/Maya)
  - FACS-based avatar rendering
  - Performance monitoring
  - Speech and vision integration
  - Error callbacks and graceful degradation

Requirements: All avatar requirements
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, Optional

import numpy as np

from Agent_Guru.avatar.config import AvatarConfig
from Agent_Guru.avatar.emotion.recognizer import EmotionRecognizer
from Agent_Guru.avatar.lip_sync.controller import LipSyncController
from Agent_Guru.avatar.models import (
    AvatarState,
    EmotionState,
    LipSyncState,
    PersonalityType,
)
from Agent_Guru.avatar.performance import PerformanceMonitor
from Agent_Guru.avatar.personality.engine import PersonalityEngine
from Agent_Guru.avatar.rendering.renderer import AvatarRenderer
from Agent_Guru.avatar.state_manager import StateManager

logger = logging.getLogger("guruvision.avatar.system")


class GuruAvatarSystem:
    """Production avatar system facade.

    Args:
        config: AvatarConfig instance or path to config file.
        render_backend: Rendering backend override.
        personality: Initial personality (GURU or MAYA).
    """

    def __init__(
        self,
        config: Optional[Any] = None,
        render_backend: str = "headless",
        personality: PersonalityType = PersonalityType.GURU,
    ) -> None:
        # Load config
        if isinstance(config, str):
            self._config = AvatarConfig.from_file(config)
        elif isinstance(config, AvatarConfig):
            self._config = config
        else:
            self._config = AvatarConfig.default()

        # Override backend if specified
        if render_backend != "headless":
            self._config.render_backend = render_backend

        self._initial_personality = personality
        self._initialized = False

        self._state_manager = StateManager()
        self._emotion_recognizer: Optional[EmotionRecognizer] = None
        self._lip_sync: Optional[LipSyncController] = None
        self._personality_engine: Optional[PersonalityEngine] = None
        self._renderer: Optional[AvatarRenderer] = None
        self._perf_monitor: Optional[PerformanceMonitor] = None

        self._error_callbacks: list[Callable[[Exception, str, dict[str, Any]], None]] = []
        self._start_time = 0.0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> bool:
        """Initialize all sub-components."""
        if self._initialized:
            return True

        self._start_time = time.perf_counter()

        # Emotion recognizer
        try:
            self._emotion_recognizer = EmotionRecognizer(
                model=self._config.emotion_model,
                confidence_threshold=self._config.emotion_confidence_threshold,
                smoothing_window=self._config.emotion_smoothing_window,
                use_gpu=self._config.enable_gpu,
                map_to_27=self._config.map_to_27_emotions,
            )
        except Exception as exc:
            logger.error("EmotionRecognizer init failed: %s", exc)
            self._notify_error(exc, "emotion_recognizer", {})
            self._emotion_recognizer = EmotionRecognizer(model="heuristic")

        # Lip sync
        try:
            self._lip_sync = LipSyncController(
                model_path=self._config.lip_sync_model_path,
                sync_threshold_ms=self._config.lip_sync_threshold_ms,
                buffer_size=self._config.audio_buffer_size,
            )
        except Exception as exc:
            logger.error("LipSyncController init failed: %s", exc)
            self._notify_error(exc, "lip_sync", {})
            self._lip_sync = LipSyncController()

        # Personality engine
        try:
            self._personality_engine = PersonalityEngine(
                self._config.personality_profile_path
            )
        except Exception as exc:
            logger.error("PersonalityEngine init failed: %s", exc)
            self._notify_error(exc, "personality_engine", {})
            self._personality_engine = PersonalityEngine()

        # Renderer
        try:
            self._renderer = AvatarRenderer(
                backend=self._config.render_backend,
                target_fps=self._config.target_fps,
                width=self._config.display_width,
                height=self._config.display_height,
                transition_duration=self._config.transition_duration_ms / 1000.0,
            )
            self._renderer.initialize_display()
        except Exception as exc:
            logger.error("AvatarRenderer init failed: %s — using headless", exc)
            self._notify_error(exc, "renderer", {})
            self._renderer = AvatarRenderer(backend="headless")
            self._renderer.initialize_display()

        # Performance monitor
        try:
            self._perf_monitor = PerformanceMonitor(
                max_cpu_percent=self._config.max_cpu_percent,
                max_memory_mb=self._config.max_memory_mb,
            )
            self._perf_monitor.start()
        except Exception as exc:
            logger.warning("PerformanceMonitor init failed: %s", exc)
            self._perf_monitor = None

        # Set initial personality
        self._state_manager.switch_personality(self._initial_personality)
        if self._personality_engine:
            profile = self._personality_engine.get_profile(self._initial_personality)
            self._state_manager.update_personality(profile)

        self._initialized = True
        logger.info(
            "GuruAvatarSystem initialized: personality=%s backend=%s",
            self._initial_personality.value, self._config.render_backend,
        )
        return True

    def stop(self) -> None:
        """Stop all components and release resources."""
        if not self._initialized:
            return
        if self._renderer:
            self._renderer.stop_render_loop()
        if self._perf_monitor:
            self._perf_monitor.stop()
        self._initialized = False
        logger.info("GuruAvatarSystem stopped")

    # ------------------------------------------------------------------
    # Processing
    # ------------------------------------------------------------------

    def process_user_emotion(self, frame: np.ndarray) -> EmotionState:
        """Detect user emotion from a video frame and update state."""
        self._require_initialized()

        if self._emotion_recognizer is None:
            return EmotionState.neutral()

        try:
            raw_emotion = self._emotion_recognizer.detect_emotion_smooth(frame)
        except Exception as exc:
            logger.warning("Emotion detection failed: %s — using neutral", exc)
            self._notify_error(exc, "emotion_recognizer", {"frame_shape": frame.shape})
            raw_emotion = EmotionState.neutral()

        # Apply personality modulation
        if self._personality_engine:
            state = self._state_manager.get_state()
            modulated = self._personality_engine.modulate_emotion(raw_emotion, state.personality)
        else:
            modulated = raw_emotion

        self._state_manager.update_emotion(modulated)
        return modulated

    def process_speech_audio(
        self, audio: np.ndarray, sample_rate: int
    ) -> LipSyncState:
        """Process speech audio for lip sync and update state."""
        self._require_initialized()

        if self._lip_sync is None:
            return LipSyncState.neutral()

        try:
            lip_state = self._lip_sync.process_audio_chunk(audio, sample_rate)
        except Exception as exc:
            logger.warning("Lip sync failed: %s — using neutral", exc)
            self._notify_error(exc, "lip_sync", {})
            lip_state = LipSyncState.neutral()

        self._state_manager.update_lip_sync(lip_state)
        return lip_state

    def render_frame(self) -> Optional[np.ndarray]:
        """Render the current avatar state to a frame."""
        self._require_initialized()

        if self._renderer is None:
            return None

        state = self._state_manager.get_state()
        t_start = time.perf_counter()
        try:
            frame = self._renderer.render_frame(state)
            self._renderer.display_frame(frame)
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            if self._perf_monitor:
                self._perf_monitor.record_fps(self._renderer.get_measured_fps())
                self._perf_monitor.record_latency(latency_ms)
            return frame
        except Exception as exc:
            logger.error("Render failed: %s", exc)
            self._notify_error(exc, "renderer", {})
            return None

    def update(
        self,
        frame: Optional[np.ndarray] = None,
        audio: Optional[np.ndarray] = None,
        sample_rate: int = 16000,
    ) -> Optional[np.ndarray]:
        """Single-call update: process inputs and render."""
        self._require_initialized()
        if frame is not None:
            self.process_user_emotion(frame)
        if audio is not None:
            self.process_speech_audio(audio, sample_rate)
        return self.render_frame()

    # ------------------------------------------------------------------
    # Personality management
    # ------------------------------------------------------------------

    def set_personality(self, personality: PersonalityType) -> bool:
        """Switch the active personality."""
        self._require_initialized()
        self._state_manager.switch_personality(personality)
        if self._personality_engine:
            profile = self._personality_engine.get_profile(personality)
            self._state_manager.update_personality(profile)
        logger.info("Personality set to %s", personality.value)
        return True

    # ------------------------------------------------------------------
    # State and metrics
    # ------------------------------------------------------------------

    def get_current_state(self) -> AvatarState:
        """Return the current avatar state."""
        self._require_initialized()
        return self._state_manager.get_state()

    def get_performance_metrics(self) -> dict[str, float]:
        """Return performance metrics."""
        self._require_initialized()
        fps = self._renderer.get_measured_fps() if self._renderer else 0.0
        uptime = time.perf_counter() - self._start_time
        metrics: dict[str, float] = {
            "fps": fps,
            "uptime_seconds": uptime,
        }
        if self._perf_monitor:
            metrics.update(self._perf_monitor.get_metrics())
        return metrics

    def reload_config(self, new_config: AvatarConfig) -> None:
        """Hot-reload configuration without restart."""
        self._config = new_config
        logger.info("Configuration reloaded")

    # ------------------------------------------------------------------
    # Error callbacks
    # ------------------------------------------------------------------

    def register_error_callback(
        self,
        callback: Callable[[Exception, str, dict[str, Any]], None],
    ) -> None:
        """Register a callback for error notifications."""
        self._error_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("GuruAvatarSystem.initialize() must be called first")

    def _notify_error(
        self, exc: Exception, component: str, context: dict[str, Any]
    ) -> None:
        for cb in self._error_callbacks:
            try:
                cb(exc, component, context)
            except Exception as cb_exc:
                logger.warning("Error callback raised: %s", cb_exc)
