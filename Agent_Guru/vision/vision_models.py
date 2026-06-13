"""Shared data models for the Agent Guru Vision System.

These models are used by all vision modules (scene understanding, depth,
OCR, gesture, pose, screen analysis, VQA, tracking, activity recognition).

NOTE: This file is intentionally separate from models.py, which contains
face-recognition-specific models (FaceDetection, FaceFeatures, etc.).

Import from: Agent_Guru.vision.vision_models
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    import numpy as np

# ---------------------------------------------------------------------------
# Primitive geometry
# ---------------------------------------------------------------------------


@dataclass
class BoundingBox:
    """Axis-aligned bounding box (pixels, top-left origin).

    Attributes:
        x: Left edge in pixels.
        y: Top edge in pixels.
        width: Box width in pixels.
        height: Box height in pixels.

    """

    x: float
    y: float
    width: float
    height: float


# ---------------------------------------------------------------------------
# Event bus
# ---------------------------------------------------------------------------


@dataclass
class VisionEvent:
    """A single event emitted by any vision module.

    Attributes:
        event_type: One of the supported event type strings (see design §14).
        timestamp: Unix timestamp (seconds since epoch, UTC).
        source_module: Name of the module that produced this event.
        confidence: Detection/classification confidence in [0.0, 1.0].
        bounding_box: Optional spatial location of the subject.
        metadata: Arbitrary extra data attached by the producing module.

    """

    event_type: str
    timestamp: float
    source_module: str
    confidence: float
    bounding_box: BoundingBox | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def now_timestamp() -> float:
        """Return current UTC time as a Unix timestamp."""
        return datetime.now(UTC).timestamp()


# ---------------------------------------------------------------------------
# Scene understanding
# ---------------------------------------------------------------------------


@dataclass
class DetectedObject:
    """A single object detected in a frame.

    Attributes:
        class_label: COCO category label string.
        confidence: Detection confidence in [0.0, 1.0].
        bounding_box: Location in the frame.
        tracking_id: Stable ID assigned by the object tracker, or None.
        depth_range: (near, far) normalised depth values in [0.0, 1.0], or None.

    """

    class_label: str
    confidence: float
    bounding_box: BoundingBox
    tracking_id: int | None = None
    depth_range: tuple[float, float] | None = None


@dataclass
class SceneResult:
    """Output of the scene understanding module.

    Attributes:
        scene_label: Predicted scene category (e.g. "office", "kitchen").
        confidence: Scene classification confidence in [0.0, 1.0].
        objects: All detected objects in the frame.
        spatial_relations: Pairwise relations as (obj_a, relation, obj_b).

    """

    scene_label: str
    confidence: float
    objects: list[DetectedObject]
    spatial_relations: list[tuple[str, str, str]]


# ---------------------------------------------------------------------------
# Depth estimation
# ---------------------------------------------------------------------------


@dataclass
class DepthMap:
    """Per-pixel relative depth map from monocular depth estimation.

    Attributes:
        data: float32 array of shape (H, W); values in [0.0, 1.0] where
              0.0 = nearest, 1.0 = farthest.
        confidence: Overall map confidence in [0.0, 1.0].
        is_null: True when the frame is too dark/featureless for estimation.

    """

    data: np.ndarray
    confidence: float
    is_null: bool = False


# ---------------------------------------------------------------------------
# OCR / document analysis
# ---------------------------------------------------------------------------


@dataclass
class OCRResult:
    """Text extraction result from the OCR engine.

    Attributes:
        text: Full extracted text string.
        words: Per-word details: [{text, bounding_box, confidence}].
        language: Detected or hinted language code (e.g. "en").
        reading_order_preserved: True when words are in reading order.

    """

    text: str
    words: list[dict[str, Any]]
    language: str
    reading_order_preserved: bool


@dataclass
class DocumentAnalysis:
    """Structural analysis of a document image.

    Attributes:
        ocr: Raw OCR extraction result.
        regions: Detected layout regions with type and bounding box.
        tables: Extracted tables as [table][row][col] string grids.
        form_fields: Extracted form fields as {label: value}.

    """

    ocr: OCRResult
    regions: list[dict[str, Any]]
    tables: list[list[list[str]]]
    form_fields: dict[str, str]


# ---------------------------------------------------------------------------
# Gesture recognition
# ---------------------------------------------------------------------------


@dataclass
class HandLandmarks:
    """21 MediaPipe hand keypoints.

    Attributes:
        keypoints: List of 21 (x, y, z) tuples in normalised image coords.
        confidence: Landmark detection confidence in [0.0, 1.0].
        hand_side: "left" or "right".

    """

    keypoints: list[tuple[float, float, float]]
    confidence: float
    hand_side: Literal["left", "right"]


@dataclass
class GestureResult:
    """Result of gesture classification for one hand.

    Attributes:
        gesture_name: Classified gesture label.
        confidence: Classification confidence in [0.0, 1.0].
        hand_landmarks: Underlying hand keypoints.
        is_held: True when the same gesture has been held for ≥500 ms.

    """

    gesture_name: str
    confidence: float
    hand_landmarks: HandLandmarks
    is_held: bool = False


# ---------------------------------------------------------------------------
# Pose estimation
# ---------------------------------------------------------------------------


@dataclass
class PoseKeypoint:
    """A single COCO-format body keypoint.

    Attributes:
        name: Keypoint name (e.g. "left_shoulder").
        x: Horizontal position in pixels.
        y: Vertical position in pixels.
        confidence: Visibility/confidence in [0.0, 1.0]; 0.0 = occluded.

    """

    name: str
    x: float
    y: float
    confidence: float


@dataclass
class PoseResult:
    """Full-body pose estimation result for one person.

    Attributes:
        keypoints: Exactly 17 COCO keypoints.
        person_id: Index of the detected person in the frame.
        posture_label: Rule-based posture classification, or None.

    """

    keypoints: list[PoseKeypoint]
    person_id: int
    posture_label: str | None


# ---------------------------------------------------------------------------
# Screen analysis
# ---------------------------------------------------------------------------


@dataclass
class UIElement:
    """A single UI element detected in a screenshot.

    Attributes:
        element_type: One of the 11 supported UI element types.
        bounding_box: Location in the screenshot.
        text: OCR-extracted text label, or None.
        is_interactive: True when the element accepts user input.
        layer_priority: Z-order priority; higher = more foreground.

    """

    element_type: str
    bounding_box: BoundingBox
    text: str | None
    is_interactive: bool
    layer_priority: int


@dataclass
class ScreenAnalysis:
    """Complete analysis of a UI screenshot.

    Attributes:
        elements: All detected UI elements.
        primary_content_region: Largest non-chrome area, or None.
        modal_detected: True when a modal dialog is visible.
        layout_json: Structured JSON consumed by the Computer Use Agent.

    """

    elements: list[UIElement]
    primary_content_region: BoundingBox | None
    modal_detected: bool
    layout_json: dict[str, Any]


# ---------------------------------------------------------------------------
# Visual question answering
# ---------------------------------------------------------------------------


@dataclass
class VQAResult:
    """Answer to a natural-language question about an image.

    Attributes:
        question: The original question string.
        answer: The model's answer string.
        confidence: Answer confidence in [0.0, 1.0].
        grounded_in_ocr: True when the answer references OCR output.
        not_visible: True when the answer cannot be determined from the image.

    """

    question: str
    answer: str
    confidence: float
    grounded_in_ocr: bool
    not_visible: bool = False


# ---------------------------------------------------------------------------
# Object tracking
# ---------------------------------------------------------------------------


@dataclass
class TrackingUpdate:
    """State update for a single tracked object.

    Attributes:
        tracking_id: Stable integer ID assigned by the tracker.
        class_label: COCO category label.
        bounding_box: Current location in the frame.
        frames_since_seen: Consecutive frames the object has been absent.
        is_new: True on the first frame this ID appears.
        is_lost: True when the ID is being released.

    """

    tracking_id: int
    class_label: str
    bounding_box: BoundingBox
    frames_since_seen: int
    is_new: bool
    is_lost: bool


# ---------------------------------------------------------------------------
# Activity recognition
# ---------------------------------------------------------------------------


@dataclass
class ActivityResult:
    """Activity classification result from a temporal frame buffer.

    Attributes:
        activity_label: Predicted activity category.
        confidence: Classification confidence in [0.0, 1.0].
        previous_label: Previous activity label, or None on first result.
        changed: True when activity_label differs from previous_label.

    """

    activity_label: str
    confidence: float
    previous_label: str | None
    changed: bool


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class VisionConfig(BaseModel):
    """Top-level configuration for the Vision System.

    All fields are validated at construction time; invalid values raise
    a ``ValidationError`` immediately (fail-fast).

    Attributes:
        detection_threshold: Minimum confidence for object detections [0.0, 1.0].
        enabled_modules: List of module names that are active.
        gpu_enabled: Whether to use CUDA execution provider.
        vram_budget_gb: Maximum GPU VRAM to use across all loaded models.

    """

    detection_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    enabled_modules: list[str] = Field(default_factory=list)
    gpu_enabled: bool = True
    vram_budget_gb: float = Field(default=4.0, gt=0.0)

    @field_validator("detection_threshold")
    @classmethod
    def _validate_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            msg = f"detection_threshold must be in [0.0, 1.0], got {v}"
            raise ValueError(msg)
        return v

    @field_validator("vram_budget_gb")
    @classmethod
    def _validate_vram(cls, v: float) -> float:
        if v <= 0.0:
            msg = f"vram_budget_gb must be positive, got {v}"
            raise ValueError(msg)
        return v

    model_config = {"frozen": False}
