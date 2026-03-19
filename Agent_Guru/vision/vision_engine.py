"""
Vision Engine Coordinator for the Agent Guru Vision System.

Top-level coordinator that initialises all vision modules, manages lifecycle,
and exposes the public API for the rest of Agent Guru.

Public API:
    start()              — initialise all modules (≤10s on GPU)
    stop()               — graceful shutdown
    process_frame()      — route a frame through the Frame Dispatcher
    analyze_screenshot() — synchronous screenshot analysis via ScreenAnalyzer
    answer_question()    — synchronous VQA via VQAEngine
    get_active_modules() — list of currently active module names
    get_event_bus()      — access to the VisionEventBus

Requirements: 12.8, 13.7, 13.8
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import numpy as np
import structlog

from Agent_Guru.vision.activity import ActivityRecognizer
from Agent_Guru.vision.bus import VisionEventBus
from Agent_Guru.vision.depth import DepthEstimator
from Agent_Guru.vision.dispatcher import FrameDispatcher
from Agent_Guru.vision.gesture import GestureRecognizer
from Agent_Guru.vision.handwriting import HandwritingRecognizer
from Agent_Guru.vision.model_manager import ModelManager
from Agent_Guru.vision.observability import VisionObservability, get_observability
from Agent_Guru.vision.ocr import OCREngine
from Agent_Guru.vision.pose import PoseEstimator
from Agent_Guru.vision.privacy import PrivacyFilter
from Agent_Guru.vision.scene import ObjectDetector, SceneClassifier, SpatialReasoner
from Agent_Guru.vision.screen import ScreenAnalyzer
from Agent_Guru.vision.tracker import ObjectTracker
from Agent_Guru.vision.vision_models import ScreenAnalysis, VisionConfig, VQAResult
from Agent_Guru.vision.vqa import VQAEngine

logger: structlog.BoundLogger = structlog.get_logger(__name__)

_INIT_TIMEOUT_SECONDS: float = 10.0


class VisionEngine:
    """Top-level coordinator for the Agent Guru Vision System.

    Initialises all modules in dependency order, manages their lifecycle,
    and routes frames through the Frame Dispatcher.

    Args:
        config: VisionConfig controlling which modules are active and their settings.
        platform: "desktop" or "mobile" — affects VQA routing.
    """

    def __init__(
        self,
        config: VisionConfig | None = None,
        platform: str = "desktop",
    ) -> None:
        self._config = config or VisionConfig()
        self._platform = platform
        self._started = False
        self._obs: VisionObservability = get_observability()

        # Core infrastructure
        self._model_manager = ModelManager(
            vram_budget_gb=self._config.vram_budget_gb,
        )
        self._event_bus = VisionEventBus()
        self._dispatcher = FrameDispatcher(event_bus=self._event_bus)

        # Vision modules (initialised lazily in start())
        self._scene_classifier: SceneClassifier | None = None
        self._object_detector: ObjectDetector | None = None
        self._spatial_reasoner: SpatialReasoner | None = None
        self._depth_estimator: DepthEstimator | None = None
        self._ocr_engine: OCREngine | None = None
        self._handwriting_recognizer: HandwritingRecognizer | None = None
        self._gesture_recognizer: GestureRecognizer | None = None
        self._pose_estimator: PoseEstimator | None = None
        self._screen_analyzer: ScreenAnalyzer | None = None
        self._vqa_engine: VQAEngine | None = None
        self._object_tracker: ObjectTracker | None = None
        self._activity_recognizer: ActivityRecognizer | None = None
        self._privacy_filter: PrivacyFilter | None = None

        self._frame_seq: int = 0

        logger.info(
            "VisionEngine created",
            platform=platform,
            gpu_enabled=self._config.gpu_enabled,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Initialise all enabled modules within the 10s timeout.

        Raises:
            asyncio.TimeoutError: If initialisation exceeds 10 seconds.
        """
        if self._started:
            return

        async def _init() -> None:
            await self._init_modules()

        await asyncio.wait_for(_init(), timeout=_INIT_TIMEOUT_SECONDS)
        self._started = True
        logger.info("VisionEngine started", active_modules=self.get_active_modules())

    async def stop(self) -> None:
        """Gracefully shut down all modules."""
        self._started = False
        self._model_manager.clear()
        logger.info("VisionEngine stopped")

    async def _init_modules(self) -> None:
        """Initialise all vision modules in dependency order."""
        enabled = set(self._config.enabled_modules) if self._config.enabled_modules is not None else None

        def _is_enabled(name: str) -> bool:
            return enabled is None or name in enabled

        # Scene understanding
        if _is_enabled("scene"):
            self._scene_classifier = SceneClassifier(
                model_manager=self._model_manager, config=self._config
            )
            self._object_detector = ObjectDetector(
                model_manager=self._model_manager, config=self._config
            )
            self._spatial_reasoner = SpatialReasoner()
            self._dispatcher.register_module("scene", self._handle_scene)

        # Depth estimation
        if _is_enabled("depth"):
            self._depth_estimator = DepthEstimator(
                model_manager=self._model_manager, config=self._config
            )
            self._dispatcher.register_module("depth", self._handle_depth)

        # OCR
        if _is_enabled("ocr"):
            self._ocr_engine = OCREngine()
            self._dispatcher.register_module("ocr", self._handle_ocr)

        # Handwriting
        if _is_enabled("handwriting"):
            self._handwriting_recognizer = HandwritingRecognizer(
                model_manager=self._model_manager, config=self._config
            )
            self._dispatcher.register_module("handwriting", self._handle_handwriting)

        # Gesture
        if _is_enabled("gesture"):
            self._gesture_recognizer = GestureRecognizer()
            self._dispatcher.register_module("gesture", self._handle_gesture)

        # Pose
        if _is_enabled("pose"):
            self._pose_estimator = PoseEstimator()
            self._dispatcher.register_module("pose", self._handle_pose)

        # Tracking
        if _is_enabled("tracker"):
            self._object_tracker = ObjectTracker()

        # Activity
        if _is_enabled("activity"):
            self._activity_recognizer = ActivityRecognizer()
            self._dispatcher.register_module("activity", self._handle_activity)

        # Privacy filter (always active)
        self._privacy_filter = PrivacyFilter(
            camera_enabled=True,
        )

        # VQA (not registered as a frame module — used via answer_question())
        if _is_enabled("vqa"):
            self._vqa_engine = VQAEngine(platform=self._platform)

        # Screen analyzer (not registered as a frame module — used via analyze_screenshot())
        if _is_enabled("screen"):
            self._screen_analyzer = ScreenAnalyzer()

        self._obs.update_active_modules(len(self._dispatcher.get_active_modules()))
        logger.info("VisionEngine modules initialised")

    # ------------------------------------------------------------------
    # Module handlers (registered with FrameDispatcher)
    # ------------------------------------------------------------------

    async def _handle_scene(self, frame: np.ndarray, frame_seq: int) -> Any:
        if self._object_detector is None:
            return None
        with self._obs.time_module("scene"):
            objects = await self._object_detector.detect(frame)
            if self._scene_classifier:
                label, conf = await self._scene_classifier.classify(frame)
            else:
                label, conf = "uncertain", 0.0
            depth_map = None
            if self._depth_estimator:
                depth_map = await self._depth_estimator.estimate(frame)
            if self._spatial_reasoner:
                relations = self._spatial_reasoner.compute_relations(objects, depth_map)
            else:
                relations = []
        return {"objects": objects, "scene_label": label, "confidence": conf, "relations": relations}

    async def _handle_depth(self, frame: np.ndarray, frame_seq: int) -> Any:
        if self._depth_estimator is None:
            return None
        with self._obs.time_module("depth"):
            return await self._depth_estimator.estimate(frame)

    async def _handle_ocr(self, frame: np.ndarray, frame_seq: int) -> Any:
        if self._ocr_engine is None:
            return None
        with self._obs.time_module("ocr"):
            return await self._ocr_engine.extract(frame)

    async def _handle_handwriting(self, frame: np.ndarray, frame_seq: int) -> Any:
        if self._handwriting_recognizer is None:
            return None
        with self._obs.time_module("handwriting"):
            return await self._handwriting_recognizer.recognize(frame)

    async def _handle_gesture(self, frame: np.ndarray, frame_seq: int) -> Any:
        if self._gesture_recognizer is None:
            return None
        with self._obs.time_module("gesture"):
            return await self._gesture_recognizer.process_frame(frame)

    async def _handle_pose(self, frame: np.ndarray, frame_seq: int) -> Any:
        if self._pose_estimator is None:
            return None
        with self._obs.time_module("pose"):
            return await self._pose_estimator.estimate(frame)

    async def _handle_activity(self, frame: np.ndarray, frame_seq: int) -> Any:
        if self._activity_recognizer is None:
            return None
        self._activity_recognizer.push_frame(frame)
        with self._obs.time_module("activity"):
            return await self._activity_recognizer.classify()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_frame(self, frame: np.ndarray) -> dict[str, Any]:
        """Route a frame through all active modules via the Frame Dispatcher.

        Args:
            frame: uint8 RGB array of shape (H, W, 3).

        Returns:
            Dict mapping module name → result.
        """
        self._frame_seq += 1
        self._obs.record_frame()
        results = await self._dispatcher.dispatch(frame, self._frame_seq)
        return results

    async def analyze_screenshot(self, screenshot: np.ndarray) -> ScreenAnalysis:
        """Analyze a UI screenshot synchronously.

        Args:
            screenshot: uint8 RGB array of shape (H, W, 3).

        Returns:
            ScreenAnalysis with all detected UI elements.

        Raises:
            RuntimeError: If the screen module is not enabled.
        """
        if self._screen_analyzer is None:
            raise RuntimeError("Screen analyzer module is not enabled")
        with self._obs.time_module("screen"):
            return await self._screen_analyzer.analyze(screenshot)

    async def answer_question(self, image: np.ndarray, question: str) -> VQAResult:
        """Answer a natural language question about an image.

        Args:
            image: uint8 RGB array of shape (H, W, 3).
            question: Natural language question string.

        Returns:
            VQAResult with answer and metadata.

        Raises:
            RuntimeError: If the VQA module is not enabled.
        """
        if self._vqa_engine is None:
            raise RuntimeError("VQA module is not enabled")
        with self._obs.time_module("vqa"):
            return await self._vqa_engine.answer(image, question)

    def get_active_modules(self) -> list[str]:
        """Return the names of all currently active modules.

        Returns:
            Sorted list of active module names.
        """
        return self._dispatcher.get_active_modules()

    def get_event_bus(self) -> VisionEventBus:
        """Return the VisionEventBus for subscribing to events.

        Returns:
            The shared VisionEventBus instance.
        """
        return self._event_bus
