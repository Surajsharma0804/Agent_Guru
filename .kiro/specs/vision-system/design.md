# Design Document: Vision System

## Overview

This document defines the architecture and implementation strategy for the Agent Guru Vision System — the broad computer vision engine responsible for all visual understanding beyond facial identity recognition. It covers scene understanding, depth estimation, OCR, handwriting recognition, gesture and pose recognition, screen analysis for autonomous computer use, visual question answering, multi-object tracking, activity recognition, and privacy-preserving on-device processing.

The Vision System is a key competitive differentiator. No competitor (Alexa, Siri, Google Assistant, ChatGPT, Copilot, Gemini) offers real-time scene understanding, gesture-based touchless control, autonomous screen navigation, and VQA in a single privacy-first, GPU-accelerated engine.

The design follows Agent Guru's Python-first architecture (Python 3.11+, PyTorch 2.0+, asyncio, ONNX Runtime GPU) and integrates with the existing `Agent_Guru/` package structure.

### Design Goals

1. **Real-Time Performance**: All interactive modules meet latency targets on GPU; graceful CPU fallback
2. **Privacy-First**: All inference on-device; raw frames never transmitted externally
3. **Composable Architecture**: Each vision module is independently enable/disable-able
4. **Event-Driven Integration**: Async Vision Event Bus decouples producers from consumers
5. **GPU-Efficient**: Batched inference, ONNX Runtime CUDA provider, model LRU eviction
6. **Observable**: Prometheus metrics and structured logs for every module


## Architecture

### System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Camera / Screenshot Input                        │
│              (Platform Integration Layer abstraction)               │
└─────────────────────────────┬───────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       Frame Dispatcher                              │
│   Routes frames to active modules in parallel via asyncio tasks     │
└──┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┘
   ↓          ↓          ↓          ↓          ↓          ↓
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
│Scene │ │Depth │ │ OCR  │ │Gest. │ │Pose  │ │Screen│ │Activ.│
│Under.│ │Estim.│ │ Doc  │ │Recog.│ │Estim.│ │Anal. │ │Recog.│
└──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘
   └────────┴────────┴────────┴────────┴────────┴────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       Object Tracker                                │
│              (ByteTrack — assigns stable Tracking_IDs)              │
└─────────────────────────────┬───────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        VQA Engine                                   │
│         (CLIP / LLaVA / InternVL — on-device or cloud VLM)         │
└─────────────────────────────┬───────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       Privacy Filter                                │
│   Blurs off-task regions; anonymizes faces before any persistence   │
└─────────────────────────────┬───────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     Vision Event Bus                                │
│   Async pub/sub; delivers Vision_Events to all registered subs      │
└──────────┬──────────────────┬──────────────────┬────────────────────┘
           ↓                  ↓                  ↓
  Computer Use Agent   Multi-Modal Fusion    Memory System
```

### Module Location Mapping

| Component | Module Path |
|-----------|-------------|
| Frame Dispatcher | `Agent_Guru/vision/dispatcher.py` |
| Scene Understanding | `Agent_Guru/vision/scene.py` |
| Depth Estimator | `Agent_Guru/vision/depth.py` |
| OCR + Document Analyzer | `Agent_Guru/vision/ocr.py` |
| Handwriting Recognizer | `Agent_Guru/vision/handwriting.py` |
| Gesture Recognizer | `Agent_Guru/vision/gesture.py` |
| Pose Estimator | `Agent_Guru/vision/pose.py` |
| Screen Analyzer | `Agent_Guru/vision/screen.py` |
| VQA Engine | `Agent_Guru/vision/vqa.py` |
| Object Tracker | `Agent_Guru/vision/tracker.py` |
| Activity Recognizer | `Agent_Guru/vision/activity.py` |
| Privacy Filter | `Agent_Guru/vision/privacy.py` |
| Vision Event Bus | `Agent_Guru/vision/bus.py` |
| GPU/Model Manager | `Agent_Guru/vision/model_manager.py` |
| Vision Engine (coordinator) | `Agent_Guru/vision/engine.py` |


## Components and Interfaces

### 1. Core Data Models

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal
import numpy as np
from datetime import datetime

@dataclass
class BoundingBox:
    x: float          # Top-left x (pixels)
    y: float          # Top-left y (pixels)
    width: float
    height: float

@dataclass
class VisionEvent:
    event_type: str   # See Requirement 12 for full enum
    timestamp: float  # Unix timestamp
    source_module: str
    confidence: float # 0.0–1.0
    bounding_box: BoundingBox | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class DetectedObject:
    class_label: str
    confidence: float
    bounding_box: BoundingBox
    tracking_id: int | None = None
    depth_range: tuple[float, float] | None = None  # (near, far) normalized 0–1

@dataclass
class SceneResult:
    scene_label: str
    confidence: float
    objects: list[DetectedObject]
    spatial_relations: list[tuple[str, str, str]]  # (obj_a, relation, obj_b)

@dataclass
class DepthMap:
    data: np.ndarray   # float32 array, same HxW as input frame, values in [0.0, 1.0]
    confidence: float
    is_null: bool = False  # True when frame is too dark/featureless

@dataclass
class OCRResult:
    text: str
    words: list[dict[str, Any]]  # [{text, bounding_box, confidence}]
    language: str
    reading_order_preserved: bool

@dataclass
class DocumentAnalysis:
    ocr: OCRResult
    regions: list[dict[str, Any]]   # [{type: heading|paragraph|table|form, bounding_box}]
    tables: list[list[list[str]]]   # [table][row][col]
    form_fields: dict[str, str]     # {label: value}

@dataclass
class HandLandmarks:
    keypoints: list[tuple[float, float, float]]  # 21 points (x, y, z)
    confidence: float
    hand_side: Literal["left", "right"]

@dataclass
class GestureResult:
    gesture_name: str
    confidence: float
    hand_landmarks: HandLandmarks
    is_held: bool = False  # True when held >500ms

@dataclass
class PoseKeypoint:
    name: str
    x: float
    y: float
    confidence: float

@dataclass
class PoseResult:
    keypoints: list[PoseKeypoint]   # 17 COCO keypoints
    person_id: int
    posture_label: str | None       # "sitting"|"standing"|"lying_down"|"raising_hand"|None

@dataclass
class UIElement:
    element_type: str   # button|text_field|dropdown|checkbox|radio_button|link|menu_item|icon|scrollbar|tab|image
    bounding_box: BoundingBox
    text: str | None
    is_interactive: bool
    layer_priority: int  # Higher = more foreground (modal > toolbar > content)

@dataclass
class ScreenAnalysis:
    elements: list[UIElement]
    primary_content_region: BoundingBox | None
    modal_detected: bool
    layout_json: dict[str, Any]   # Structured JSON for Computer Use Agent

@dataclass
class VQAResult:
    question: str
    answer: str
    confidence: float
    grounded_in_ocr: bool   # True if answer references OCR output
    not_visible: bool = False  # True when answer cannot be determined from image

@dataclass
class TrackingUpdate:
    tracking_id: int
    class_label: str
    bounding_box: BoundingBox
    frames_since_seen: int
    is_new: bool
    is_lost: bool

@dataclass
class ActivityResult:
    activity_label: str
    confidence: float
    previous_label: str | None
    changed: bool
```

---

### 2. Frame Dispatcher

**Responsibility**: Receive raw frames from the camera/screenshot pipeline and fan out to all active vision modules in parallel using `asyncio.gather`.

```python
class FrameDispatcher:
    async def dispatch(self, frame: np.ndarray, frame_seq: int) -> None:
        """Fan out frame to all enabled modules concurrently."""

    def register_module(self, name: str, handler: Callable) -> None:
        """Register a vision module handler."""

    def enable_module(self, name: str) -> None: ...
    def disable_module(self, name: str) -> None: ...
    def get_active_modules(self) -> list[str]: ...
```

**Key Design Decisions**:
- Each module handler runs as an independent `asyncio.Task`; failures in one module do not block others
- Frame sequence number (`frame_seq`) is monotonically increasing; used for tracking and activity temporal ordering
- When no subscribers are registered for a module's output, the module is suspended (not dispatched to)
- Frame queue depth > 2 triggers GPU batch accumulation before inference

---

### 3. Scene Understanding (scene.py)

**Responsibility**: Classify scene type and detect objects with bounding boxes, spatial relationships, and depth annotations.

```python
class SceneClassifier:
    async def classify(self, frame: np.ndarray) -> tuple[str, float]:
        """Returns (scene_label, confidence). Returns ("uncertain", conf) when conf < 0.4."""

class ObjectDetector:
    async def detect(self, frame: np.ndarray) -> list[DetectedObject]:
        """YOLOv8/DETR inference. Filters by Detection_Threshold. Supports 80+ COCO categories."""

class SpatialReasoner:
    def compute_relations(
        self, objects: list[DetectedObject], depth_map: DepthMap | None
    ) -> list[tuple[str, str, str]]:
        """Returns list of (obj_a_label, relation, obj_b_label) for all pairs."""
```

**Key Design Decisions**:
- YOLOv8n/s exported to ONNX for inference; DETR as optional higher-accuracy alternative
- Scene taxonomy: 30 categories (indoor/outdoor subtypes: office, kitchen, bedroom, street, park, etc.)
- Spatial relations: left_of, right_of, above, below, near, far, occluding, occluded_by
- Uncertain label emitted when scene confidence < 0.4 (Requirement 1.7)
- mAP ≥ 50% on COCO benchmark (Requirement 1.3)
- Sustained 15 FPS GPU / 5 FPS CPU (Requirements 1.5, 1.6)

---

### 4. Depth Estimator (depth.py)

**Responsibility**: Produce a per-pixel relative depth map from a single RGB frame using monocular depth estimation.

```python
class DepthEstimator:
    async def estimate(self, frame: np.ndarray) -> DepthMap:
        """MiDaS/Depth Anything ONNX inference. Returns null DepthMap on dark/featureless frames."""
```

**Key Design Decisions**:
- MiDaS v3.1 (DPT-Large) or Depth Anything v2 exported to ONNX
- Output normalized to [0.0, 1.0]: 0.0 = nearest, 1.0 = farthest (Requirement 2.3)
- Null DepthMap with low-confidence warning when frame mean brightness < 20 or variance < 5 (Requirement 2.6)
- Latency target: ≤100ms per frame on GPU (Requirement 2.2)
- No stereo camera or depth sensor required (Requirement 2.5)

---

### 5. OCR Engine and Document Analyzer (ocr.py)

**Responsibility**: Extract text from images, screenshots, and documents with structural analysis.

```python
class OCREngine:
    async def extract(self, image: np.ndarray, language_hint: str = "auto") -> OCRResult:
        """PaddleOCR inference. Applies super-resolution if DPI < 72. Preserves reading order."""

class DocumentAnalyzer:
    async def analyze(self, image: np.ndarray) -> DocumentAnalysis:
        """LayoutLMv3/DocTR for structure detection. Extracts tables and form fields."""
```

**Key Design Decisions**:
- PaddleOCR v4 as primary engine; Tesseract as CPU fallback
- 10+ language support: en, es, fr, de, zh, ja, ko, pt, it, ar (Requirement 3.3)
- Super-resolution preprocessing (Real-ESRGAN) when estimated DPI < 72 (Requirement 3.8)
- Reading order preserved via bounding box sort (top-to-bottom, left-to-right with column detection)
- CER < 5% on printed text under normal lighting (Requirement 3.2)
- Latency ≤200ms per image on GPU (Requirement 3.7)
- Table extraction: cells identified by line detection + OCR; output as `list[list[str]]`
- Form field extraction: label-value pairing via proximity and alignment heuristics

---

### 6. Handwriting Recognizer (handwriting.py)

**Responsibility**: Transcribe handwritten text from images, whiteboards, and physical paper.

```python
class HandwritingRecognizer:
    async def recognize(self, image: np.ndarray) -> OCRResult:
        """Detects handwritten regions, corrects perspective, transcribes. WER < 15% for legible text."""

    def classify_region(self, image: np.ndarray) -> Literal["printed", "handwritten", "mixed"]:
        """Distinguish printed vs handwritten regions."""
```

**Key Design Decisions**:
- TrOCR (Microsoft) fine-tuned on IAM Handwriting Database for cursive and print styles
- Perspective correction: homography estimation via corner detection before recognition (Requirement 4.3)
- Confidence < 0.3 → mark region as "unreadable" rather than returning low-confidence text (Requirement 4.5)
- WER < 15% for legible handwriting (Requirement 4.1)
- Latency ≤500ms per image (Requirement 4.4)

---

### 7. Gesture Recognizer (gesture.py)

**Responsibility**: Detect hand landmarks and classify gestures for touchless control.

```python
class GestureRecognizer:
    async def process_frame(self, frame: np.ndarray) -> list[GestureResult]:
        """MediaPipe Hands inference. Returns results for up to 2 hands. Discards if landmark conf < 0.5."""

    async def detect_held_gesture(
        self, gesture_history: list[GestureResult], window_ms: int = 500
    ) -> GestureResult | None:
        """Returns gesture with is_held=True if same gesture held for window_ms."""
```

**Key Design Decisions**:
- MediaPipe Hands (21 keypoints per hand) as primary; ONNX export for GPU acceleration
- 10 supported gestures: open_palm, closed_fist, thumbs_up, thumbs_down, pointing_index, peace_sign, ok_sign, swipe_left, swipe_right, stop (Requirement 5.2)
- Confidence < 0.5 on landmarks → discard frame, no event emitted (Requirement 5.8)
- Confidence ≥ 0.8 on gesture classification → emit `gesture_detected` event (Requirement 5.3)
- Held gesture: same classification for ≥500ms → emit `gesture_held` event (Requirement 5.7)
- Accuracy ≥ 92% across gesture set in normal lighting (Requirement 5.4)
- Sustained ≥20 FPS (Requirement 5.5)

---

### 8. Pose Estimator (pose.py)

**Responsibility**: Estimate full-body skeleton keypoints for activity and posture analysis.

```python
class PoseEstimator:
    async def estimate(self, frame: np.ndarray) -> list[PoseResult]:
        """MediaPipe Pose / OpenPose ONNX. Returns up to 5 persons. Marks occluded keypoints conf=0."""
```

**Key Design Decisions**:
- MediaPipe Pose (33 keypoints, COCO-17 subset reported) as primary
- Up to 5 simultaneous subjects (Requirement 6.4)
- Occluded keypoints: confidence = 0.0, position estimated from skeleton geometry (Requirement 6.5)
- Posture classification: rule-based on keypoint geometry (sitting, standing, lying_down, raising_hand)
- MPJPE < 80mm on standard benchmarks (Requirement 6.2)
- Sustained ≥15 FPS on GPU (Requirement 6.3)

---

### 9. Screen Analyzer (screen.py)

**Responsibility**: Parse UI screenshots to identify all interactive elements for the Computer Use Agent.

```python
class ScreenAnalyzer:
    async def analyze(self, screenshot: np.ndarray) -> ScreenAnalysis:
        """YOLO + OCR + CLIP pipeline. Deterministic output. ≤300ms on GPU for 1920x1080."""
```

**Key Design Decisions**:
- Detection pipeline: YOLOv8 fine-tuned on UI element dataset → OCR on each detected element → CLIP for semantic label disambiguation
- 11 element types: button, text_field, dropdown, checkbox, radio_button, link, menu_item, icon, scrollbar, tab, image (Requirement 7.2)
- Deterministic: same screenshot → identical output (no stochastic sampling) (Requirement 7.9)
- Modal detection: topmost layer identified by z-order heuristics (overlay coverage > 30% of screen)
- Primary content region: largest non-chrome area identified by layout analysis
- Precision ≥ 85%, Recall ≥ 80% on UI benchmarks (Requirement 7.3)
- Latency ≤300ms for 1920×1080 on GPU (Requirement 7.4)
- Output: structured `ScreenAnalysis.layout_json` consumed directly by Computer Use Agent

---

### 10. VQA Engine (vqa.py)

**Responsibility**: Answer natural language questions about images using a vision-language model.

```python
class VQAEngine:
    async def answer(self, image: np.ndarray, question: str) -> VQAResult:
        """On-device VLM (desktop) or cloud VLM (mobile). Uses OCR output for text-grounded answers."""
```

**Key Design Decisions**:
- Desktop: LLaVA-1.6 or InternVL2 quantized (4-bit GGUF) via llama.cpp for on-device inference
- Mobile: route to configured cloud VLM provider (OpenAI GPT-4V, Gemini Vision) (Requirement 8.8)
- OCR integration: when question involves text in image, OCR result injected into VLM prompt (Requirement 8.6)
- Not-visible response: VLM instructed via system prompt to respond "I cannot determine that from the image" rather than hallucinate (Requirement 8.4)
- Accuracy ≥ 65% on VQAv2 benchmark (Requirement 8.2)
- Latency ≤2s on GPU for images up to 1920×1080 (Requirement 8.3)
- Supported question types: identity, count, color, spatial position, text content, scene context (Requirement 8.5)

---

### 11. Object Tracker (tracker.py)

**Responsibility**: Assign and maintain stable Tracking_IDs for detected objects across video frames.

```python
class ObjectTracker:
    def update(self, detections: list[DetectedObject], frame_seq: int) -> list[TrackingUpdate]:
        """ByteTrack update step. Returns tracking updates including new/lost events."""
```

**Key Design Decisions**:
- ByteTrack algorithm: two-stage association (high-confidence first, then low-confidence)
- Tracking_ID persists through occlusion for up to 30 consecutive frames (Requirement 9.4)
- Re-identification: same Tracking_ID reassigned if object reappears within 30 frames (Requirement 9.5)
- Up to 20 simultaneous objects without FPS degradation (Requirement 9.6)
- `object_appeared` event on new Tracking_ID; `object_disappeared` on release (Requirement 9.7)
- Tracking update latency ≤10ms per frame on GPU (Requirement 9.8)
- MOTA ≥ 60% on standard benchmarks (Requirement 9.3)

---

### 12. Activity Recognizer (activity.py)

**Responsibility**: Classify human activities from sequences of video frames.

```python
class ActivityRecognizer:
    async def classify(self, frame_buffer: list[np.ndarray]) -> ActivityResult:
        """SlowFast/VideoMAE inference on ≥8 frame buffer. Updates at ≥1Hz."""
```

**Key Design Decisions**:
- SlowFast R50 or VideoMAE-S exported to ONNX; minimum 8-frame temporal window (Requirement 10.1)
- 11 activity categories: walking, running, sitting, standing, typing, eating, drinking, reading, writing, phone_use, idle (Requirement 10.2)
- Top-1 accuracy ≥ 75% on Kinetics-400 subset (Requirement 10.3)
- Confidence ≥ 0.7 → emit `activity_detected` event (Requirement 10.4)
- Update rate ≥ 1Hz during continuous operation (Requirement 10.5)
- `activity_changed` event emitted with previous + new labels on transition (Requirement 10.6)

---

### 13. Privacy Filter (privacy.py)

**Responsibility**: Anonymize frames before any persistence; blur off-task regions.

```python
class PrivacyFilter:
    async def anonymize_faces(self, frame: np.ndarray, face_boxes: list[BoundingBox]) -> np.ndarray:
        """Gaussian blur on all detected face regions. ≤20ms per frame."""

    async def blur_off_task(
        self, frame: np.ndarray, relevant_region: BoundingBox | None
    ) -> np.ndarray:
        """Blur all pixels outside relevant_region. If None, blur entire frame."""
```

**Key Design Decisions**:
- Face anonymization: Gaussian blur (σ=15) applied to all face bounding boxes from GuruVision pipeline
- Off-task blurring: only the relevant sub-region (e.g., detected object) passed downstream unblurred
- Raw pixel data never written to disk or memory beyond current pipeline (Requirement 11.4)
- Anonymization latency ≤20ms per frame (Requirement 11.7)
- Camera disable config: all modules return empty results without error (Requirement 11.5)
- Active module indicator: real-time status exposed via `VisionEngine.get_active_modules()` (Requirement 11.6)

---

### 14. Vision Event Bus (bus.py)

**Responsibility**: Async pub/sub delivery of Vision_Events to all registered subscribers.

```python
class VisionEventBus:
    async def publish(self, event: VisionEvent) -> None:
        """Deliver to all matching subscribers within 10ms."""

    def subscribe(
        self,
        callback: Callable[[VisionEvent], Awaitable[None]],
        event_types: list[str] | None = None,
        min_confidence: float = 0.0,
        source_module: str | None = None,
    ) -> str:
        """Returns subscription_id. Filters applied before delivery."""

    def unsubscribe(self, subscription_id: str) -> None: ...

    async def request(self, request_type: str, payload: dict[str, Any]) -> Any:
        """Synchronous request-response for one-shot queries (VQA, screenshot analysis)."""
```

**Key Design Decisions**:
- Delivery guarantee: all subscribers notified within 10ms of event emission (Requirement 12.2)
- Filter support: by event_type, min_confidence, source_module (Requirement 12.5)
- Module suspension: when no subscribers for a module, dispatcher skips it (Requirement 12.6)
- Synchronous request-response API for VQA and screenshot analysis (Requirement 12.7)
- Standalone importability: no other Agent Guru components required at import time (Requirement 12.8)
- Supported event types: scene_classified, object_detected, object_appeared, object_disappeared, gesture_detected, gesture_held, activity_detected, activity_changed, text_extracted, ui_elements_detected, vqa_answered, pose_estimated (Requirement 12.4)

---

### 15. GPU/Model Manager (model_manager.py)

**Responsibility**: Load, cache, and evict ONNX models; manage GPU VRAM budget.

```python
class ModelManager:
    async def load(self, model_name: str) -> ort.InferenceSession:
        """Load model with CUDA provider if GPU available, else CPU. LRU eviction when VRAM > 4GB."""

    async def evict_lru(self) -> None:
        """Evict least-recently-used model from VRAM."""

    def get_provider(self) -> str:
        """Returns 'CUDAExecutionProvider' or 'CPUExecutionProvider'."""

    async def batch_infer(
        self, model_name: str, frames: list[np.ndarray]
    ) -> list[np.ndarray]:
        """Batch frames when queue depth > 2 for GPU efficiency."""
```

**Key Design Decisions**:
- CUDA provider when GPU detected at startup (Requirement 13.1); CPU provider otherwise (Requirement 13.2)
- Batching: queue depth > 2 → accumulate and batch for GPU inference (Requirement 13.3)
- GPU utilization target > 70% during sustained active processing (Requirement 13.4)
- VRAM budget: ≤4GB total across all loaded models (Requirement 13.5)
- LRU eviction when VRAM budget exceeded (Requirement 13.6)
- Full initialization ≤10s on GPU-equipped systems (Requirement 13.8)

---

### 16. Vision Engine Coordinator (engine.py)

**Responsibility**: Top-level coordinator; initializes all modules, manages lifecycle, exposes public API.

```python
class VisionEngine:
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def process_frame(self, frame: np.ndarray) -> None: ...
    async def analyze_screenshot(self, screenshot: np.ndarray) -> ScreenAnalysis: ...
    async def answer_question(self, image: np.ndarray, question: str) -> VQAResult: ...
    def get_active_modules(self) -> list[str]: ...
    def get_event_bus(self) -> VisionEventBus: ...
```


## Correctness Properties

The following 42 correctness properties are validated using Hypothesis property-based tests. All tests live in `Agent_Guru/vision/tests/`.

### Scene Understanding Properties

**Property 1: Object detection confidence threshold**
For any frame and any Detection_Threshold T in [0.0, 1.0], all returned DetectedObjects have confidence ≥ T.
```
∀ frame, T: detect(frame, threshold=T) → all(obj.confidence >= T for obj in result)
```

**Property 2: Scene uncertain label on low confidence**
When the scene classifier's raw top-1 score is below 0.4, the returned label is always "uncertain".
```
∀ frame: raw_score < 0.4 → classify(frame).label == "uncertain"
```

**Property 3: Spatial relations symmetry**
For every (A, left_of, B) relation, there exists a corresponding (B, right_of, A) relation, and similarly for above/below pairs.
```
∀ (a, "left_of", b) ∈ relations → (b, "right_of", a) ∈ relations
```

**Property 4: Scene classification latency**
For any valid frame, scene classification completes within 50ms on GPU.
```
∀ frame: elapsed(classify(frame)) ≤ 50ms
```

### Depth Estimation Properties

**Property 5: Depth map value range**
All values in a non-null DepthMap are in [0.0, 1.0].
```
∀ frame: depth_map = estimate(frame); not depth_map.is_null → all(0.0 ≤ v ≤ 1.0 for v in depth_map.data.flat)
```

**Property 6: Null depth map on dark frames**
When mean frame brightness < 20, the returned DepthMap has is_null=True.
```
∀ frame: mean(frame) < 20 → estimate(frame).is_null == True
```

**Property 7: Depth map spatial resolution**
The DepthMap data array has the same height and width as the input frame.
```
∀ frame (H×W): estimate(frame).data.shape == (H, W)
```

**Property 8: Depth estimation latency**
For any valid frame, depth estimation completes within 100ms on GPU.
```
∀ frame: elapsed(estimate(frame)) ≤ 100ms
```

### OCR Properties

**Property 9: OCR text extraction non-empty on text-containing images**
For any image synthetically generated to contain at least one word, the OCR result text is non-empty.
```
∀ image with_text: extract(image).text != ""
```

**Property 10: OCR bounding box containment**
Every word bounding box returned by OCR is fully contained within the image dimensions.
```
∀ word in extract(image).words: 0 ≤ word.bbox.x and word.bbox.x + word.bbox.width ≤ image.width
```

**Property 11: OCR reading order preservation**
The concatenated text of words in returned order matches the expected top-to-bottom, left-to-right reading order for single-column documents.
```
∀ single_column_image: words_in_order(extract(image)) == expected_reading_order
```

**Property 12: OCR latency**
For any image up to 1920×1080, OCR extraction completes within 200ms on GPU.
```
∀ image (≤1920×1080): elapsed(extract(image)) ≤ 200ms
```

**Property 13: Document table extraction round-trip**
For any synthetically generated table image, the extracted table structure has the correct number of rows and columns.
```
∀ table_image (R rows, C cols): len(analyze(table_image).tables[0]) == R and len(analyze(table_image).tables[0][0]) == C
```

### Handwriting Recognition Properties

**Property 14: Handwriting unreadable on very low confidence**
When the recognizer's internal confidence is below 0.3, the returned text is marked as unreadable rather than a low-confidence transcription.
```
∀ image: internal_conf < 0.3 → recognize(image).text == "[unreadable]"
```

**Property 15: Handwriting latency**
For any image up to 1920×1080, handwriting recognition completes within 500ms.
```
∀ image: elapsed(recognize(image)) ≤ 500ms
```

### Gesture Recognition Properties

**Property 16: Gesture confidence threshold enforcement**
No gesture event is emitted when hand landmark confidence is below 0.5.
```
∀ frame: landmark_conf < 0.5 → process_frame(frame) == []
```

**Property 17: Gesture event confidence gate**
All emitted GestureResults have confidence ≥ 0.8 when used to trigger a gesture_detected event.
```
∀ result in process_frame(frame): result.confidence >= 0.8 (for event emission)
```

**Property 18: Held gesture detection**
A gesture held for ≥500ms produces a GestureResult with is_held=True; a gesture held for <500ms produces is_held=False.
```
∀ gesture_history: duration ≥ 500ms → detect_held_gesture(history).is_held == True
∀ gesture_history: duration < 500ms → detect_held_gesture(history) is None or .is_held == False
```

**Property 19: Gesture frame rate**
Gesture processing sustains ≥20 FPS on GPU.
```
∀ continuous_stream: fps(process_frame) ≥ 20
```

### Pose Estimation Properties

**Property 20: Pose keypoint count**
Every PoseResult contains exactly 17 keypoints (COCO format).
```
∀ frame with_person: len(estimate(frame)[0].keypoints) == 17
```

**Property 21: Occluded keypoint confidence**
Keypoints marked as occluded have confidence == 0.0.
```
∀ keypoint: keypoint.is_occluded → keypoint.confidence == 0.0
```

**Property 22: Multi-person limit**
The pose estimator returns at most 5 PoseResults per frame.
```
∀ frame: len(estimate(frame)) ≤ 5
```

### Screen Analysis Properties

**Property 23: Screen analysis determinism**
Analyzing the same screenshot twice returns identical ScreenAnalysis results.
```
∀ screenshot: analyze(screenshot) == analyze(screenshot)
```

**Property 24: UI element bounding box containment**
All detected UIElement bounding boxes are fully within the screenshot dimensions.
```
∀ element in analyze(screenshot).elements: bbox_within(element.bounding_box, screenshot.shape)
```

**Property 25: Screen analysis latency**
For any 1920×1080 screenshot, analysis completes within 300ms on GPU.
```
∀ screenshot (1920×1080): elapsed(analyze(screenshot)) ≤ 300ms
```

**Property 26: Modal layer priority**
When a modal dialog is detected, all its UIElements have higher layer_priority than non-modal elements.
```
∀ analysis: analysis.modal_detected → all(e.layer_priority > max_non_modal_priority for e in modal_elements)
```

### VQA Properties

**Property 27: Not-visible response on unanswerable questions**
When the VLM cannot determine the answer from the image, VQAResult.not_visible is True and the answer contains an explicit "cannot determine" statement.
```
∀ (image, unanswerable_question): answer(image, q).not_visible == True
```

**Property 28: VQA latency**
For any image up to 1920×1080 and any question, VQA completes within 2s on GPU.
```
∀ (image, question): elapsed(answer(image, question)) ≤ 2000ms
```

**Property 29: OCR-grounded text answers**
When the question asks about text visible in the image, grounded_in_ocr is True.
```
∀ (image_with_text, text_question): answer(image, q).grounded_in_ocr == True
```

### Object Tracking Properties

**Property 30: Tracking ID persistence through occlusion**
A tracked object's Tracking_ID is preserved for up to 30 consecutive frames of absence.
```
∀ track: frames_since_seen ≤ 30 → tracking_id unchanged
```

**Property 31: Tracking ID re-assignment on reappearance**
An object that reappears within 30 frames receives the same Tracking_ID it had before disappearing.
```
∀ track: reappears_within(30_frames) → same tracking_id
```

**Property 32: Tracking update latency**
Tracker update completes within 10ms per frame on GPU.
```
∀ frame: elapsed(update(detections, frame_seq)) ≤ 10ms
```

**Property 33: Object appeared/disappeared events**
Every new Tracking_ID assignment produces an object_appeared event; every Tracking_ID release produces an object_disappeared event.
```
∀ new_id: object_appeared ∈ events
∀ released_id: object_disappeared ∈ events
```

### Activity Recognition Properties

**Property 34: Activity classification requires minimum frame buffer**
Activity classification is not attempted on fewer than 8 frames; returns None when buffer is insufficient.
```
∀ buffer: len(buffer) < 8 → classify(buffer) is None
```

**Property 35: Activity changed event on transition**
When activity label changes between consecutive classifications, an activity_changed event is emitted with both previous and new labels.
```
∀ (prev, curr): prev.label != curr.label → activity_changed event with {previous: prev.label, new: curr.label}
```

**Property 36: Activity update rate**
Activity classification updates at ≥1Hz during continuous operation.
```
∀ continuous_stream: update_rate(classify) ≥ 1.0 Hz
```

### Privacy Filter Properties

**Property 37: Face anonymization completeness**
After anonymization, no face bounding box region in the output frame has pixel values matching the original (i.e., blur was applied).
```
∀ (frame, face_boxes): anonymize_faces(frame, face_boxes)[face_region] ≠ frame[face_region]
```

**Property 38: Anonymization latency**
Face anonymization completes within 20ms per frame.
```
∀ frame: elapsed(anonymize_faces(frame, boxes)) ≤ 20ms
```

**Property 39: Camera disable returns empty results**
When camera access is disabled in configuration, all vision modules return empty/null results without raising exceptions.
```
∀ module: camera_disabled → module.process(frame) returns empty_result (no exception)
```

### Vision Event Bus Properties

**Property 40: Event delivery latency**
All subscribers receive a published event within 10ms of publication.
```
∀ event: max(delivery_time(sub, event) for sub in subscribers) ≤ 10ms
```

**Property 41: Subscriber filter correctness**
A subscriber with event_type filter T never receives events of a different type.
```
∀ subscriber(filter=T), event(type=E): E != T → subscriber not called
```

**Property 42: Module suspension when no subscribers**
When no subscribers are registered for a module's output, the Frame Dispatcher does not invoke that module.
```
∀ module: len(subscribers_for(module)) == 0 → module not dispatched to
```


## Error Handling

| Scenario | Behavior |
|----------|----------|
| Model file missing at startup | Log clear error, disable only affected module, continue with remaining modules |
| ONNX inference exception | Log full stack trace, increment error counter metric, skip frame, continue |
| GPU OOM during inference | Evict LRU model, retry inference; if still OOM, fall back to CPU for that module |
| Frame too dark/featureless for depth | Return null DepthMap with is_null=True and low-confidence warning event |
| Hand landmark confidence < 0.5 | Discard frame silently; no gesture event emitted |
| VLM cannot answer question | Return VQAResult with not_visible=True; never hallucinate |
| Camera access disabled | All modules return empty results; no exceptions raised |
| Activity buffer < 8 frames | Return None; no activity event emitted |
| Subscriber callback raises exception | Log error, continue delivering to remaining subscribers |
| Config value out of range | Fail fast at startup with descriptive error identifying the invalid field |
| Hot-reload config invalid | Reject new config, retain previous valid config, log warning |

## Testing Strategy

### Test Location
All tests in `Agent_Guru/vision/tests/`:
- `test_scene.py` — unit tests for SceneClassifier, ObjectDetector, SpatialReasoner
- `test_depth.py` — unit tests for DepthEstimator
- `test_ocr.py` — unit tests for OCREngine, DocumentAnalyzer
- `test_handwriting.py` — unit tests for HandwritingRecognizer
- `test_gesture.py` — unit tests for GestureRecognizer
- `test_pose.py` — unit tests for PoseEstimator
- `test_screen.py` — unit tests for ScreenAnalyzer
- `test_vqa.py` — unit tests for VQAEngine
- `test_tracker.py` — unit tests for ObjectTracker
- `test_activity.py` — unit tests for ActivityRecognizer
- `test_privacy.py` — unit tests for PrivacyFilter
- `test_bus.py` — unit tests for VisionEventBus
- `test_engine.py` — integration tests for VisionEngine
- `test_properties.py` — all 42 Hypothesis property-based tests

### Test Markers
- `@pytest.mark.unit` — isolated module tests with mocked ONNX sessions
- `@pytest.mark.property` — Hypothesis PBT (max_examples=100)
- `@pytest.mark.integration` — full pipeline tests with real model stubs
- `@pytest.mark.slow` — benchmark/latency tests

### Mocking Strategy
- ONNX InferenceSession mocked via `unittest.mock.MagicMock` for unit tests
- Synthetic frame generation using `numpy.random` and PIL for property tests
- MediaPipe mocked with fixed landmark arrays for gesture/pose unit tests

## Performance Benchmarks

| Module | GPU Target | CPU Target | Metric |
|--------|-----------|-----------|--------|
| Scene Classification | ≤50ms | ≤200ms | 95th percentile |
| Object Detection | ≤50ms | ≤300ms | 95th percentile |
| Depth Estimation | ≤100ms | ≤500ms | 95th percentile |
| OCR Extraction | ≤200ms | ≤800ms | 95th percentile |
| Handwriting Recognition | ≤500ms | ≤2000ms | 95th percentile |
| Gesture Recognition | ≥20 FPS | ≥5 FPS | Sustained |
| Pose Estimation | ≥15 FPS | ≥3 FPS | Sustained |
| Screen Analysis (1080p) | ≤300ms | ≤1500ms | 95th percentile |
| VQA (1080p) | ≤2000ms | ≤8000ms | 95th percentile |
| Object Tracking Update | ≤10ms | ≤50ms | 95th percentile |
| Activity Classification | ≥1 Hz | ≥0.5 Hz | Update rate |
| Privacy Filter (face blur) | ≤20ms | ≤80ms | 95th percentile |
| Event Bus Delivery | ≤10ms | ≤10ms | 95th percentile |
| Full Initialization | ≤10s | ≤30s | Cold start |
| GPU VRAM Usage | ≤4GB | N/A | Peak |

## Configuration Schema

All configuration loaded from `vision_config.yaml` at startup. Example:

```yaml
vision:
  gpu_enabled: true
  vram_budget_gb: 4.0
  initialization_timeout_s: 10

  modules:
    scene_understanding:
      enabled: true
      model_path: "models/yolov8n.onnx"
      detection_threshold: 0.5
      frame_rate_target: 15

    depth_estimation:
      enabled: true
      model_path: "models/midas_v31.onnx"
      frame_rate_target: 10

    ocr:
      enabled: true
      languages: ["en", "es", "fr", "de", "zh", "ja", "ko", "pt", "it", "ar"]
      super_resolution_dpi_threshold: 72

    handwriting:
      enabled: true
      model_path: "models/trocr_handwritten.onnx"
      confidence_threshold: 0.3

    gesture:
      enabled: true
      landmark_confidence_threshold: 0.5
      gesture_confidence_threshold: 0.8
      held_gesture_ms: 500

    pose:
      enabled: true
      max_persons: 5

    screen_analysis:
      enabled: true
      model_path: "models/yolov8_ui.onnx"

    vqa:
      enabled: true
      on_device_model_path: "models/llava_1.6_q4.gguf"
      cloud_provider: "openai"  # fallback for mobile

    object_tracking:
      enabled: true
      max_objects: 20
      max_occlusion_frames: 30

    activity_recognition:
      enabled: true
      model_path: "models/slowfast_r50.onnx"
      min_frame_buffer: 8
      confidence_threshold: 0.7

    privacy_filter:
      enabled: true
      blur_sigma: 15
      anonymize_faces: true

  camera:
    enabled: true
    device_index: 0
    resolution: [1280, 720]
    fps: 30
```

