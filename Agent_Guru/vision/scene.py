"""
Scene Understanding module for the Agent Guru Vision System.

Provides:
- ObjectDetector: YOLOv8 ONNX-based object detection with configurable threshold
- SceneClassifier: EfficientNet/ViT ONNX-based 30-category scene classification
- SpatialReasoner: Pairwise spatial relationship computation with depth annotation

Requirements: 1.1-1.8
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import numpy as np
import structlog

from Agent_Guru.vision.model_manager import ModelManager
from Agent_Guru.vision.vision_models import (
    BoundingBox,
    DepthMap,
    DetectedObject,
    VisionConfig,
)

logger: structlog.BoundLogger = structlog.get_logger(__name__)

COCO_LABELS: list[str] = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]

SCENE_LABELS: list[str] = [
    "office", "kitchen", "bedroom", "living_room", "bathroom",
    "dining_room", "hallway", "garage", "basement", "attic",
    "street", "park", "forest", "beach", "mountain",
    "desert", "field", "river", "lake", "ocean",
    "restaurant", "store", "hospital", "school", "library",
    "gym", "stadium", "airport", "train_station", "parking_lot",
]

_UNCERTAIN_THRESHOLD: float = 0.4

class ObjectDetector:
    """YOLOv8-based object detector using ONNX Runtime.

    Args:
        model_manager: Shared ModelManager for ONNX session lifecycle.
        config: VisionConfig with detection_threshold and gpu_enabled.
        model_path: Path to the YOLOv8 ONNX model file.
        _infer_fn: Optional callable for testing; replaces ONNX inference.
            Signature: (frame: np.ndarray) -> np.ndarray
            Output shape: (N, 6) where each row is
            [cx_norm, cy_norm, w_norm, h_norm, confidence, class_id]
    """

    def __init__(
        self,
        model_manager: ModelManager,
        config: VisionConfig,
        model_path: str = "models/yolov8n.onnx",
        _infer_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._model_manager = model_manager
        self._config = config
        self._model_path = model_path
        self._infer_fn = _infer_fn
        self._session: Any = None
        logger.info("ObjectDetector initialised", model_path=model_path, threshold=config.detection_threshold)

    def _get_session(self) -> Any:
        if self._infer_fn is not None:
            return None
        if self._session is None:
            try:
                self._session = self._model_manager.load_model("object_detector", self._model_path)
            except Exception as exc:
                logger.error("ObjectDetector: failed to load model", path=self._model_path, error=str(exc))
                raise
        return self._session

    def _run_inference(self, frame: np.ndarray) -> np.ndarray:
        if self._infer_fn is not None:
            return self._infer_fn(frame)
        session = self._get_session()
        import cv2  # type: ignore[import]
        resized = cv2.resize(frame, (640, 640)).astype(np.float32) / 255.0
        blob = np.transpose(resized, (2, 0, 1))[np.newaxis]
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: blob})
        raw = outputs[0][0].T
        boxes_norm = raw[:, :4] / 640.0
        class_scores = raw[:, 4:]
        class_ids = np.argmax(class_scores, axis=1)
        confidences = class_scores[np.arange(len(class_ids)), class_ids]
        detections = np.column_stack([boxes_norm, confidences, class_ids.astype(np.float32)])
        return detections

    async def detect(self, frame: np.ndarray) -> list[DetectedObject]:
        """Detect objects in a frame, filtering by detection_threshold.

        Args:
            frame: uint8 RGB array of shape (H, W, 3).

        Returns:
            List of DetectedObject instances with confidence >= detection_threshold.
        """
        threshold = self._config.detection_threshold
        h, w = frame.shape[:2]
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, self._run_inference, frame)
        objects: list[DetectedObject] = []
        for row in raw:
            cx_n = float(row[0])
            cy_n = float(row[1])
            bw_n = float(row[2])
            bh_n = float(row[3])
            conf = float(row[4])
            class_id = int(row[5])
            if conf < threshold:
                continue
            label = COCO_LABELS[class_id] if 0 <= class_id < len(COCO_LABELS) else "unknown"
            bw_px = bw_n * w
            bh_px = bh_n * h
            x_px = cx_n * w - bw_px / 2.0
            y_px = cy_n * h - bh_px / 2.0
            objects.append(
                DetectedObject(
                    class_label=label,
                    confidence=conf,
                    bounding_box=BoundingBox(x=x_px, y=y_px, width=bw_px, height=bh_px),
                )
            )
        logger.debug("ObjectDetector: detections", count=len(objects), threshold=threshold)
        return objects


class SceneClassifier:
    """EfficientNet/ViT-based scene classifier using ONNX Runtime.

    Returns ("uncertain", conf) when top-1 confidence < 0.4 (Requirement 1.7).

    Args:
        model_manager: Shared ModelManager for ONNX session lifecycle.
        config: VisionConfig.
        model_path: Path to the scene classifier ONNX model file.
        _infer_fn: Optional callable for testing; replaces ONNX inference.
            Signature: (frame: np.ndarray) -> np.ndarray
            Output: 1-D float32 array of length 30 (softmax scores).
    """

    def __init__(
        self,
        model_manager: ModelManager,
        config: VisionConfig,
        model_path: str = "models/scene_efficientnet.onnx",
        _infer_fn: Callable[..., Any] | None = None,
    ) -> None:
        self._model_manager = model_manager
        self._config = config
        self._model_path = model_path
        self._infer_fn = _infer_fn
        self._session: Any = None
        logger.info("SceneClassifier initialised", model_path=model_path)

    def _get_session(self) -> Any:
        if self._infer_fn is not None:
            return None
        if self._session is None:
            try:
                self._session = self._model_manager.load_model("scene_classifier", self._model_path)
            except Exception as exc:
                logger.error("SceneClassifier: failed to load model", path=self._model_path, error=str(exc))
                raise
        return self._session

    def _run_inference(self, frame: np.ndarray) -> np.ndarray:
        if self._infer_fn is not None:
            return self._infer_fn(frame)
        session = self._get_session()
        import cv2  # type: ignore[import]
        resized = cv2.resize(frame, (224, 224)).astype(np.float32) / 255.0
        blob = np.transpose(resized, (2, 0, 1))[np.newaxis]
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: blob})
        logits = outputs[0][0]
        exp_logits = np.exp(logits - np.max(logits))
        scores: np.ndarray = exp_logits / exp_logits.sum()
        return scores

    async def classify(self, frame: np.ndarray) -> tuple[str, float]:
        """Classify the scene in a frame.

        Args:
            frame: uint8 RGB array of shape (H, W, 3).

        Returns:
            Tuple of (scene_label, confidence). Returns ("uncertain", conf)
            when top-1 confidence < 0.4.
        """
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(None, self._run_inference, frame)
        top_idx = int(np.argmax(scores))
        top_conf = float(scores[top_idx])
        if top_conf < _UNCERTAIN_THRESHOLD:
            label = "uncertain"
        else:
            label = SCENE_LABELS[top_idx] if 0 <= top_idx < len(SCENE_LABELS) else "uncertain"
        logger.debug("SceneClassifier: result", label=label, confidence=top_conf)
        return label, top_conf


class SpatialReasoner:
    """Computes pairwise spatial relationships between detected objects.

    Supported relations:
        left_of, right_of, above, below, near, far, occluding, occluded_by

    Symmetry guarantees (Property 3):
        (A, left_of, B)  <->  (B, right_of, A)
        (A, above, B)    <->  (B, below, A)
        (A, occluding, B) <-> (B, occluded_by, A)

    Args:
        near_threshold: Normalised depth value below which objects are "near".
        far_threshold: Normalised depth value above which objects are "far".
    """

    def __init__(
        self,
        near_threshold: float = 0.35,
        far_threshold: float = 0.65,
    ) -> None:
        self._near_threshold = near_threshold
        self._far_threshold = far_threshold

    def compute_relations(
        self,
        objects: list[DetectedObject],
        depth_map: DepthMap | None,
    ) -> list[tuple[str, str, str]]:
        """Compute pairwise spatial relations for all detected object pairs.

        Also annotates each DetectedObject.depth_range when depth_map is provided.

        Args:
            objects: Detected objects in the current frame.
            depth_map: Optional per-pixel depth map (values in [0, 1]).

        Returns:
            List of (obj_a_label, relation, obj_b_label) triples.
        """
        if depth_map is not None and not depth_map.is_null:
            self._annotate_depth(objects, depth_map)

        relations: list[tuple[str, str, str]] = []
        n = len(objects)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                a = objects[i]
                b = objects[j]
                relations.extend(self._pair_relations(a, b))

        return relations

    @staticmethod
    def _centre(obj: DetectedObject) -> tuple[float, float]:
        bb = obj.bounding_box
        return bb.x + bb.width / 2.0, bb.y + bb.height / 2.0

    @staticmethod
    def _iou(a: DetectedObject, b: DetectedObject) -> float:
        ax1 = a.bounding_box.x
        ay1 = a.bounding_box.y
        ax2 = ax1 + a.bounding_box.width
        ay2 = ay1 + a.bounding_box.height
        bx1 = b.bounding_box.x
        by1 = b.bounding_box.y
        bx2 = bx1 + b.bounding_box.width
        by2 = by1 + b.bounding_box.height
        inter_x = max(0.0, min(ax2, bx2) - max(ax1, bx1))
        inter_y = max(0.0, min(ay2, by2) - max(ay1, by1))
        inter = inter_x * inter_y
        if inter == 0.0:
            return 0.0
        union = (
            a.bounding_box.width * a.bounding_box.height
            + b.bounding_box.width * b.bounding_box.height
            - inter
        )
        return inter / union if union > 0.0 else 0.0

    def _pair_relations(
        self, a: DetectedObject, b: DetectedObject
    ) -> list[tuple[str, str, str]]:
        result: list[tuple[str, str, str]] = []
        la = a.class_label
        lb = b.class_label
        cx_a, cy_a = self._centre(a)
        cx_b, cy_b = self._centre(b)

        if cx_a < cx_b:
            result.append((la, "left_of", lb))
        elif cx_a > cx_b:
            result.append((la, "right_of", lb))

        if cy_a < cy_b:
            result.append((la, "above", lb))
        elif cy_a > cy_b:
            result.append((la, "below", lb))

        if a.depth_range is not None and b.depth_range is not None:
            depth_a = (a.depth_range[0] + a.depth_range[1]) / 2.0
            depth_b = (b.depth_range[0] + b.depth_range[1]) / 2.0
            if depth_a < depth_b - 0.1:
                result.append((la, "near", lb))
            elif depth_a > depth_b + 0.1:
                result.append((la, "far", lb))
        else:
            area_a = a.bounding_box.width * a.bounding_box.height
            area_b = b.bounding_box.width * b.bounding_box.height
            if area_a > area_b * 1.5:
                result.append((la, "near", lb))
            elif area_b > area_a * 1.5:
                result.append((la, "far", lb))

        iou = self._iou(a, b)
        if iou > 0.1:
            if a.depth_range is not None and b.depth_range is not None:
                depth_a = (a.depth_range[0] + a.depth_range[1]) / 2.0
                depth_b = (b.depth_range[0] + b.depth_range[1]) / 2.0
                if depth_a < depth_b:
                    result.append((la, "occluding", lb))
                else:
                    result.append((la, "occluded_by", lb))
            else:
                area_a = a.bounding_box.width * a.bounding_box.height
                area_b = b.bounding_box.width * b.bounding_box.height
                if area_a >= area_b:
                    result.append((la, "occluding", lb))
                else:
                    result.append((la, "occluded_by", lb))

        return result

    def _annotate_depth(
        self, objects: list[DetectedObject], depth_map: DepthMap
    ) -> None:
        h, w = depth_map.data.shape[:2]
        for obj in objects:
            bb = obj.bounding_box
            x1 = max(0, int(bb.x))
            y1 = max(0, int(bb.y))
            x2 = min(w, int(bb.x + bb.width))
            y2 = min(h, int(bb.y + bb.height))
            if x2 <= x1 or y2 <= y1:
                continue
            region = depth_map.data[y1:y2, x1:x2]
            obj.depth_range = (float(region.min()), float(region.max()))
