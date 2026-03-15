# Implementation Plan: Vision System

## Overview

Implement the Agent Guru Vision System — a real-time, privacy-first, GPU-accelerated computer vision engine covering scene understanding, depth estimation, OCR, handwriting recognition, gesture and pose recognition, screen analysis, VQA, multi-object tracking, activity recognition, and the Vision Event Bus. All 42 correctness properties are validated with Hypothesis property-based tests. All tasks are marked `[ ]` (not started).

## Tasks

- [ ] 1. Core Data Models and Package Scaffold (`Agent_Guru/vision/`)
  - [ ] 1.1 Create `Agent_Guru/vision/` package with `__init__.py` and `models.py`
    - Implement all shared dataclasses: `BoundingBox`, `VisionEvent`, `DetectedObject`, `SceneResult`, `DepthMap`, `OCRResult`, `DocumentAnalysis`, `HandLandmarks`, `GestureResult`, `PoseKeypoint`, `PoseResult`, `UIElement`, `ScreenAnalysis`, `VQAResult`, `TrackingUpdate`, `ActivityResult`
    - All dataclasses use Pydantic v2 or Python `dataclasses` with full type annotations
    - _Requirements: 12.3_

  - [ ] 1.2 Create `vision_config.yaml` schema and `Agent_Guru/vision/config.py`
    - Implement `VisionConfig` Pydantic model loading from YAML/TOML
    - Validate all fields at startup; fail fast with descriptive errors on invalid values
    - Implement hot-reload support for `detection_threshold` and `enabled` per module
    - Document all options with descriptions, types, valid ranges, and defaults
    - _Requirements: 15.1, 15.2, 15.4, 15.5, 15.6, 15.7_

  - [ ] 1.3 Create `Agent_Guru/vision/tests/` directory with `conftest.py`
    - Add pytest fixtures: synthetic frame generator, mock ONNX session, mock MediaPipe results
    - Configure pytest markers: `unit`, `property`, `integration`, `slow`
    - _Requirements: all_


- [ ] 2. GPU/Model Manager (`Agent_Guru/vision/model_manager.py`)
  - [ ] 2.1 Implement `ModelManager` with ONNX Runtime provider selection
    - Detect CUDA GPU at startup; load models with `CUDAExecutionProvider` if available, else `CPUExecutionProvider`
    - Implement LRU model cache with VRAM budget enforcement (≤4GB)
    - Implement `evict_lru()` to free least-recently-used model when budget exceeded
    - Implement `batch_infer()` accumulating frames when queue depth > 2
    - _Requirements: 13.1, 13.2, 13.3, 13.5, 13.6_

  - [ ] 2.2 Implement model loading lifecycle and initialization timeout
    - Full initialization (all enabled models loaded) must complete within 10s on GPU
    - Log clear error and disable affected module when model file is missing
    - Expose `get_provider()` returning current execution provider string
    - _Requirements: 13.8, 15.3_

  - [ ]* 2.3 Write property test for GPU VRAM budget enforcement
    - **Property: VRAM budget never exceeded**
    - Validates: Requirement 13.5

  - [ ]* 2.4 Write unit tests for `ModelManager`
    - Test CUDA/CPU provider selection, LRU eviction, batch accumulation, missing model handling
    - _Requirements: 13.1, 13.2, 13.6, 13.8_

- [ ] 3. Vision Event Bus (`Agent_Guru/vision/bus.py`)
  - [ ] 3.1 Implement `VisionEventBus` with async pub/sub
    - Implement `publish()` delivering to all matching subscribers within 10ms
    - Implement `subscribe()` with filters: event_type list, min_confidence, source_module
    - Implement `unsubscribe()` by subscription_id
    - Implement `request()` synchronous request-response for one-shot queries
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.7, 12.8_

  - [ ] 3.2 Implement module suspension when no subscribers
    - Track subscriber counts per module; signal Frame Dispatcher to skip modules with zero subscribers
    - _Requirements: 12.6_

  - [ ]* 3.3 Write property test for event delivery latency (Property 40)
    - **Property 40: Event delivery latency ≤10ms**
    - Validates: Requirement 12.2

  - [ ]* 3.4 Write property test for subscriber filter correctness (Property 41)
    - **Property 41: Subscriber filter correctness**
    - Validates: Requirement 12.5

  - [ ]* 3.5 Write property test for module suspension when no subscribers (Property 42)
    - **Property 42: Module suspension when no subscribers**
    - Validates: Requirement 12.6

  - [ ]* 3.6 Write unit tests for `VisionEventBus`
    - Test all event types, filter combinations, request-response, standalone importability
    - _Requirements: 12.1, 12.3, 12.4, 12.7, 12.8_

- [ ] 4. Frame Dispatcher (`Agent_Guru/vision/dispatcher.py`)
  - [ ] 4.1 Implement `FrameDispatcher` with parallel module fan-out
    - Fan out each frame to all enabled modules via `asyncio.gather`
    - Assign monotonically increasing `frame_seq` to each frame
    - Isolate module failures: exception in one module does not block others
    - Respect module suspension signals from VisionEventBus
    - _Requirements: 12.6, 13.3_

  - [ ] 4.2 Implement module enable/disable and GPU batch accumulation
    - Implement `enable_module()` / `disable_module()` / `get_active_modules()`
    - Accumulate frames in queue when depth > 2 before dispatching for GPU batch inference
    - _Requirements: 13.3, 13.7_

  - [ ]* 4.3 Write unit tests for `FrameDispatcher`
    - Test parallel dispatch, module isolation on failure, enable/disable, batch accumulation
    - _Requirements: 12.6, 13.3, 13.7_

- [ ] 5. Scene Understanding (`Agent_Guru/vision/scene.py`)
  - [ ] 5.1 Implement `ObjectDetector` with YOLOv8 ONNX inference
    - Load YOLOv8n/s ONNX model via `ModelManager`
    - Filter detections by configurable `Detection_Threshold`
    - Support ≥80 COCO object categories
    - Target mAP ≥50% on COCO benchmark
    - _Requirements: 1.2, 1.3, 1.8_

  - [ ] 5.2 Implement `SceneClassifier` with uncertain label logic
    - EfficientNet/ViT ONNX model for 30-category scene taxonomy
    - Return ("uncertain", conf) when top-1 confidence < 0.4
    - Latency ≤50ms per frame on GPU
    - _Requirements: 1.1, 1.7_

  - [ ] 5.3 Implement `SpatialReasoner` for pairwise object relations
    - Compute left_of, right_of, above, below, near, far, occluding, occluded_by for all detected pairs
    - Annotate each DetectedObject with depth range when DepthMap is available
    - _Requirements: 1.4, 2.4_

  - [ ]* 5.4 Write property test for object detection confidence threshold (Property 1)
    - **Property 1: All returned objects have confidence ≥ Detection_Threshold**
    - Validates: Requirement 1.2

  - [ ]* 5.5 Write property test for scene uncertain label on low confidence (Property 2)
    - **Property 2: Scene label is "uncertain" when raw score < 0.4**
    - Validates: Requirement 1.7

  - [ ]* 5.6 Write property test for spatial relations symmetry (Property 3)
    - **Property 3: Spatial relations are symmetric (left_of ↔ right_of, above ↔ below)**
    - Validates: Requirement 1.4

  - [ ]* 5.7 Write property test for scene classification latency (Property 4)
    - **Property 4: Scene classification completes within 50ms on GPU**
    - Validates: Requirement 1.1

  - [ ]* 5.8 Write unit tests for `ObjectDetector`, `SceneClassifier`, `SpatialReasoner`
    - Test threshold filtering, uncertain label, spatial relation computation, depth annotation
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_


- [ ] 6. Depth Estimator (`Agent_Guru/vision/depth.py`)
  - [ ] 6.1 Implement `DepthEstimator` with MiDaS/Depth Anything ONNX inference
    - Load MiDaS v3.1 or Depth Anything v2 ONNX model via `ModelManager`
    - Normalize output to [0.0, 1.0]: 0.0 = nearest, 1.0 = farthest
    - Return null DepthMap with low-confidence warning when mean brightness < 20 or variance < 5
    - Latency ≤100ms per frame on GPU
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7_

  - [ ]* 6.2 Write property test for depth map value range (Property 5)
    - **Property 5: All DepthMap values in [0.0, 1.0]**
    - Validates: Requirement 2.3

  - [ ]* 6.3 Write property test for null depth map on dark frames (Property 6)
    - **Property 6: is_null=True when mean brightness < 20**
    - Validates: Requirement 2.6

  - [ ]* 6.4 Write property test for depth map spatial resolution (Property 7)
    - **Property 7: DepthMap shape matches input frame shape**
    - Validates: Requirement 2.1

  - [ ]* 6.5 Write property test for depth estimation latency (Property 8)
    - **Property 8: Depth estimation completes within 100ms on GPU**
    - Validates: Requirement 2.2

  - [ ]* 6.6 Write unit tests for `DepthEstimator`
    - Test null map conditions, value normalization, latency, CPU fallback
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7_

- [ ] 7. OCR Engine and Document Analyzer (`Agent_Guru/vision/ocr.py`)
  - [ ] 7.1 Implement `OCREngine` with PaddleOCR and super-resolution preprocessing
    - Integrate PaddleOCR v4 as primary; Tesseract as CPU fallback
    - Support 10 languages: en, es, fr, de, zh, ja, ko, pt, it, ar
    - Apply Real-ESRGAN super-resolution preprocessing when estimated DPI < 72
    - Preserve reading order via bounding box sort (top-to-bottom, left-to-right with column detection)
    - Latency ≤200ms per image on GPU
    - _Requirements: 3.1, 3.2, 3.3, 3.7, 3.8, 3.9_

  - [ ] 7.2 Implement `DocumentAnalyzer` with LayoutLMv3/DocTR
    - Detect structural regions: headings, paragraphs, tables, form fields
    - Extract table contents as `list[list[str]]` (row × column)
    - Extract form fields as `dict[str, str]` (label → value)
    - _Requirements: 3.4, 3.5, 3.6_

  - [ ]* 7.3 Write property test for OCR text extraction non-empty (Property 9)
    - **Property 9: OCR returns non-empty text for images containing text**
    - Validates: Requirement 3.1

  - [ ]* 7.4 Write property test for OCR bounding box containment (Property 10)
    - **Property 10: All word bounding boxes contained within image dimensions**
    - Validates: Requirement 3.1

  - [ ]* 7.5 Write property test for OCR reading order preservation (Property 11)
    - **Property 11: Reading order preserved for single-column documents**
    - Validates: Requirement 3.9

  - [ ]* 7.6 Write property test for OCR latency (Property 12)
    - **Property 12: OCR extraction completes within 200ms on GPU**
    - Validates: Requirement 3.7

  - [ ]* 7.7 Write property test for document table extraction round-trip (Property 13)
    - **Property 13: Extracted table has correct row and column counts**
    - Validates: Requirement 3.5

  - [ ]* 7.8 Write unit tests for `OCREngine` and `DocumentAnalyzer`
    - Test multi-language extraction, super-resolution trigger, table/form extraction, CPU fallback
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

- [ ] 8. Handwriting Recognizer (`Agent_Guru/vision/handwriting.py`)
  - [ ] 8.1 Implement `HandwritingRecognizer` with TrOCR and perspective correction
    - Integrate TrOCR ONNX model fine-tuned on IAM Handwriting Database
    - Implement perspective correction via homography estimation before recognition
    - Implement `classify_region()` distinguishing printed vs handwritten regions
    - Return "[unreadable]" when internal confidence < 0.3
    - Latency ≤500ms per image
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 8.2 Write property test for handwriting unreadable on low confidence (Property 14)
    - **Property 14: Returns "[unreadable]" when confidence < 0.3**
    - Validates: Requirement 4.5

  - [ ]* 8.3 Write property test for handwriting latency (Property 15)
    - **Property 15: Handwriting recognition completes within 500ms**
    - Validates: Requirement 4.4

  - [ ]* 8.4 Write unit tests for `HandwritingRecognizer`
    - Test perspective correction, printed/handwritten classification, cursive and print styles
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [ ] 9. Checkpoint — Ensure all tests pass for tasks 1–8
  - Run full test suite; ensure all unit and property tests pass before proceeding.


- [ ] 10. Gesture Recognizer (`Agent_Guru/vision/gesture.py`)
  - [ ] 10.1 Implement `GestureRecognizer` with MediaPipe Hands
    - Integrate MediaPipe Hands (21 keypoints per hand); ONNX export for GPU acceleration
    - Support 10 gestures: open_palm, closed_fist, thumbs_up, thumbs_down, pointing_index, peace_sign, ok_sign, swipe_left, swipe_right, stop
    - Discard frame silently when hand landmark confidence < 0.5
    - Emit gesture_detected event only when gesture confidence ≥ 0.8
    - Support simultaneous detection of both hands
    - Sustain ≥20 FPS on GPU
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.8_

  - [ ] 10.2 Implement held gesture detection
    - Track gesture history per hand; emit gesture_held event when same gesture held ≥500ms
    - _Requirements: 5.7_

  - [ ]* 10.3 Write property test for gesture confidence threshold enforcement (Property 16)
    - **Property 16: No gesture event emitted when landmark confidence < 0.5**
    - Validates: Requirement 5.8

  - [ ]* 10.4 Write property test for gesture event confidence gate (Property 17)
    - **Property 17: All emitted gesture events have confidence ≥ 0.8**
    - Validates: Requirement 5.3

  - [ ]* 10.5 Write property test for held gesture detection (Property 18)
    - **Property 18: is_held=True iff gesture held ≥500ms**
    - Validates: Requirement 5.7

  - [ ]* 10.6 Write property test for gesture frame rate (Property 19)
    - **Property 19: Gesture processing sustains ≥20 FPS on GPU**
    - Validates: Requirement 5.5

  - [ ]* 10.7 Write unit tests for `GestureRecognizer`
    - Test all 10 gestures, dual-hand detection, held gesture timing, low-confidence discard
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

- [ ] 11. Pose Estimator (`Agent_Guru/vision/pose.py`)
  - [ ] 11.1 Implement `PoseEstimator` with MediaPipe Pose ONNX
    - Integrate MediaPipe Pose (17 COCO keypoints reported)
    - Support up to 5 simultaneous persons
    - Mark occluded keypoints with confidence = 0.0
    - Classify posture: sitting, standing, lying_down, raising_hand via keypoint geometry rules
    - Emit pose_estimated Vision_Event for each detected person
    - Sustain ≥15 FPS on GPU
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 11.2 Write property test for pose keypoint count (Property 20)
    - **Property 20: Every PoseResult contains exactly 17 keypoints**
    - Validates: Requirement 6.1

  - [ ]* 11.3 Write property test for occluded keypoint confidence (Property 21)
    - **Property 21: Occluded keypoints have confidence == 0.0**
    - Validates: Requirement 6.5

  - [ ]* 11.4 Write property test for multi-person limit (Property 22)
    - **Property 22: At most 5 PoseResults returned per frame**
    - Validates: Requirement 6.4

  - [ ]* 11.5 Write unit tests for `PoseEstimator`
    - Test posture classification rules, multi-person handling, partial occlusion, event emission
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ] 12. Screen Analyzer (`Agent_Guru/vision/screen.py`)
  - [ ] 12.1 Implement `ScreenAnalyzer` with YOLO + OCR + CLIP pipeline
    - Fine-tuned YOLOv8 for UI element detection (11 element types)
    - Run OCR on each detected element to extract text labels
    - Use CLIP for semantic label disambiguation
    - Identify primary content region and modal dialog layer
    - Produce deterministic output (no stochastic sampling)
    - Latency ≤300ms for 1920×1080 on GPU
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9_

  - [ ] 12.2 Implement structured JSON layout output for Computer Use Agent
    - Serialize `ScreenAnalysis` to `layout_json` dict consumable by Computer Use Agent
    - _Requirements: 7.8_

  - [ ]* 12.3 Write property test for screen analysis determinism (Property 23)
    - **Property 23: Same screenshot → identical ScreenAnalysis**
    - Validates: Requirement 7.9

  - [ ]* 12.4 Write property test for UI element bounding box containment (Property 24)
    - **Property 24: All UIElement bounding boxes within screenshot dimensions**
    - Validates: Requirement 7.1

  - [ ]* 12.5 Write property test for screen analysis latency (Property 25)
    - **Property 25: Analysis completes within 300ms for 1920×1080 on GPU**
    - Validates: Requirement 7.4

  - [ ]* 12.6 Write property test for modal layer priority (Property 26)
    - **Property 26: Modal elements have higher layer_priority than non-modal elements**
    - Validates: Requirement 7.7

  - [ ]* 12.7 Write unit tests for `ScreenAnalyzer`
    - Test all 11 element types, modal detection, primary content region, JSON output structure
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 7.9_

- [ ] 13. Checkpoint — Ensure all tests pass for tasks 10–12
  - Run full test suite; ensure all unit and property tests pass before proceeding.


- [ ] 14. VQA Engine (`Agent_Guru/vision/vqa.py`)
  - [ ] 14.1 Implement `VQAEngine` with on-device and cloud VLM routing
    - Desktop: LLaVA-1.6 or InternVL2 quantized (4-bit GGUF) via llama.cpp for on-device inference
    - Mobile: route to configured cloud VLM provider (OpenAI GPT-4V, Gemini Vision)
    - Inject OCR output into VLM prompt when question involves text in image
    - Return VQAResult with not_visible=True when answer cannot be determined; never hallucinate
    - Latency ≤2s on GPU for images up to 1920×1080
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

  - [ ]* 14.2 Write property test for not-visible response on unanswerable questions (Property 27)
    - **Property 27: not_visible=True and answer contains "cannot determine" for unanswerable questions**
    - Validates: Requirement 8.4

  - [ ]* 14.3 Write property test for VQA latency (Property 28)
    - **Property 28: VQA completes within 2s on GPU for images up to 1920×1080**
    - Validates: Requirement 8.3

  - [ ]* 14.4 Write property test for OCR-grounded text answers (Property 29)
    - **Property 29: grounded_in_ocr=True when question asks about text in image**
    - Validates: Requirement 8.6

  - [ ]* 14.5 Write unit tests for `VQAEngine`
    - Test on-device vs cloud routing, OCR injection, not-visible response, question type coverage
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

- [ ] 15. Object Tracker (`Agent_Guru/vision/tracker.py`)
  - [ ] 15.1 Implement `ObjectTracker` with ByteTrack algorithm
    - Two-stage association: high-confidence detections first, then low-confidence
    - Persist Tracking_ID through occlusion for up to 30 consecutive frames
    - Reassign same Tracking_ID when object reappears within 30 frames
    - Track up to 20 simultaneous objects without FPS degradation
    - Emit object_appeared event on new Tracking_ID; object_disappeared on release
    - Tracking update latency ≤10ms per frame on GPU
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

  - [ ]* 15.2 Write property test for tracking ID persistence through occlusion (Property 30)
    - **Property 30: Tracking_ID preserved for up to 30 frames of absence**
    - Validates: Requirement 9.4

  - [ ]* 15.3 Write property test for tracking ID re-assignment on reappearance (Property 31)
    - **Property 31: Same Tracking_ID reassigned when object reappears within 30 frames**
    - Validates: Requirement 9.5

  - [ ]* 15.4 Write property test for tracking update latency (Property 32)
    - **Property 32: Tracker update completes within 10ms per frame on GPU**
    - Validates: Requirement 9.8

  - [ ]* 15.5 Write property test for appeared/disappeared events (Property 33)
    - **Property 33: object_appeared on new ID; object_disappeared on released ID**
    - Validates: Requirement 9.7

  - [ ]* 15.6 Write unit tests for `ObjectTracker`
    - Test ByteTrack association, occlusion handling, re-identification, 20-object capacity
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

- [ ] 16. Activity Recognizer (`Agent_Guru/vision/activity.py`)
  - [ ] 16.1 Implement `ActivityRecognizer` with SlowFast/VideoMAE ONNX
    - Load SlowFast R50 or VideoMAE-S ONNX model via `ModelManager`
    - Require minimum 8-frame buffer; return None when buffer insufficient
    - Support 11 activity categories: walking, running, sitting, standing, typing, eating, drinking, reading, writing, phone_use, idle
    - Emit activity_detected event when confidence ≥ 0.7
    - Emit activity_changed event with previous + new labels on transition
    - Update rate ≥1Hz during continuous operation
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ]* 16.2 Write property test for minimum frame buffer requirement (Property 34)
    - **Property 34: Returns None when frame buffer < 8**
    - Validates: Requirement 10.1

  - [ ]* 16.3 Write property test for activity changed event on transition (Property 35)
    - **Property 35: activity_changed event emitted with both labels on transition**
    - Validates: Requirement 10.6

  - [ ]* 16.4 Write property test for activity update rate (Property 36)
    - **Property 36: Activity classification updates at ≥1Hz**
    - Validates: Requirement 10.5

  - [ ]* 16.5 Write unit tests for `ActivityRecognizer`
    - Test all 11 categories, buffer management, confidence gating, transition events
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [ ] 17. Privacy Filter (`Agent_Guru/vision/privacy.py`)
  - [ ] 17.1 Implement `PrivacyFilter` with face anonymization and off-task blurring
    - Apply Gaussian blur (σ=15) to all face bounding boxes from GuruVision pipeline
    - Blur all pixels outside the relevant sub-region when a task-specific region is provided
    - Blur entire frame when no relevant region specified
    - Anonymization latency ≤20ms per frame
    - _Requirements: 11.2, 11.3, 11.7_

  - [ ] 17.2 Implement camera disable config and active module indicator
    - When `camera.enabled: false`, all modules return empty results without raising exceptions
    - Expose `VisionEngine.get_active_modules()` for real-time status indicator
    - Ensure no raw pixel data written to disk or memory beyond current pipeline
    - _Requirements: 11.1, 11.4, 11.5, 11.6_

  - [ ]* 17.3 Write property test for face anonymization completeness (Property 37)
    - **Property 37: Face regions in output differ from original (blur applied)**
    - Validates: Requirement 11.3

  - [ ]* 17.4 Write property test for anonymization latency (Property 38)
    - **Property 38: Face anonymization completes within 20ms per frame**
    - Validates: Requirement 11.7

  - [ ]* 17.5 Write property test for camera disable returns empty results (Property 39)
    - **Property 39: All modules return empty results when camera disabled (no exceptions)**
    - Validates: Requirement 11.5

  - [ ]* 17.6 Write unit tests for `PrivacyFilter`
    - Test face blur application, off-task region blurring, camera disable behavior, no raw data persistence
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7_

- [ ] 18. Checkpoint — Ensure all tests pass for tasks 14–17
  - Run full test suite; ensure all unit and property tests pass before proceeding.


- [ ] 19. Observability and Diagnostics (`Agent_Guru/vision/observability.py`)
  - [ ] 19.1 Implement structured logging with structlog
    - Emit structured log entry for every Vision_Event: module name, latency, confidence, frame_seq
    - Support configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) without restart
    - Emit WARNING when any module's inference latency exceeds its target by >50%
    - Log full stack trace and continue on unhandled module exception
    - _Requirements: 14.1, 14.3, 14.4, 14.6_

  - [ ] 19.2 Implement Prometheus metrics
    - Expose metrics: `frames_processed_total`, `events_emitted_total`, `inference_latency_seconds` (histogram per module), `gpu_memory_bytes_used`, `active_modules_count`
    - Track and report p50, p95, p99 inference latency per module over rolling 60s window
    - Increment error counter metric on unhandled module exception
    - _Requirements: 14.2, 14.5, 14.6_

  - [ ]* 19.3 Write unit tests for observability
    - Test log emission per event, latency warning threshold, Prometheus metric registration, error counter increment
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

- [ ] 20. Vision Engine Coordinator (`Agent_Guru/vision/engine.py`)
  - [ ] 20.1 Implement `VisionEngine` as top-level coordinator
    - Initialize all modules in dependency order; enforce 10s initialization timeout on GPU
    - Implement `start()` / `stop()` lifecycle management
    - Implement `process_frame()` routing frames through Frame Dispatcher
    - Implement `analyze_screenshot()` and `answer_question()` as synchronous request-response
    - Expose `get_active_modules()` and `get_event_bus()`
    - _Requirements: 12.8, 13.7, 13.8_

  - [ ] 20.2 Implement GPU utilization monitoring and target enforcement
    - Monitor GPU utilization via `pynvml`; log WARNING when utilization < 70% during sustained active processing
    - _Requirements: 13.4_

  - [ ]* 20.3 Write integration tests for `VisionEngine`
    - Test full pipeline: frame → dispatcher → modules → event bus → subscriber delivery
    - Test screenshot analysis and VQA request-response paths
    - Test module enable/disable at runtime
    - Test graceful degradation when GPU unavailable
    - _Requirements: 12.1, 12.6, 12.7, 12.8, 13.1, 13.2, 13.7_

- [ ] 21. Configuration and Model Management Integration
  - [ ] 21.1 Wire `VisionConfig` into all modules
    - Each module reads its configuration from `VisionConfig` at initialization
    - Implement hot-reload: `detection_threshold` and `enabled` changes applied without restart
    - Validate all config values at startup; fail fast with descriptive errors
    - _Requirements: 15.1, 15.2, 15.4, 15.5_

  - [ ] 21.2 Implement missing model handling and config schema documentation
    - Log clear error identifying missing model file; disable only affected module
    - Generate `vision_config_schema.yaml` documenting all options with descriptions, types, valid ranges, defaults
    - _Requirements: 15.3, 15.6, 15.7_

  - [ ]* 21.3 Write unit tests for configuration management
    - Test missing model graceful disable, hot-reload application, invalid config fast-fail, default values
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7_

- [ ] 22. Final Integration and End-to-End Tests
  - [ ] 22.1 Write end-to-end integration tests for Computer Use Agent integration
    - Test: screenshot → ScreenAnalyzer → layout_json → Computer Use Agent consumption
    - Verify deterministic output across multiple runs
    - _Requirements: 7.8, 7.9_

  - [ ] 22.2 Write end-to-end integration tests for Multi-Modal Fusion integration
    - Test: frame → scene understanding → Vision_Event → Multi-Modal Fusion subscriber delivery
    - Verify event delivery latency ≤10ms end-to-end
    - _Requirements: 12.1, 12.2_

  - [ ] 22.3 Write end-to-end integration tests for Memory System integration
    - Test: Vision_Events stored as structured metadata (no raw pixel data) in Memory System
    - _Requirements: 11.4_

  - [ ] 22.4 Write performance benchmark suite
    - Benchmark all modules at GPU and CPU targets defined in design Performance Benchmarks table
    - Report p50, p95, p99 latency and sustained FPS for each module
    - _Requirements: 1.5, 1.6, 2.2, 3.7, 4.4, 5.5, 6.3, 7.4, 8.3, 9.8, 13.4_

  - [ ] 22.5 Final checkpoint — all 42 property tests and all unit/integration tests pass
    - Verify test coverage ≥80% across all `Agent_Guru/vision/` modules
    - Verify all Prometheus metrics registered and emitting correctly
    - Verify GPU VRAM usage ≤4GB with all modules active

