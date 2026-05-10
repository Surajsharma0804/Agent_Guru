"""Module: Agent_Guru.vision.engine
Purpose: Main GuruVision recognition engine — orchestrates all vision modules.

GuruVisionEngine is the single entry-point for:
  - Initialising all sub-modules (detection, alignment, recognition,
    liveness, emotion, tracking, database)
  - Processing video frames end-to-end
  - Managing identities (add / remove / update / list)
  - Event callbacks (identity_recognized, new_identity, permission_changed, error)
  - Graceful shutdown and resource cleanup

Requirements: 3.1, 4.1, 5.1, 5.3, 7.1, 7.4, 8.1, 10.1, 12.2, 12.3, 12.4,
              13.1, 13.2, 13.3, 13.5, 14.4, 16.1–16.5, 20.1–20.7, 22.1,
              31.1, 31.2, 31.3, 32.1, 32.4
"""

from __future__ import annotations

import html
import logging
import signal
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from Agent_Guru.vision.alignment.aligner import FaceAligner
from Agent_Guru.vision.config import GuruVisionConfig
from Agent_Guru.vision.database.face_db import FaceDatabase, MatchResult
from Agent_Guru.vision.detection.detector import Detection, FaceDetector
from Agent_Guru.vision.emotion.recognizer import EmotionRecognizer, EmotionResult
from Agent_Guru.vision.exceptions import (
    DatabaseError,
    InitializationError,
    InvalidImageError,
)
from Agent_Guru.vision.liveness.detector import LivenessDetector, LivenessResult
from Agent_Guru.vision.recognition.recognizer import FaceRecognizer
from Agent_Guru.vision.tracking.tracker import FaceTracker, TrackedFace
from Agent_Guru.vision.utils.logging import setup_logging
from Agent_Guru.vision.utils.preprocessing import enhance_low_light, is_low_light

if TYPE_CHECKING:
    from collections.abc import Callable

    import numpy as np

logger = logging.getLogger("guruvision.engine")

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FaceResult:
    """Per-face result from a single frame.

    Attributes:
        track_id: Tracker ID for this face (-1 if tracking disabled).
        bbox: Bounding box (x, y, w, h).
        identity: Recognised identity name, or "Unknown".
        confidence: Recognition confidence in [0.0, 1.0].
        permission_level: RBAC level of the matched identity.
        is_live: Liveness result (None if liveness disabled).
        emotion: Dominant emotion label (None if emotion disabled).
        emotion_confidence: Emotion confidence (None if emotion disabled).
        landmarks: 5-point landmarks array or None.

    """

    track_id: int
    bbox: tuple
    identity: str
    confidence: float
    permission_level: str
    is_live: bool | None = None
    emotion: str | None = None
    emotion_confidence: float | None = None
    landmarks: np.ndarray | None = field(default=None, repr=False)


@dataclass
class RecognitionResult:
    """Aggregated result for a complete frame.

    Attributes:
        faces: List of per-face results.
        frame_timestamp: ISO 8601 timestamp when the frame was processed.
        processing_time_ms: Wall-clock time to process the frame in ms.
        frame_enhanced: True if low-light enhancement was applied.

    """

    faces: list[FaceResult]
    frame_timestamp: str
    processing_time_ms: float
    frame_enhanced: bool = False


@dataclass
class IdentityInfo:
    """Summary info for a stored identity."""

    name: str
    num_embeddings: int
    permission_level: str
    date_added: str


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class GuruVisionEngine:
    """Main GuruVision recognition engine.

    Orchestrates detection → alignment → recognition → liveness → emotion →
    tracking into a single ``process_frame()`` call.

    Args:
        config_path: Optional path to a YAML/JSON config file.  When None
            the engine uses default :class:`GuruVisionConfig` values.

    Example::

        engine = GuruVisionEngine()
        engine.initialize()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = engine.process_frame(frame)
        engine.shutdown()

    """

    def __init__(self, config_path: str | None = None) -> None:
        self._config_path = config_path
        self._config: GuruVisionConfig | None = None
        self._initialized = False
        self._shutdown_event = threading.Event()

        self._detector: FaceDetector | None = None
        self._aligner: FaceAligner | None = None
        self._recognizer: FaceRecognizer | None = None
        self._liveness: LivenessDetector | None = None
        self._emotion: EmotionRecognizer | None = None
        self._tracker: FaceTracker | None = None
        self._database: FaceDatabase | None = None

        # Event callbacks: event_type → list of callables
        self._callbacks: dict[str, list[Callable[..., None]]] = {
            "identity_recognized": [],
            "new_identity": [],
            "permission_changed": [],
            "error": [],
            "system_ready": [],
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialise all sub-modules and load the face database.

        Must be called before :meth:`process_frame`.  Safe to call multiple
        times — subsequent calls are no-ops.

        Raises:
            RuntimeError: If initialisation fails critically.

        """
        if self._initialized:
            return

        # Load and validate config
        if self._config_path:
            try:
                self._config = GuruVisionConfig.from_file(self._config_path)
            except Exception as exc:
                logger.exception(
                    "Failed to load config from '%s': %s — using defaults",
                    self._config_path,
                    exc,
                )
                self._config = GuruVisionConfig()
        else:
            self._config = GuruVisionConfig()

        warnings = self._config.validate()
        for w in warnings:
            logger.warning("Config warning: %s", w)

        # Setup logging
        setup_logging(
            log_level=self._config.log_level,
            log_file=self._config.log_file,
            max_size_mb=self._config.log_max_size_mb,
        )

        cfg = self._config

        # Initialise sub-modules — each wrapped so a single failure is reported
        # clearly via InitializationError rather than a bare AttributeError.
        try:
            self._detector = FaceDetector(
                confidence_threshold=cfg.detection_confidence,
                use_gpu=cfg.use_gpu,
            )
        except Exception as exc:
            msg = f"FaceDetector init failed: {exc}"
            raise InitializationError(msg) from exc
        try:
            self._aligner = FaceAligner(output_size=(112, 112))
        except Exception as exc:
            msg = f"FaceAligner init failed: {exc}"
            raise InitializationError(msg) from exc
        try:
            self._recognizer = FaceRecognizer(
                model_path=cfg.onnx_model_path,
                use_gpu=cfg.use_gpu,
            )
        except Exception as exc:
            msg = f"FaceRecognizer init failed: {exc}"
            raise InitializationError(msg) from exc
        # Optional modules — failure is logged but does NOT abort initialisation
        if cfg.enable_liveness:
            try:
                self._liveness = LivenessDetector()
            except Exception:
                logger.exception("LivenessDetector init failed (%s) — liveness disabled")
                self._liveness = None
        else:
            self._liveness = None

        if cfg.enable_emotion:
            try:
                self._emotion = EmotionRecognizer(use_gpu=cfg.use_gpu)
            except Exception:
                logger.exception("EmotionRecognizer init failed (%s) — emotion disabled")
                self._emotion = None
        else:
            self._emotion = None

        if cfg.enable_tracking:
            try:
                self._tracker = FaceTracker(max_age=cfg.tracker_max_age)
            except Exception:
                logger.exception("FaceTracker init failed (%s) — tracking disabled")
                self._tracker = None
        else:
            self._tracker = None

        try:
            self._database = FaceDatabase(db_path=cfg.database_path)
        except Exception as exc:
            msg = f"FaceDatabase init failed: {exc}"
            raise InitializationError(msg) from exc
        self._initialized = True
        logger.info("GuruVisionEngine initialised successfully")
        self._emit("system_ready", {})

    def shutdown(self) -> None:
        """Release resources and save pending database changes.

        Completes within 3 seconds.  Safe to call multiple times.
        """
        if not self._initialized:
            return

        logger.info("GuruVisionEngine shutting down …")
        self._shutdown_event.set()

        # Save database
        if self._database is not None:
            try:
                self._database.save()
            except Exception:
                logger.exception("shutdown: database save failed")
        # Reset tracker
        if self._tracker is not None:
            try:
                self._tracker.reset()
            except Exception:
                logger.exception("shutdown: tracker reset failed")
        self._initialized = False
        logger.info("GuruVisionEngine shutdown complete")

    # ------------------------------------------------------------------
    # Frame processing
    # ------------------------------------------------------------------

    def process_frame(self, frame: np.ndarray) -> RecognitionResult:
        """Process a single BGR video frame end-to-end.

        Pipeline:
          1. Low-light enhancement (if enabled and frame is dark)
          2. Face detection
          3. Tracker update
          4. Per-face: align → embed → match identity
          5. Per-face: liveness check (if enabled)
          6. Per-face: emotion recognition (if enabled)
          7. Aggregate results and emit events

        Args:
            frame: BGR uint8 image of any size.

        Returns:
            :class:`RecognitionResult` with per-face results and metadata.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.

        """
        if not self._initialized:
            msg = "GuruVisionEngine.initialize() must be called before process_frame()"
            raise RuntimeError(
                msg,
            )

        t_start = time.perf_counter()
        timestamp = datetime.now(UTC).isoformat()
        frame_enhanced = False

        # Step 1: Low-light enhancement
        if self._config.enable_low_light_enhancement and is_low_light(frame):
            frame = enhance_low_light(frame)
            frame_enhanced = True

        # Step 2: Face detection
        try:
            if self._detector is None:
                msg = "FaceDetector not initialized"
                raise RuntimeError(msg)
            detections: list[Detection] = self._detector.detect(frame)
        except Exception as exc:
            logger.exception("Detection failed")
            self._emit("error", {"stage": "detection", "error": str(exc)})
            detections = []
        # Step 3: Tracker update — failure degrades gracefully to per-frame processing
        active_tracks: list[TrackedFace] = []
        if self._tracker is not None:
            try:
                active_tracks = self._tracker.update(detections)
            except Exception as exc:
                logger.exception(
                    "Tracker update failed (%s) — processing frames independently",
                    exc,
                )
                self._emit("error", {"stage": "tracking", "error": str(exc)})
                active_tracks = []
        # Step 4–6: Per-face processing
        face_results: list[FaceResult] = []
        for i, detection in enumerate(detections):
            face_result = self._process_single_face(frame, detection, i, active_tracks)
            if face_result is not None:
                face_results.append(face_result)

        # Step 7: Emit recognition events
        for fr in face_results:
            if fr.identity != "Unknown":
                self._emit(
                    "identity_recognized",
                    {
                        "identity": fr.identity,
                        "confidence": fr.confidence,
                        "track_id": fr.track_id,
                        "permission_level": fr.permission_level,
                    },
                )

        processing_ms = (time.perf_counter() - t_start) * 1000.0

        return RecognitionResult(
            faces=face_results,
            frame_timestamp=timestamp,
            processing_time_ms=round(processing_ms, 2),
            frame_enhanced=frame_enhanced,
        )

    def _process_single_face(
        self,
        frame: np.ndarray,
        detection: Detection,
        det_index: int,
        active_tracks: list[TrackedFace],
    ) -> FaceResult | None:
        """Run the full per-face pipeline for one detection."""
        # Find matching track
        track_id = -1
        if active_tracks:
            # Match by detection index order (tracker preserves insertion order)
            if det_index < len(active_tracks):
                track_id = active_tracks[det_index].track_id

        # Align — failure skips this face entirely (AlignmentError)
        try:
            aligned = self._aligner.align(frame, detection)
        except Exception as exc:
            logger.exception("Alignment failed for detection %d: %s")
            self._emit("error", {"stage": "alignment", "error": str(exc)})
            return None
        # Liveness check — failure degrades gracefully (LivenessError → continue without)
        is_live: bool | None = None
        if self._liveness is not None:
            try:
                liveness_result: LivenessResult = self._liveness.check_liveness(
                    aligned,
                    landmarks=detection.landmarks,
                )
                is_live = liveness_result.is_live
                if not is_live:
                    logger.debug(
                        "Liveness failed for detection %d — skipping recognition",
                        det_index,
                    )
                    return FaceResult(
                        track_id=track_id,
                        bbox=detection.bbox,
                        identity="Unknown",
                        confidence=0.0,
                        permission_level="guest",
                        is_live=False,
                    )
            except Exception as exc:
                logger.exception(
                    "Liveness check failed (%s) — continuing without liveness result",
                    exc,
                )
                self._emit("error", {"stage": "liveness", "error": str(exc)})
        # Extract embedding and match identity — RecognitionError is logged, partial result returned
        identity = "Unknown"
        confidence = 0.0
        permission_level = "guest"
        try:
            embedding = self._recognizer.extract_embedding(aligned)
            match: MatchResult = self._database.search(
                embedding,
                threshold=self._config.recognition_threshold,
            )
            identity = match.identity
            confidence = match.confidence
            permission_level = match.permission_level

            # Assign identity to tracker
            if self._tracker is not None and track_id >= 0 and identity != "Unknown":
                self._tracker.assign_identity(track_id, identity)
        except InvalidImageError as exc:
            logger.exception("Invalid aligned face for detection %d: %s")
            return None
            logger.exception("Recognition failed for detection %d: %s")
            self._emit("error", {"stage": "recognition", "error": str(exc)})
            # Return partial result with Unknown identity rather than dropping the face
        # Emotion recognition — failure falls back to "neutral" (EmotionError)
        emotion: str | None = None
        emotion_conf: float | None = None
        if self._emotion is not None:
            try:
                emotion_result: EmotionResult = self._emotion.recognize(aligned)
                emotion = emotion_result.emotion
                emotion_conf = emotion_result.confidence
            except Exception:
                logger.exception("Emotion recognition failed (%s) — returning neutral")
                emotion = "neutral"
                emotion_conf = 0.0
        return FaceResult(
            track_id=track_id,
            bbox=detection.bbox,
            identity=identity,
            confidence=confidence,
            permission_level=permission_level,
            is_live=is_live,
            emotion=emotion,
            emotion_confidence=emotion_conf,
            landmarks=detection.landmarks,
        )

    # ------------------------------------------------------------------
    # Identity management
    # ------------------------------------------------------------------

    def add_identity(
        self,
        name: str,
        images: list[np.ndarray],
        permission_level: str = "user",
    ) -> bool:
        """Add a new identity from a list of face images.

        Each image is detected, aligned, and embedded.  All resulting
        embeddings are stored in the database.

        Args:
            name: Unique identity name.
            images: List of BGR uint8 images containing the person's face.
            permission_level: RBAC level ("admin", "user", "guest", "denied").

        Returns:
            True if at least one embedding was successfully extracted and stored.

        """
        self._require_initialized()
        embeddings: list[np.ndarray] = []

        for i, img in enumerate(images):
            try:
                detections = self._detector.detect(img)
                if not detections:
                    logger.warning("add_identity '%s': no face in image %d", name, i)
                    continue
                # Use the largest face
                detection = max(detections, key=lambda d: d.bbox[2] * d.bbox[3])
                aligned = self._aligner.align(img, detection)
                embedding = self._recognizer.extract_embedding(aligned)
                embeddings.append(embedding)
            except Exception as exc:
                logger.exception("add_identity '%s': failed on image %d: %s", name, i, exc)
        if not embeddings:
            logger.error("add_identity '%s': no valid embeddings extracted", name)
            return False

        try:
            result = self._database.add_identity(
                name,
                embeddings,
                permission_level=permission_level,
            )
        except Exception as exc:
            logger.exception("add_identity '%s': database write failed: %s", name, exc)
            msg = f"Failed to store identity '{html.escape(str(name))}': {exc}"
            raise DatabaseError(
                msg,
            ) from exc
        if result:
            self._emit("new_identity", {"name": name, "num_embeddings": len(embeddings)})
        return result

    def remove_identity(self, name: str) -> bool:
        """Remove an identity from the database.

        Returns:
            True if the identity was found and removed.

        """
        self._require_initialized()
        return self._database.remove_identity(name)

    def get_identities(self) -> list[IdentityInfo]:
        """Return summary info for all stored identities."""
        self._require_initialized()
        return [
            IdentityInfo(
                name=identity.name,
                num_embeddings=len(identity.embeddings),
                permission_level=identity.permission_level,
                date_added=identity.date_added,
            )
            for identity in self._database.get_all_identities()
        ]

    def update_permission(self, name: str, permission_level: str) -> bool:
        """Update the permission level for an existing identity.

        Returns:
            True on success.

        """
        self._require_initialized()
        result = self._database.update_permission(name, permission_level)
        if result:
            self._emit("permission_changed", {"name": name, "permission_level": permission_level})
        return result

    # ------------------------------------------------------------------
    # Event system
    # ------------------------------------------------------------------

    def register_callback(self, event_type: str, callback: Callable[..., None]) -> None:
        """Register a callback for a specific event type.

        Supported event types:
          - ``identity_recognized``: fired when a known face is matched.
          - ``new_identity``: fired when a new identity is added.
          - ``permission_changed``: fired when a permission level changes.
          - ``error``: fired on non-fatal processing errors.
          - ``system_ready``: fired once after successful initialisation.

        Args:
            event_type: One of the supported event type strings.
            callback: Callable that accepts a single dict argument.

        Raises:
            ValueError: If event_type is not recognised.

        """
        if event_type not in self._callbacks:
            msg = (
                f"Unknown event type '{html.escape(str(event_type))}'. "
                f"Valid types: {sorted(self._callbacks.keys())}"
            )
            raise ValueError(
                msg,
            )
        self._callbacks[event_type].append(callback)
        logger.debug("Registered callback for event '%s'", event_type)

    # ------------------------------------------------------------------
    # Camera / video input
    # ------------------------------------------------------------------

    def open_video_source(
        self,
        source: Any | None = None,
    ) -> Any:  # cv2.VideoCapture
        """Open a video source and return an OpenCV VideoCapture object.

        Args:
            source: One of:
                - ``None`` — use ``config.camera_index`` (default webcam).
                - ``int`` — webcam device index.
                - ``str`` — path to a video file (MP4, AVI, MOV) or image file.

        Returns:
            An opened :class:`cv2.VideoCapture` instance.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
            ImportError: If OpenCV is not installed.
            OSError: If the source cannot be opened.

        """
        self._require_initialized()

        try:
            import cv2  # type: ignore[import]
        except ImportError as exc:
            msg = (
                "opencv-python is required for video input. "
                "Install it with: pip install opencv-python"
            )
            raise ImportError(
                msg,
            ) from exc
        if source is None:
            source = self._config.camera_index

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            msg = f"Cannot open video source {source!r}. Check the device index or file path."
            raise OSError(
                msg,
            )

        # Log detected properties
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        logger.info("Opened video source %r — %dx%d @ %.1f FPS", source, width, height, fps)
        return cap

    def process_video_source(
        self,
        source: Any | None = None,
        max_frames: int | None = None,
        on_result: Callable[[RecognitionResult], None] | None = None,
    ) -> list[RecognitionResult]:
        """Process all frames from a video source.

        Opens the source, reads frames in a loop, calls :meth:`process_frame`
        on each, and optionally invokes *on_result* after every frame.

        Args:
            source: Same as :meth:`open_video_source`.
            max_frames: Stop after this many frames (``None`` = run until end
                of file or until :meth:`shutdown` is called).
            on_result: Optional callback invoked with each
                :class:`RecognitionResult`.

        Returns:
            List of all :class:`RecognitionResult` objects produced.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called.
            OSError: If the source cannot be opened.

        """
        self._require_initialized()
        cap = self.open_video_source(source)

        results: list[RecognitionResult] = []
        frame_count = 0

        try:
            while not self._shutdown_event.is_set():
                ret, frame = cap.read()
                if not ret:
                    logger.info("Video source exhausted after %d frames", frame_count)
                    break

                result = self.process_frame(frame)
                results.append(result)
                if on_result is not None:
                    try:
                        on_result(result)
                    except Exception:
                        logger.exception("on_result callback raised")
                frame_count += 1
                if max_frames is not None and frame_count >= max_frames:
                    break
        finally:
            cap.release()
            logger.info("Video source released after %d frames", frame_count)

        return results

    def setup_signal_handlers(self) -> None:
        """Register SIGINT / SIGTERM handlers to call shutdown() gracefully."""

        def _handler(signum: int, frame: Any) -> None:
            logger.info("Signal %d received — shutting down", signum)
            self.shutdown()

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, event_type: str, data: dict[str, Any]) -> None:
        """Fire all registered callbacks for event_type."""
        for cb in self._callbacks.get(event_type, []):
            try:
                cb(data)
            except Exception as exc:
                logger.exception("Callback for '%s' raised: %s", event_type, exc)

    def _require_initialized(self) -> None:
        if not self._initialized:
            msg = "GuruVisionEngine.initialize() must be called first"
            raise RuntimeError(msg)
