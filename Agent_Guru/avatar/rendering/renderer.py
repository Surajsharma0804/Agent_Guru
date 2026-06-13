"""Module: Agent_Guru.avatar.rendering.renderer
Purpose: Production avatar renderer with FACS-based expression system.

Architecture:
    - FACS Action Unit → facial expression mapping
    - Smooth emotion transitions (linear interpolation over 200-500ms)
    - Three backends: opencv, pyqt, headless
    - 60 FPS render loop with frame timing
    - Personality-specific visual styling (Guru vs Maya)
    - Performance monitoring (FPS counter, frame timing)

Performance:
    - Target: 60 FPS (16.7ms per frame)
    - Minimum: 24 FPS (Req 4.1)
    - Emotion update latency: <100ms (Req 4.2)
    - Transition duration: 200-500ms (Req 4.6)

Requirements: Req 4 (Avatar Rendering), Req 11.5
"""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import TYPE_CHECKING

import numpy as np

from Agent_Guru.avatar.models import (
    EMOTION_FACS_MAP,
    AvatarState,
    EmotionState,
    PersonalityType,
)

if TYPE_CHECKING:
    import threading

logger = logging.getLogger("guruvision.avatar.renderer")


# ---------------------------------------------------------------------------
# Personality visual styles
# ---------------------------------------------------------------------------

# BGR colour palettes for each personality
_PERSONALITY_PALETTE: dict[PersonalityType, dict[str, tuple[int, int, int]]] = {
    PersonalityType.GURU: {
        "background": (30, 30, 50),  # Dark navy
        "skin": (180, 140, 110),  # Warm skin tone
        "hair": (40, 30, 20),  # Dark brown
        "eyes": (60, 80, 120),  # Blue-grey
        "text": (220, 220, 255),  # Light blue-white
        "accent": (100, 160, 220),  # Professional blue
    },
    PersonalityType.MAYA: {
        "background": (40, 20, 40),  # Dark purple
        "skin": (200, 160, 130),  # Warm skin tone
        "hair": (60, 40, 80),  # Dark purple-brown
        "eyes": (80, 120, 80),  # Green
        "text": (255, 220, 240),  # Warm pink-white
        "accent": (200, 100, 160),  # Warm pink
    },
}

# Emotion → background tint (BGR)
_EMOTION_TINT: dict[str, tuple[int, int, int]] = {
    "joy": (0, 200, 200),
    "happy": (0, 200, 200),
    "sadness": (150, 80, 40),
    "anger": (30, 30, 200),
    "fear": (150, 40, 150),
    "disgust": (40, 120, 40),
    "surprise": (40, 200, 40),
    "amusement": (0, 180, 180),
    "excitement": (0, 220, 255),
    "awe": (100, 200, 255),
    "admiration": (80, 160, 220),
    "adoration": (100, 180, 255),
    "triumph": (0, 200, 255),
    "calmness": (120, 160, 120),
    "relief": (100, 180, 100),
    "satisfaction": (80, 180, 80),
    "nostalgia": (120, 100, 160),
    "romance": (100, 80, 200),
    "interest": (60, 160, 200),
    "entrancement": (80, 140, 220),
    "anxiety": (100, 60, 140),
    "awkwardness": (100, 100, 120),
    "boredom": (100, 100, 100),
    "confusion": (120, 100, 80),
    "craving": (60, 100, 180),
    "empathic_pain": (80, 60, 120),
    "horror": (20, 20, 160),
    "neutral": (120, 120, 120),
}


# ---------------------------------------------------------------------------
# FACS expression renderer
# ---------------------------------------------------------------------------


class FACSExpressionRenderer:
    """Render facial expressions using FACS Action Units.

    Maps AU activations to geometric deformations of a parametric face.
    """

    def apply_aus(
        self,
        frame: np.ndarray,
        action_units: dict[int, float],
        face_center: tuple[int, int],
        face_radius: int,
        palette: dict[str, tuple[int, int, int]],
    ) -> np.ndarray:
        """Apply FACS action units to a face frame.

        Args:
            frame: BGR frame to draw on.
            action_units: Dict of {AU_number: intensity}.
            face_center: (cx, cy) center of face.
            face_radius: Radius of face circle.
            palette: Colour palette for this personality.

        Returns:
            Modified frame.

        """
        try:
            import cv2  # type: ignore[import]
        except ImportError:
            return frame

        cx, cy = face_center
        r = face_radius

        # AU1/AU2: Brow raise (inner/outer)
        brow_raise = max(
            action_units.get(1, 0.0),
            action_units.get(2, 0.0),
        )
        # AU4: Brow lowerer
        brow_lower = action_units.get(4, 0.0)
        # AU6: Cheek raiser
        cheek_raise = action_units.get(6, 0.0)
        # AU12: Lip corner puller (smile)
        smile = action_units.get(12, 0.0)
        # AU15: Lip corner depressor (frown)
        frown = action_units.get(15, 0.0)
        # AU5: Upper lid raiser (wide eyes)
        wide_eyes = action_units.get(5, 0.0)
        # AU43/AU45: Eyes closed/blink
        eyes_closed = max(action_units.get(43, 0.0), action_units.get(45, 0.0))

        # --- Draw eyebrows ---
        brow_y_base = cy - int(r * 0.45)
        brow_y = brow_y_base - int(brow_raise * r * 0.08) + int(brow_lower * r * 0.05)
        brow_thickness = max(2, int(r * 0.04))
        brow_color = palette.get("hair", (40, 30, 20))

        # Left brow
        lbx = cx - int(r * 0.35)
        cv2.line(
            frame,
            (lbx - int(r * 0.12), brow_y + int(brow_lower * 3)),
            (lbx + int(r * 0.12), brow_y - int(brow_lower * 3)),
            brow_color,
            brow_thickness,
        )
        # Right brow
        rbx = cx + int(r * 0.35)
        cv2.line(
            frame,
            (rbx - int(r * 0.12), brow_y - int(brow_lower * 3)),
            (rbx + int(r * 0.12), brow_y + int(brow_lower * 3)),
            brow_color,
            brow_thickness,
        )

        # --- Draw eyes ---
        eye_y = cy - int(r * 0.25)
        eye_rx = max(2, int(r * 0.12 * (1.0 + wide_eyes * 0.3)))
        eye_ry = max(1, int(r * 0.07 * (1.0 + wide_eyes * 0.4) * (1.0 - eyes_closed * 0.9)))
        eye_color = palette.get("eyes", (60, 80, 120))

        # Left eye
        cv2.ellipse(frame, (cx - int(r * 0.3), eye_y), (eye_rx, eye_ry), 0, 0, 360, eye_color, -1)
        # Right eye
        cv2.ellipse(frame, (cx + int(r * 0.3), eye_y), (eye_rx, eye_ry), 0, 0, 360, eye_color, -1)

        # Eye pupils
        pupil_r = max(1, int(eye_rx * 0.4))
        cv2.circle(frame, (cx - int(r * 0.3), eye_y), pupil_r, (10, 10, 10), -1)
        cv2.circle(frame, (cx + int(r * 0.3), eye_y), pupil_r, (10, 10, 10), -1)

        # --- Draw cheeks (AU6) ---
        if cheek_raise > 0.2:
            int(cheek_raise * 40)
            cheek_color = (80, 80, 200)
            cheek_r = int(r * 0.15)
            overlay = frame.copy()
            cv2.circle(overlay, (cx - int(r * 0.4), cy + int(r * 0.05)), cheek_r, cheek_color, -1)
            cv2.circle(overlay, (cx + int(r * 0.4), cy + int(r * 0.05)), cheek_r, cheek_color, -1)
            cv2.addWeighted(overlay, cheek_raise * 0.3, frame, 1.0 - cheek_raise * 0.3, 0, frame)

        # --- Draw mouth ---
        mouth_y = cy + int(r * 0.3)
        mouth_w = int(r * 0.35)

        if smile > 0.3:
            # Smile arc
            smile_depth = int(smile * r * 0.15)
            cv2.ellipse(
                frame,
                (cx, mouth_y),
                (mouth_w, smile_depth + 4),
                0,
                0,
                180,
                (30, 30, 30),
                2,
            )
        elif frown > 0.3:
            # Frown arc (inverted)
            frown_depth = int(frown * r * 0.12)
            cv2.ellipse(
                frame,
                (cx, mouth_y + frown_depth),
                (mouth_w, frown_depth + 4),
                0,
                180,
                360,
                (30, 30, 30),
                2,
            )
        else:
            # Neutral line
            cv2.line(frame, (cx - mouth_w, mouth_y), (cx + mouth_w, mouth_y), (30, 30, 30), 2)

        return frame


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------


class AvatarRenderer:
    """Production avatar renderer with FACS expression system.

    Args:
        backend: One of "opencv", "pyqt", "headless".
        target_fps: Target rendering frame rate.
        width: Display width in pixels.
        height: Display height in pixels.
        title: Window title (opencv backend).
        transition_duration: Emotion transition duration in seconds.

    """

    def __init__(
        self,
        backend: str = "headless",
        target_fps: int = 60,
        width: int = 640,
        height: int = 480,
        title: str = "Agent Guru Avatar",
        transition_duration: float = 0.35,
    ) -> None:
        self._backend = backend
        self._target_fps = target_fps
        self._width = width
        self._height = height
        self._title = title
        self._transition_duration = transition_duration

        self._running = False
        self._render_thread: threading.Thread | None = None
        self._last_frame: np.ndarray | None = None
        self._last_state: AvatarState | None = None

        # FPS tracking
        self._frame_count = 0
        self._fps_start = time.perf_counter()
        self._measured_fps = 0.0
        self._frame_times: deque[float] = deque(maxlen=100)

        # Transition state
        self._transition_start: float | None = None
        self._prev_emotion: EmotionState | None = None
        self._prev_aus: dict[int, float] = {}

        # FACS renderer
        self._facs_renderer = FACSExpressionRenderer()

        self._cv2_available = self._check_cv2()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize_display(self) -> bool:
        """Initialize the display window or widget."""
        if self._backend == "opencv":
            if not self._cv2_available:
                logger.warning("OpenCV not available — falling back to headless")
                self._backend = "headless"
                return True
            try:
                import cv2  # type: ignore[import]

                cv2.namedWindow(self._title, cv2.WINDOW_RESIZABLE)
                logger.info("OpenCV display initialized (%dx%d)", self._width, self._height)
                return True
            except Exception:
                logger.exception("OpenCV display init failed: %s — using headless")
                self._backend = "headless"
                return True
        elif self._backend == "pyqt":
            logger.info("PyQt backend: widget must be embedded by caller")
            return True
        else:
            logger.info("Headless renderer initialized (%dx%d)", self._width, self._height)
            return True

    def stop_render_loop(self) -> None:
        """Stop the rendering loop and release resources."""
        self._running = False
        if self._render_thread and self._render_thread.is_alive():
            self._render_thread.join(timeout=2.0)
        if self._backend == "opencv" and self._cv2_available:
            try:
                import cv2  # type: ignore[import]

                cv2.destroyWindow(self._title)
            except cv2.error as exc:
                logger.debug("cv2.destroyWindow failed during shutdown: %s", exc)
        logger.info("Renderer stopped (measured FPS: %.1f)", self._measured_fps)

    def set_target_fps(self, fps: int) -> None:
        """Update the target frame rate."""
        self._target_fps = max(1, fps)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render_frame(self, state: AvatarState) -> np.ndarray:
        """Generate a frame from the current avatar state.

        Applies FACS-based emotion expressions, lip sync mouth movements,
        and personality-specific visual styling.

        Args:
            state: Current :class:`AvatarState`.

        Returns:
            BGR uint8 frame of shape (height, width, 3).

        """
        t_start = time.perf_counter()
        frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)

        palette = _PERSONALITY_PALETTE.get(
            state.personality_type,
            _PERSONALITY_PALETTE[PersonalityType.GURU],
        )

        # Background
        frame[:] = palette["background"]

        # Compute interpolated AUs for smooth transitions
        aus = self._interpolate_aus(state.emotion)

        # Face geometry
        cx, cy = self._width // 2, self._height // 2
        face_radius = min(self._width, self._height) // 3

        if self._cv2_available:
            import cv2  # type: ignore[import]

            # Emotion tint on background
            tint = _EMOTION_TINT.get(state.emotion.emotion, (120, 120, 120))
            tint_alpha = state.emotion.confidence * 0.15
            bg_tint = tuple(
                int(palette["background"][i] * (1 - tint_alpha) + tint[i] * tint_alpha)
                for i in range(3)
            )
            frame[:] = bg_tint

            # Draw face (skin-coloured circle)
            skin_color = palette["skin"]
            cv2.circle(frame, (cx, cy), face_radius, skin_color, -1)

            # Draw hair (top arc)
            hair_color = palette["hair"]
            cv2.ellipse(
                frame,
                (cx, cy - face_radius // 4),
                (face_radius + 10, face_radius + 20),
                0,
                180,
                360,
                hair_color,
                -1,
            )

            # Apply FACS expressions
            frame = self._facs_renderer.apply_aus(frame, aus, (cx, cy), face_radius, palette)

            # Apply lip sync mouth override
            mouth_open = state.lip_sync.mouth_open_ratio
            lip_spread = state.lip_sync.lip_spread
            if mouth_open > 0.05:
                mouth_y = cy + int(face_radius * 0.3)
                mouth_w = int(face_radius * 0.35 * (1.0 + lip_spread * 0.2))
                mouth_h = max(2, int(face_radius * 0.15 * mouth_open))
                # Draw open mouth
                cv2.ellipse(frame, (cx, mouth_y), (mouth_w, mouth_h), 0, 0, 180, (20, 20, 20), -1)
                # Teeth
                if mouth_open > 0.3:
                    teeth_h = max(1, mouth_h - 2)
                    cv2.ellipse(
                        frame,
                        (cx, mouth_y),
                        (mouth_w - 4, teeth_h),
                        0,
                        0,
                        180,
                        (240, 240, 240),
                        -1,
                    )

            # Personality label
            label = state.personality_type.value.upper()
            accent = palette.get("accent", (200, 200, 200))
            cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, accent, 2)

            # Emotion label with confidence
            emotion_text = f"{state.emotion.emotion} ({state.emotion.confidence:.2f})"
            text_color = palette.get("text", (220, 220, 220))
            cv2.putText(
                frame,
                emotion_text,
                (10, self._height - 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                text_color,
                1,
            )

            # Valence/arousal indicator
            va_text = f"V:{state.emotion.valence:+.2f} A:{state.emotion.arousal:+.2f}"
            cv2.putText(
                frame,
                va_text,
                (10, self._height - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                text_color,
                1,
            )

            # FPS counter
            fps_text = f"FPS: {self._measured_fps:.1f}"
            cv2.putText(
                frame,
                fps_text,
                (self._width - 100, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                text_color,
                1,
            )

        self._last_frame = frame
        self._last_state = state
        self._frame_count += 1
        self._update_fps()

        # Track frame time — deque(maxlen=100) auto-evicts oldest
        frame_ms = (time.perf_counter() - t_start) * 1000.0
        self._frame_times.append(frame_ms)

        return frame

    def display_frame(self, frame: np.ndarray) -> bool:
        """Display a frame in the window.

        Returns:
            True on success.

        """
        if self._backend == "opencv" and self._cv2_available:
            try:
                import cv2  # type: ignore[import]

                cv2.imshow(self._title, frame)
                cv2.waitKey(1)
                return True
            except Exception:
                logger.exception("display_frame failed")
                return False
        return True  # headless / pyqt

    def get_last_frame(self) -> np.ndarray | None:
        """Return the most recently rendered frame."""
        return self._last_frame

    def get_measured_fps(self) -> float:
        """Return the measured rendering FPS."""
        return self._measured_fps

    def get_avg_frame_time_ms(self) -> float:
        """Return average frame render time in milliseconds."""
        if not self._frame_times:
            return 0.0
        return float(np.mean(self._frame_times))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _interpolate_aus(self, emotion: EmotionState) -> dict[int, float]:
        """Interpolate FACS AUs for smooth emotion transitions."""
        target_aus = {
            k: v * emotion.confidence for k, v in EMOTION_FACS_MAP.get(emotion.emotion, {}).items()
        }

        # Also use AUs from the emotion state itself if provided
        if emotion.action_units:
            target_aus = emotion.action_units

        if self._prev_emotion is None or self._prev_emotion.emotion == emotion.emotion:
            self._prev_emotion = emotion
            self._prev_aus = target_aus
            self._transition_start = None
            return target_aus

        # Start transition
        if self._transition_start is None:
            self._transition_start = time.perf_counter()

        elapsed = time.perf_counter() - self._transition_start
        alpha = min(1.0, elapsed / self._transition_duration)

        # Interpolate between prev and target AUs
        all_aus = set(self._prev_aus.keys()) | set(target_aus.keys())
        interpolated = {}
        for au in all_aus:
            prev_val = self._prev_aus.get(au, 0.0)
            target_val = target_aus.get(au, 0.0)
            interpolated[au] = prev_val * (1.0 - alpha) + target_val * alpha

        if alpha >= 1.0:
            self._prev_emotion = emotion
            self._prev_aus = target_aus
            self._transition_start = None

        return interpolated

    def _update_fps(self) -> None:
        elapsed = time.perf_counter() - self._fps_start
        if elapsed >= 1.0:
            self._measured_fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_start = time.perf_counter()

    @staticmethod
    def _check_cv2() -> bool:
        try:
            import cv2  # noqa: F401

            return True
        except ImportError:
            return False
