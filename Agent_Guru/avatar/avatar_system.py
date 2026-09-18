"""Module: Agent_Guru.avatar.avatar_system
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
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy as np

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
        config: Any | None = None,
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
        self._emotion_recognizer: EmotionRecognizer | None = None
        self._lip_sync: LipSyncController | None = None
        self._personality_engine: PersonalityEngine | None = None
        self._renderer: AvatarRenderer | None = None
        self._perf_monitor: PerformanceMonitor | None = None

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

        self._emotion_recognizer = self._build_emotion_recognizer()
        self._lip_sync = self._build_lip_sync()
        self._personality_engine = self._build_personality_engine()
        self._renderer = self._build_renderer()

        # Performance monitor
        try:
            self._perf_monitor = PerformanceMonitor(
                max_cpu_percent=self._config.max_cpu_percent,
                max_memory_mb=self._config.max_memory_mb,
            )
            self._perf_monitor.start()
        except Exception:
            logger.exception("PerformanceMonitor init failed")
            self._perf_monitor = None

        # Set initial personality
        self._state_manager.switch_personality(self._initial_personality)
        if self._personality_engine:
            profile = self._personality_engine.get_profile(self._initial_personality)
            self._state_manager.update_personality(profile)

        self._initialized = True
        logger.info(
            "GuruAvatarSystem initialized: personality=%s backend=%s",
            self._initial_personality.value,
            self._config.render_backend,
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
            logger.exception("Emotion detection failed — using neutral")
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

    def process_speech_audio(self, audio: np.ndarray, sample_rate: int) -> LipSyncState:
        """Process speech audio for lip sync and update state."""
        self._require_initialized()

        if self._lip_sync is None:
            return LipSyncState.neutral()

        try:
            lip_state = self._lip_sync.process_audio_chunk(audio, sample_rate)
        except Exception as exc:
            logger.exception("Lip sync failed — using neutral")
            self._notify_error(exc, "lip_sync", {})
            lip_state = LipSyncState.neutral()

        self._state_manager.update_lip_sync(lip_state)
        return lip_state

    def render_frame(self) -> np.ndarray | None:
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
            logger.exception("Render failed")
            self._notify_error(exc, "renderer", {})
            return None

    def update(
        self,
        frame: np.ndarray | None = None,
        audio: np.ndarray | None = None,
        sample_rate: int = 16000,
    ) -> np.ndarray | None:
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
        """Hot-reload configuration without restart.

        BUG FIX (Round 13): this previously only reassigned ``self._config``
        to the new object and logged a message. Every already-constructed
        sub-component (EmotionRecognizer, LipSyncController,
        PersonalityEngine, AvatarRenderer, PerformanceMonitor) is built
        from ``self._config`` once, in :meth:`initialize`, and none of
        them re-read it afterwards -- so a caller invoking this method
        (or :class:`~Agent_Guru.avatar.config.ConfigWatcher`, which calls
        exactly this method whenever the on-disk config file changes)
        believed a live setting change had taken effect, when in reality
        nothing downstream ever observed the new values until the next
        full restart. That is a silent no-op wearing the API of a real
        hot-reload feature -- confirmed by inspection: not one line of
        the old body referenced any sub-component.

        Fixed by diffing the old and new config per sub-component and,
        for each one, either applying a cheap in-place update through
        that component's own setter (for fields that are safe to change
        without rebuilding internal state -- e.g. confidence thresholds,
        target FPS, render dimensions, resource limits) or fully
        reconstructing the component via the same construction-with-
        fallback helper :meth:`initialize` uses (for fields that are
        only meaningful at construction time -- e.g. emotion backend
        selection, GPU device detection, or the renderer's actual
        window/thread backend). Each sub-component's reload is isolated
        in its own try/except reported through the existing error-
        callback mechanism, so one broken subsystem's reload failure
        never blocks the others from applying and never raises out of
        this method for a problem that :meth:`initialize` itself would
        merely log and degrade gracefully from.

        If the system has not been initialized yet, there are no
        sub-components to update -- this simply stores the new config,
        exactly matching what :meth:`initialize` will read on its first
        run.
        """
        old_config = self._config
        self._config = new_config

        if not self._initialized:
            logger.info("Configuration replaced (system not yet initialized)")
            return

        self._reload_emotion_recognizer(old_config, new_config)
        self._reload_lip_sync(old_config, new_config)
        self._reload_personality_engine(old_config, new_config)
        self._reload_renderer(old_config, new_config)
        self._reload_performance_monitor(old_config, new_config)

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
    # Sub-component construction (shared by initialize() and
    # reload_config() so both paths apply the exact same
    # construct-with-graceful-fallback behavior).
    # ------------------------------------------------------------------

    def _build_emotion_recognizer(self) -> EmotionRecognizer:
        try:
            return EmotionRecognizer(
                model=self._config.emotion_model,
                confidence_threshold=self._config.emotion_confidence_threshold,
                smoothing_window=self._config.emotion_smoothing_window,
                use_gpu=self._config.enable_gpu,
                map_to_27=self._config.map_to_27_emotions,
            )
        except Exception as exc:
            logger.exception("EmotionRecognizer init failed")
            self._notify_error(exc, "emotion_recognizer", {})
            return EmotionRecognizer(model="heuristic")

    def _build_lip_sync(self) -> LipSyncController:
        try:
            return LipSyncController(
                model_path=self._config.lip_sync_model_path,
                sync_threshold_ms=self._config.lip_sync_threshold_ms,
                buffer_size=self._config.audio_buffer_size,
            )
        except Exception as exc:
            logger.exception("LipSyncController init failed")
            self._notify_error(exc, "lip_sync", {})
            return LipSyncController()

    def _build_personality_engine(self) -> PersonalityEngine:
        try:
            return PersonalityEngine(self._config.personality_profile_path)
        except Exception as exc:
            logger.exception("PersonalityEngine init failed")
            self._notify_error(exc, "personality_engine", {})
            return PersonalityEngine()

    def _build_renderer(self) -> AvatarRenderer:
        try:
            renderer = AvatarRenderer(
                backend=self._config.render_backend,
                target_fps=self._config.target_fps,
                width=self._config.display_width,
                height=self._config.display_height,
                transition_duration=self._config.transition_duration_ms / 1000.0,
            )
            renderer.initialize_display()
        except Exception as exc:
            logger.exception("AvatarRenderer init failed — using headless")
            self._notify_error(exc, "renderer", {})
            renderer = AvatarRenderer(backend="headless")
            renderer.initialize_display()
        return renderer

    # ------------------------------------------------------------------
    # reload_config() per-subsystem helpers
    # ------------------------------------------------------------------

    def _reload_emotion_recognizer(self, old: AvatarConfig, new: AvatarConfig) -> None:
        try:
            if (
                old.emotion_model != new.emotion_model
                or old.emotion_smoothing_window != new.emotion_smoothing_window
                or old.enable_gpu != new.enable_gpu
                or old.map_to_27_emotions != new.map_to_27_emotions
            ):
                # These fields only take effect at construction time
                # (backend selection, GPU device detection, EMA/Kalman
                # smoothing-window sizing) -- rebuild the component.
                self._emotion_recognizer = self._build_emotion_recognizer()
            elif (
                self._emotion_recognizer is not None
                and old.emotion_confidence_threshold != new.emotion_confidence_threshold
            ):
                self._emotion_recognizer.set_confidence_threshold(
                    new.emotion_confidence_threshold,
                )
        except Exception as exc:
            logger.exception("Failed to reload emotion recognizer config")
            self._notify_error(exc, "emotion_recognizer", {"phase": "reload_config"})

    def _reload_lip_sync(self, old: AvatarConfig, new: AvatarConfig) -> None:
        try:
            if (
                old.lip_sync_model_path != new.lip_sync_model_path
                or old.audio_buffer_size != new.audio_buffer_size
            ):
                self._lip_sync = self._build_lip_sync()
            elif (
                self._lip_sync is not None
                and old.lip_sync_threshold_ms != new.lip_sync_threshold_ms
            ):
                self._lip_sync.set_sync_threshold_ms(new.lip_sync_threshold_ms)
        except Exception as exc:
            logger.exception("Failed to reload lip sync config")
            self._notify_error(exc, "lip_sync", {"phase": "reload_config"})

    def _reload_personality_engine(self, old: AvatarConfig, new: AvatarConfig) -> None:
        try:
            if (
                self._personality_engine is not None
                and new.personality_profile_path
                and old.personality_profile_path != new.personality_profile_path
            ):
                self._personality_engine.load_profile(new.personality_profile_path)
                # Re-apply the (possibly updated) profile for whichever
                # personality is currently active so the change is
                # visible immediately, not just on the next set_personality().
                state = self._state_manager.get_state()
                profile = self._personality_engine.get_profile(state.personality_type)
                self._state_manager.update_personality(profile)
        except Exception as exc:
            logger.exception("Failed to reload personality profile")
            self._notify_error(exc, "personality_engine", {"phase": "reload_config"})

    def _reload_renderer(self, old: AvatarConfig, new: AvatarConfig) -> None:
        try:
            if old.render_backend != new.render_backend:
                # Switching backend means tearing down whatever window/
                # thread the old backend owns before building a new one.
                if self._renderer is not None:
                    self._renderer.stop_render_loop()
                self._renderer = self._build_renderer()
                return
            if self._renderer is None:
                return
            if old.target_fps != new.target_fps:
                self._renderer.set_target_fps(new.target_fps)
            if old.display_width != new.display_width or old.display_height != new.display_height:
                self._renderer.set_dimensions(new.display_width, new.display_height)
            if old.transition_duration_ms != new.transition_duration_ms:
                self._renderer.set_transition_duration(new.transition_duration_ms / 1000.0)
        except Exception as exc:
            logger.exception("Failed to reload renderer config")
            self._notify_error(exc, "renderer", {"phase": "reload_config"})

    def _reload_performance_monitor(self, old: AvatarConfig, new: AvatarConfig) -> None:
        try:
            if self._perf_monitor is not None and (
                old.max_cpu_percent != new.max_cpu_percent
                or old.max_memory_mb != new.max_memory_mb
            ):
                self._perf_monitor.set_limits(new.max_cpu_percent, new.max_memory_mb)
        except Exception as exc:
            logger.exception("Failed to reload performance monitor limits")
            self._notify_error(exc, "performance_monitor", {"phase": "reload_config"})

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_initialized(self) -> None:
        if not self._initialized:
            msg = "GuruAvatarSystem.initialize() must be called first"
            raise RuntimeError(msg)

    def _notify_error(self, exc: Exception, component: str, context: dict[str, Any]) -> None:
        for cb in self._error_callbacks:
            try:
                cb(exc, component, context)
            except Exception:
                logger.exception("Error callback raised")
