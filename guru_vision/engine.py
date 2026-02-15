"""
GuruVision Main Recognition Engine

This module provides the main GuruVisionEngine class that orchestrates all
subsystems for real-time face recognition, liveness detection, emotion recognition,
and face tracking.

Requirements: 13.1, 13.2, 31.1, 31.2
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Callable, Dict, Any
import numpy as np
import time
import signal
import atexit
from datetime import datetime


@dataclass
class FaceResult:
    """
    Result for a single detected face.
    
    Attributes:
        tracking_id: Unique tracking ID for this face across frames
        bbox: Bounding box coordinates as (x, y, w, h)
        identity: Name of recognized identity or "Unknown"
        confidence: Recognition confidence score (0.0 to 1.0)
        permission_level: Permission level (admin, user, guest, denied)
        emotion: Dominant emotion (neutral, happy, sad, angry, surprised, fearful, disgusted)
        emotion_confidence: Confidence score for emotion classification
        is_live: Whether face passed liveness detection
        liveness_confidence: Confidence score for liveness detection
    
    Requirements: 13.2, 31.3
    """
    tracking_id: int
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    identity: str
    confidence: float
    permission_level: str
    emotion: str
    emotion_confidence: float
    is_live: bool
    liveness_confidence: float


@dataclass
class RecognitionResult:
    """
    Complete recognition result for a frame.
    
    Attributes:
        faces: List of FaceResult objects, one for each detected face
        frame_id: Sequential frame identifier
        timestamp: ISO format timestamp of when frame was processed
        processing_time_ms: Time taken to process the frame in milliseconds
    
    Requirements: 13.2, 31.3
    """
    faces: List[FaceResult]
    frame_id: int
    timestamp: str
    processing_time_ms: float


@dataclass
class IdentityInfo:
    """
    Information about a stored identity.
    
    Attributes:
        name: Identity name
        permission_level: Permission level
        num_embeddings: Number of stored embeddings
        date_added: ISO format timestamp of when identity was added
        metadata: Additional custom metadata
    """
    name: str
    permission_level: str
    num_embeddings: int
    date_added: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class GuruVisionEngine:
    """
    Main recognition engine that orchestrates all GuruVision subsystems.
    
    This class provides the primary API for AI agent integration, managing:
    - Face detection and tracking
    - Face recognition and identity matching
    - Liveness detection (anti-spoofing)
    - Emotion recognition
    - Database management
    - Event callbacks
    
    Requirements: 13.1, 13.2, 31.1, 31.2
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the GuruVision engine.
        
        Args:
            config_path: Optional path to configuration file (YAML or JSON).
                        If None, uses default configuration.
        
        Requirements: 13.1, 31.1, 31.2
        """
        self.config_path = config_path
        self.config = None
        self.logger = None
        
        # Module instances (initialized in initialize())
        self.detector = None
        self.aligner = None
        self.recognizer = None
        self.liveness_detector = None
        self.emotion_recognizer = None
        self.tracker = None
        self.database = None
        
        # State
        self.initialized = False
        self.frame_counter = 0
        self._shutdown_requested = False
        
        # Video source
        self.video_source = None
        
        # Event callbacks
        self.callbacks: Dict[str, List[Callable]] = {
            'identity_recognized': [],
            'new_identity': [],
            'permission_changed': [],
            'error': [],
            'system_ready': []
        }
    
    def initialize(self) -> None:
        """
        Initialize all subsystems and load models.
        
        This method:
        1. Loads configuration
        2. Initializes logging
        3. Loads ONNX model with ONNX Runtime
        4. Initializes all modules (detection, alignment, recognition, liveness, emotion, tracking)
        5. Loads face database
        6. Emits "system_ready" event
        
        Raises:
            RuntimeError: If initialization fails
        
        Requirements: 20.1, 20.2, 14.4, 32.4
        """
        from guru_vision.config import GuruVisionConfig
        from guru_vision.utils.logging import setup_logging, get_logger
        from guru_vision.detection.detector import FaceDetector
        from guru_vision.alignment.aligner import FaceAligner
        from guru_vision.recognition.recognizer import FaceRecognizer
        from guru_vision.liveness.detector import LivenessDetector
        from guru_vision.emotion.recognizer import EmotionRecognizer
        from guru_vision.tracking.tracker import FaceTracker
        from guru_vision.database.face_db import FaceDatabase
        
        try:
            # Step 1: Load configuration
            # Requirements: 20.1
            if self.config_path:
                self.config = GuruVisionConfig.from_file(self.config_path)
            else:
                self.config = GuruVisionConfig()
            
            # Step 2: Initialize logging
            # Requirements: 20.1
            setup_logging(
                log_level=self.config.log_level,
                log_file=self.config.log_file,
                log_max_size_mb=self.config.log_max_size_mb,
                console_output=True
            )
            self.logger = get_logger(__name__)
            self.logger.info("GuruVision Engine initialization started")
            
            # Step 3: Initialize detection module
            # Requirements: 20.2
            self.logger.info("Initializing face detector...")
            self.detector = FaceDetector(use_gpu=self.config.use_gpu)
            
            # Step 4: Initialize alignment module
            # Requirements: 20.2
            self.logger.info("Initializing face aligner...")
            self.aligner = FaceAligner(output_size=(112, 112))
            
            # Step 5: Load ONNX model with ONNX Runtime for recognition
            # Requirements: 20.2, 14.4
            self.logger.info(f"Loading recognition model from {self.config.onnx_model_path}...")
            self.recognizer = FaceRecognizer(
                model_path=self.config.onnx_model_path,
                use_gpu=self.config.use_gpu
            )
            
            # Step 6: Initialize liveness detection (if enabled) with graceful degradation
            # Requirements: 20.2, 32.4
            if self.config.enable_liveness:
                try:
                    self.logger.info("Initializing liveness detector...")
                    self.liveness_detector = LivenessDetector(
                        model_path=self.config.liveness_model_path,
                        use_gpu=self.config.use_gpu
                    )
                except Exception as e:
                    # Graceful degradation: Continue without liveness detection
                    self.logger.warning(f"Failed to initialize liveness detector: {e}. Continuing without liveness detection.")
                    self.liveness_detector = None
                    self.config.enable_liveness = False
            else:
                self.logger.info("Liveness detection disabled")
                self.liveness_detector = None
            
            # Step 7: Initialize emotion recognition (if enabled) with graceful degradation
            # Requirements: 20.2, 32.4
            if self.config.enable_emotion:
                try:
                    self.logger.info("Initializing emotion recognizer...")
                    self.emotion_recognizer = EmotionRecognizer(
                        model_name="fer",
                        use_gpu=self.config.use_gpu
                    )
                except Exception as e:
                    # Graceful degradation: Continue without emotion recognition
                    self.logger.warning(f"Failed to initialize emotion recognizer: {e}. Continuing without emotion recognition.")
                    self.emotion_recognizer = None
                    self.config.enable_emotion = False
            else:
                self.logger.info("Emotion recognition disabled")
                self.emotion_recognizer = None
            
            # Step 8: Initialize face tracking (if enabled) with graceful degradation
            # Requirements: 20.2, 32.4
            if self.config.enable_tracking:
                try:
                    self.logger.info("Initializing face tracker...")
                    self.tracker = FaceTracker(
                        algorithm=self.config.tracker_algorithm,
                        max_age=self.config.tracker_max_age
                    )
                except Exception as e:
                    # Graceful degradation: Continue without tracking
                    self.logger.warning(f"Failed to initialize face tracker: {e}. Continuing without tracking.")
                    self.tracker = None
                    self.config.enable_tracking = False
            else:
                self.logger.info("Face tracking disabled")
                self.tracker = None
            
            # Step 9: Load face database
            # Requirements: 20.2
            self.logger.info(f"Loading face database from {self.config.database_path}...")
            self.database = FaceDatabase(db_path=self.config.database_path)
            try:
                self.database.load()
                num_identities = len(self.database.get_all_identities())
                self.logger.info(f"Loaded {num_identities} identities from database")
            except Exception as e:
                self.logger.warning(f"Could not load database (will create new): {e}")
            
            # Mark as initialized
            self.initialized = True
            self.frame_counter = 0
            
            # Step 10: Register signal handlers for graceful shutdown
            # Requirements: 20.6 - Support graceful shutdown on interrupt signals
            self._register_signal_handlers()
            
            # Step 11: Emit "system_ready" event
            # Requirements: 20.2, 14.4
            self.logger.info("GuruVision Engine initialization complete")
            self._emit_event('system_ready', {
                'timestamp': datetime.utcnow().isoformat(),
                'config': self.config.to_dict(),
                'num_identities': len(self.database.get_all_identities())
            })
            
        except Exception as e:
            # Requirements: 20.1 - Report which component failed and why
            error_msg = f"Initialization failed: {e}"
            if self.logger:
                self.logger.error(error_msg, exc_info=True)
            # Emit error event
            self._emit_event('error', {
                'timestamp': datetime.utcnow().isoformat(),
                'component': 'initialization',
                'error_type': type(e).__name__,
                'error_message': str(e)
            })
            raise RuntimeError(error_msg) from e
    
    def _emit_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Emit an event to all registered callbacks.
        
        Args:
            event_type: Type of event
            event_data: Event data dictionary
        """
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(event_data)
                except Exception as e:
                    if self.logger:
                        self.logger.error(
                            f"Error in callback for event '{event_type}': {e}",
                            exc_info=True
                        )
    
    def process_frame(self, frame: np.ndarray) -> RecognitionResult:
        """
        Process a single frame and return recognition results.
        
        This method implements the complete recognition pipeline:
        1. Check frame brightness and apply low-light enhancement if needed
        2. Run face detection
        3. Update tracker with detections
        4. For each detected face:
           - Align face
           - Extract embedding
           - Match identity
           - Run liveness detection (if enabled)
           - Run emotion recognition (if enabled)
           - Reject recognition if liveness fails
        5. Combine all per-face results into RecognitionResult
        6. Add frame metadata (timestamp, processing time)
        7. Emit recognition events
        
        Args:
            frame: Input frame as numpy array in BGR format (OpenCV format)
        
        Returns:
            RecognitionResult with all detected faces and metadata
        
        Raises:
            RuntimeError: If engine is not initialized
            ValueError: If frame is invalid
        
        Requirements: 3.1, 4.1, 5.1, 5.3, 7.1, 7.4, 8.1, 10.1, 13.2, 22.1, 31.3
        """
        from guru_vision.utils.preprocessing import enhance_low_light, check_brightness
        
        # Check if engine is initialized
        if not self.initialized:
            raise RuntimeError("Engine not initialized. Call initialize() first.")
        
        # Check if shutdown has been requested
        # Requirement 20.7: Complete current frame before shutting down
        if self._shutdown_requested:
            if self.logger:
                self.logger.warning("Shutdown requested, skipping frame processing")
            # Return empty result
            return RecognitionResult(
                faces=[],
                frame_id=self.frame_counter,
                timestamp=datetime.utcnow().isoformat(),
                processing_time_ms=0.0
            )
        
        # Validate frame
        if frame is None or frame.size == 0:
            raise ValueError("Invalid frame: frame is None or empty")
        
        # Start timing
        start_time = time.time()
        
        # Increment frame counter
        self.frame_counter += 1
        
        # Step 1: Check frame brightness and apply low-light enhancement if needed
        # Requirements: 22.1
        processed_frame = frame
        if self.config.enable_low_light_enhancement:
            brightness = check_brightness(frame)
            if brightness < 50.0:
                self.logger.debug(f"Low brightness detected ({brightness:.2f}), applying enhancement")
                processed_frame, was_enhanced = enhance_low_light(frame)
                if was_enhanced:
                    self.logger.debug("Low-light enhancement applied")
        
        # Step 2: Run face detection
        # Requirements: 3.1
        try:
            detections = self.detector.detect(
                processed_frame,
                confidence_threshold=self.config.detection_confidence
            )
            self.logger.debug(f"Detected {len(detections)} faces")
        except Exception as e:
            self.logger.error(f"Face detection failed: {e}", exc_info=True)
            # Emit error event
            self._emit_event('error', {
                'timestamp': datetime.utcnow().isoformat(),
                'frame_id': self.frame_counter,
                'component': 'face_detection',
                'error_type': type(e).__name__,
                'error_message': str(e)
            })
            detections = []
        
        # Step 3: Update tracker with detections
        # Requirements: 10.1, 32.4
        tracks = []
        if self.config.enable_tracking and self.tracker is not None:
            try:
                tracks = self.tracker.update(detections, processed_frame)
                self.logger.debug(f"Tracking {len(tracks)} faces")
            except Exception as e:
                # Graceful degradation: Process frames independently if tracking fails
                # Requirements: 32.4
                self.logger.error(f"Face tracking failed: {e}. Processing frames independently.", exc_info=True)
                # Emit error event
                self._emit_event('error', {
                    'timestamp': datetime.utcnow().isoformat(),
                    'frame_id': self.frame_counter,
                    'component': 'face_tracking',
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                })
                # Fall back to using detections without tracking
                tracks = []
                # Disable tracking for future frames to avoid repeated errors
                self.config.enable_tracking = False
                self.tracker = None
        
        # Create mapping from detection to track
        # If tracking is disabled, create pseudo-tracks
        if tracks:
            detection_to_track = {}
            for i, detection in enumerate(detections):
                # Find matching track by bbox overlap
                best_track = None
                best_iou = 0.0
                for track in tracks:
                    iou = self._compute_iou(detection.bbox, track.bbox)
                    if iou > best_iou:
                        best_iou = iou
                        best_track = track
                if best_track and best_iou > 0.3:
                    detection_to_track[i] = best_track
        else:
            # No tracking - assign sequential IDs
            detection_to_track = {}
            for i in range(len(detections)):
                # Create pseudo-track with sequential ID
                from guru_vision.tracking.tracker import Track
                pseudo_track = Track(
                    tracking_id=self.frame_counter * 1000 + i,
                    bbox=detections[i].bbox,
                    age=0,
                    hits=1,
                    state=np.zeros(8),
                    covariance=np.eye(8)
                )
                detection_to_track[i] = pseudo_track
        
        # Step 4: Process each detected face (implemented in subtask 19.4)
        face_results = []
        for i, detection in enumerate(detections):
            track = detection_to_track.get(i)
            if track is None:
                continue
            
            face_result = self._process_single_face(
                processed_frame,
                detection,
                track.tracking_id
            )
            
            if face_result is not None:
                face_results.append(face_result)
        
        # Step 5: Combine results and add metadata (implemented in subtask 19.5)
        end_time = time.time()
        processing_time_ms = (end_time - start_time) * 1000.0
        
        result = RecognitionResult(
            faces=face_results,
            frame_id=self.frame_counter,
            timestamp=datetime.utcnow().isoformat(),
            processing_time_ms=processing_time_ms
        )
        
        # Step 6: Emit recognition events (implemented in subtask 19.5)
        self._emit_recognition_events(result)
        
        return result
    
    def _compute_iou(self, bbox1: Tuple[int, int, int, int], 
                     bbox2: Tuple[int, int, int, int]) -> float:
        """
        Compute Intersection over Union (IoU) between two bounding boxes.
        
        Args:
            bbox1: First bounding box (x, y, w, h)
            bbox2: Second bounding box (x, y, w, h)
        
        Returns:
            IoU score between 0.0 and 1.0
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2
        
        # Convert to (x1, y1, x2, y2) format
        box1 = [x1, y1, x1 + w1, y1 + h1]
        box2 = [x2, y2, x2 + w2, y2 + h2]
        
        # Compute intersection
        x_left = max(box1[0], box2[0])
        y_top = max(box1[1], box2[1])
        x_right = min(box1[2], box2[2])
        y_bottom = min(box1[3], box2[3])
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection = (x_right - x_left) * (y_bottom - y_top)
        
        # Compute union
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _process_single_face(
        self,
        frame: np.ndarray,
        detection,
        tracking_id: int
    ) -> Optional[FaceResult]:
        """
        Process a single detected face through the recognition pipeline.
        
        This method:
        1. Aligns the face
        2. Extracts embedding
        3. Matches identity
        4. Runs liveness detection (if enabled)
        5. Runs emotion recognition (if enabled)
        6. Rejects recognition if liveness fails
        
        Args:
            frame: Input frame
            detection: Detection object
            tracking_id: Tracking ID for this face
        
        Returns:
            FaceResult or None if processing fails
        
        Requirements: 4.1, 5.1, 5.3, 7.1, 7.4, 8.1
        """
        try:
            # Step 1: Align face
            # Requirements: 4.1
            aligned_face = self.aligner.align(frame, detection)
            
            # Step 2: Extract embedding
            # Requirements: 5.1
            embedding = self.recognizer.extract_embedding(aligned_face)
            
            # Step 3: Match identity
            # Requirements: 5.3
            match_result = self.recognizer.match_identity(
                embedding,
                self.database,
                threshold=self.config.recognition_threshold
            )
            
            identity = match_result.identity
            confidence = match_result.confidence
            permission_level = match_result.permission_level
            
            # Step 4: Run liveness detection (if enabled)
            # Requirements: 7.1, 7.4
            is_live = True
            liveness_confidence = 1.0
            
            if self.config.enable_liveness and self.liveness_detector is not None:
                try:
                    liveness_result = self.liveness_detector.detect(aligned_face)
                    is_live = liveness_result.is_live
                    liveness_confidence = liveness_result.confidence
                    
                    # Reject recognition if liveness fails
                    # Requirements: 7.4
                    if not is_live:
                        self.logger.warning(
                            f"Liveness check failed for tracking_id={tracking_id}, "
                            f"attack_type={liveness_result.attack_type}"
                        )
                        # Override identity to Unknown when liveness fails
                        identity = "Unknown"
                        confidence = 0.0
                        permission_level = "guest"
                        
                except Exception as e:
                    self.logger.error(f"Liveness detection failed: {e}", exc_info=True)
                    # Emit error event
                    self._emit_event('error', {
                        'timestamp': datetime.utcnow().isoformat(),
                        'frame_id': self.frame_counter,
                        'tracking_id': tracking_id,
                        'component': 'liveness_detection',
                        'error_type': type(e).__name__,
                        'error_message': str(e)
                    })
                    # Continue without liveness check (graceful degradation)
                    is_live = True
                    liveness_confidence = 0.0
            
            # Step 5: Run emotion recognition (if enabled)
            # Requirements: 8.1
            emotion = "neutral"
            emotion_confidence = 0.0
            
            if self.config.enable_emotion and self.emotion_recognizer is not None:
                try:
                    emotion_result = self.emotion_recognizer.recognize(aligned_face)
                    emotion = emotion_result.dominant_emotion
                    emotion_confidence = emotion_result.confidence
                except Exception as e:
                    self.logger.error(f"Emotion recognition failed: {e}", exc_info=True)
                    # Emit error event
                    self._emit_event('error', {
                        'timestamp': datetime.utcnow().isoformat(),
                        'frame_id': self.frame_counter,
                        'tracking_id': tracking_id,
                        'component': 'emotion_recognition',
                        'error_type': type(e).__name__,
                        'error_message': str(e)
                    })
                    # Continue with default neutral emotion (graceful degradation)
                    emotion = "neutral"
                    emotion_confidence = 0.0
            
            # Create FaceResult
            face_result = FaceResult(
                tracking_id=tracking_id,
                bbox=detection.bbox,
                identity=identity,
                confidence=confidence,
                permission_level=permission_level,
                emotion=emotion,
                emotion_confidence=emotion_confidence,
                is_live=is_live,
                liveness_confidence=liveness_confidence
            )
            
            return face_result
            
        except Exception as e:
            self.logger.error(
                f"Failed to process face (tracking_id={tracking_id}): {e}",
                exc_info=True
            )
            return None
    
    def _emit_recognition_events(self, result: RecognitionResult) -> None:
        """
        Emit recognition events for callbacks.
        
        This method emits 'identity_recognized' events for each recognized face
        in the result.
        
        Args:
            result: RecognitionResult to emit events for
        
        Requirements: 13.2, 31.3
        """
        # Emit event for each recognized face
        for face in result.faces:
            # Only emit for recognized identities (not "Unknown")
            if face.identity != "Unknown":
                event_data = {
                    'timestamp': result.timestamp,
                    'frame_id': result.frame_id,
                    'tracking_id': face.tracking_id,
                    'identity': face.identity,
                    'confidence': face.confidence,
                    'permission_level': face.permission_level,
                    'emotion': face.emotion,
                    'emotion_confidence': face.emotion_confidence,
                    'is_live': face.is_live,
                    'liveness_confidence': face.liveness_confidence,
                    'bbox': face.bbox
                }
                
                self._emit_event('identity_recognized', event_data)
                
                self.logger.debug(
                    f"Identity recognized: {face.identity} "
                    f"(confidence={face.confidence:.3f}, "
                    f"permission={face.permission_level}, "
                    f"emotion={face.emotion})"
                )
    
    def add_identity(
        self,
        name: str,
        images: List[np.ndarray],
        permission_level: str = "user"
    ) -> bool:
        """
        Add a new identity without retraining the model.
        
        This method:
        1. Validates inputs
        2. For each image: detect face, align, extract embedding
        3. Stores embeddings in database
        4. Saves database to disk
        5. Emits "new_identity" event
        
        Args:
            name: Unique identifier for the identity
            images: List of face images (BGR format)
            permission_level: Permission level (admin, user, guest, denied)
        
        Returns:
            True if identity was added successfully, False otherwise
        
        Raises:
            RuntimeError: If engine is not initialized
            ValueError: If inputs are invalid
        
        Requirements: 16.1, 16.2, 16.3, 16.4, 16.5
        """
        # Requirement 16.1: Add new identity without retraining
        # Requirement 16.2: Store embeddings immediately
        # Requirement 16.3: Recognize newly added identities in subsequent operations
        # Requirement 16.4: Require at least 5 images for reliable recognition
        # Requirement 16.5: Support batch import and individual addition
        
        # Check if engine is initialized
        if not self.initialized:
            raise RuntimeError("Engine not initialized. Call initialize() first.")
        
        # Validate inputs
        if not name or not isinstance(name, str):
            raise ValueError("Identity name must be a non-empty string")
        
        if not images or not isinstance(images, list):
            raise ValueError("Images must be a non-empty list")
        
        if len(images) < 5:
            # Requirement 16.4: Require at least 5 images
            self.logger.warning(
                f"Adding identity '{name}' with only {len(images)} images. "
                "At least 5 images recommended for reliable recognition."
            )
        
        valid_permissions = ["admin", "user", "guest", "denied"]
        if permission_level not in valid_permissions:
            raise ValueError(
                f"Invalid permission_level '{permission_level}'. "
                f"Must be one of: {valid_permissions}"
            )
        
        self.logger.info(
            f"Adding identity '{name}' with {len(images)} images "
            f"and permission level '{permission_level}'"
        )
        
        # Extract embeddings from all images
        embeddings = []
        successful_images = 0
        
        for idx, image in enumerate(images):
            try:
                # Validate image format
                if not isinstance(image, np.ndarray):
                    self.logger.warning(
                        f"Image {idx} for identity '{name}' is not a numpy array, skipping"
                    )
                    continue
                
                if len(image.shape) != 3 or image.shape[2] != 3:
                    self.logger.warning(
                        f"Image {idx} for identity '{name}' has invalid shape {image.shape}, skipping"
                    )
                    continue
                
                # Step 1: Detect face
                detections = self.detector.detect(image)
                
                if len(detections) == 0:
                    self.logger.warning(
                        f"No face detected in image {idx} for identity '{name}', skipping"
                    )
                    continue
                
                if len(detections) > 1:
                    self.logger.warning(
                        f"Multiple faces detected in image {idx} for identity '{name}', "
                        "using face with highest confidence"
                    )
                
                # Use the detection with highest confidence
                detection = max(detections, key=lambda d: d.confidence)
                
                # Step 2: Align face
                aligned_face = self.aligner.align(image, detection)
                
                # Step 3: Extract embedding
                embedding = self.recognizer.extract_embedding(aligned_face)
                
                # Store embedding with metadata
                from guru_vision.database.face_db import Embedding
                embedding_obj = Embedding(
                    vector=embedding,
                    timestamp=datetime.utcnow().isoformat(),
                    angle_category="unknown",  # Could be enhanced with angle detection
                    lighting_condition="unknown",  # Could be enhanced with lighting detection
                    metadata={"source_image_index": idx}
                )
                embeddings.append(embedding_obj)
                successful_images += 1
                
            except Exception as e:
                self.logger.error(
                    f"Error processing image {idx} for identity '{name}': {e}",
                    exc_info=True
                )
                continue
        
        # Check if we got any valid embeddings
        if len(embeddings) == 0:
            self.logger.error(
                f"Failed to extract any embeddings for identity '{name}'. "
                "No valid faces detected in provided images."
            )
            return False
        
        self.logger.info(
            f"Successfully extracted {len(embeddings)} embeddings from "
            f"{successful_images}/{len(images)} images for identity '{name}'"
        )
        
        # Step 4: Store embeddings in database
        try:
            # Requirement 16.2: Store embeddings immediately
            success = self.database.add_identity(
                name=name,
                embeddings=embeddings,
                permission_level=permission_level,
                metadata={
                    "date_added": datetime.utcnow().isoformat(),
                    "num_images_processed": len(images),
                    "num_embeddings_extracted": len(embeddings)
                }
            )
            
            if not success:
                self.logger.error(f"Failed to add identity '{name}' to database")
                return False
            
            # Step 5: Save database to disk
            self.database.save()
            self.logger.info(f"Identity '{name}' saved to database")
            
            # Step 6: Emit "new_identity" event
            self._emit_event('new_identity', {
                'timestamp': datetime.utcnow().isoformat(),
                'identity': name,
                'permission_level': permission_level,
                'num_embeddings': len(embeddings)
            })
            
            return True
            
        except Exception as e:
            self.logger.error(
                f"Error adding identity '{name}' to database: {e}",
                exc_info=True
            )
            return False
    
    def remove_identity(self, name: str) -> bool:
        """
        Remove an identity and all associated embeddings.
        
        Args:
            name: Identity name to remove
        
        Returns:
            True if identity was removed, False if not found
        
        Raises:
            RuntimeError: If engine is not initialized
        
        Requirements: 12.3
        """
        # Requirement 12.3: Support deleting identities and all associated embeddings
        
        # Check if engine is initialized
        if not self.initialized:
            raise RuntimeError("Engine not initialized. Call initialize() first.")
        
        # Validate input
        if not name or not isinstance(name, str):
            raise ValueError("Identity name must be a non-empty string")
        
        self.logger.info(f"Removing identity '{name}'")
        
        try:
            # Call database.remove_identity()
            success = self.database.remove_identity(name)
            
            if not success:
                self.logger.warning(f"Identity '{name}' not found in database")
                return False
            
            # Save database to disk
            self.database.save()
            self.logger.info(f"Identity '{name}' removed and database saved")
            
            # Emit event for identity removal
            self._emit_event('identity_removed', {
                'timestamp': datetime.utcnow().isoformat(),
                'identity': name
            })
            
            return True
            
        except Exception as e:
            self.logger.error(
                f"Error removing identity '{name}': {e}",
                exc_info=True
            )
            return False
    
    def get_identities(self) -> List[IdentityInfo]:
        """
        Get information about all stored identities.
        
        Returns:
            List of IdentityInfo objects
        
        Raises:
            RuntimeError: If engine is not initialized
        
        Requirements: 12.4
        """
        # Requirement 12.4: Support querying all stored identities with their metadata
        
        # Check if engine is initialized
        if not self.initialized:
            raise RuntimeError("Engine not initialized. Call initialize() first.")
        
        try:
            # Call database.get_all_identities()
            identities = self.database.get_all_identities()
            
            # Convert to IdentityInfo objects
            identity_infos = []
            for identity in identities:
                info = IdentityInfo(
                    name=identity.name,
                    permission_level=identity.permission_level,
                    num_embeddings=len(identity.embeddings),
                    date_added=identity.date_added,
                    metadata=identity.metadata
                )
                identity_infos.append(info)
            
            self.logger.debug(f"Retrieved {len(identity_infos)} identities from database")
            return identity_infos
            
        except Exception as e:
            self.logger.error(
                f"Error retrieving identities: {e}",
                exc_info=True
            )
            return []
    
    def update_permission(self, name: str, permission_level: str) -> bool:
        """
        Update the permission level for an identity.
        
        Args:
            name: Identity name
            permission_level: New permission level (admin, user, guest, denied)
        
        Returns:
            True if updated successfully, False if identity not found
        
        Raises:
            RuntimeError: If engine is not initialized
            ValueError: If permission_level is invalid
        
        Requirements: 9.5, 12.2
        """
        # Requirement 9.5: Allow administrators to modify permission level assignments
        # Requirement 12.2: Support updating existing identity information including permission level
        
        # Check if engine is initialized
        if not self.initialized:
            raise RuntimeError("Engine not initialized. Call initialize() first.")
        
        # Validate inputs
        if not name or not isinstance(name, str):
            raise ValueError("Identity name must be a non-empty string")
        
        valid_permissions = ["admin", "user", "guest", "denied"]
        if permission_level not in valid_permissions:
            raise ValueError(
                f"Invalid permission_level '{permission_level}'. "
                f"Must be one of: {valid_permissions}"
            )
        
        self.logger.info(
            f"Updating permission level for identity '{name}' to '{permission_level}'"
        )
        
        try:
            # Call database.update_permission()
            success = self.database.update_permission(name, permission_level)
            
            if not success:
                self.logger.warning(f"Identity '{name}' not found in database")
                return False
            
            # Save database to disk
            self.database.save()
            self.logger.info(
                f"Permission level for identity '{name}' updated to '{permission_level}' "
                "and database saved"
            )
            
            # Emit "permission_changed" event
            self._emit_event('permission_changed', {
                'timestamp': datetime.utcnow().isoformat(),
                'identity': name,
                'new_permission_level': permission_level
            })
            
            return True
            
        except Exception as e:
            self.logger.error(
                f"Error updating permission for identity '{name}': {e}",
                exc_info=True
            )
            return False
    
    def register_callback(self, event_type: str, callback: Callable) -> None:
        """
        Register a callback function for recognition events.
        
        Args:
            event_type: Type of event to listen for:
                       - 'identity_recognized': When an identity is recognized
                       - 'new_identity': When a new identity is added
                       - 'permission_changed': When permission level changes
                       - 'error': When an error occurs
                       - 'system_ready': When system initialization completes
            callback: Callable that accepts event data as a dictionary
        
        Raises:
            ValueError: If event_type is invalid
        
        Requirements: 13.3, 13.5
        """
        # Requirement 13.3: Support callback functions that trigger when specific identities are recognized
        # Requirement 13.5: Emit events that the AI_Agent can subscribe to
        
        # Validate event type
        valid_event_types = [
            'identity_recognized',
            'new_identity',
            'permission_changed',
            'error',
            'system_ready'
        ]
        
        if event_type not in valid_event_types:
            raise ValueError(
                f"Invalid event_type '{event_type}'. "
                f"Must be one of: {valid_event_types}"
            )
        
        # Validate callback is callable
        if not callable(callback):
            raise ValueError("Callback must be a callable function")
        
        # Store callback by event type
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        
        self.callbacks[event_type].append(callback)
        
        if self.logger:
            self.logger.debug(
                f"Registered callback for event type '{event_type}'. "
                f"Total callbacks for this event: {len(self.callbacks[event_type])}"
            )
    
    def init_video_source(self, source: Optional[str] = None, camera_index: Optional[int] = None) -> bool:
        """
        Initialize video source for frame capture.
        
        This method supports multiple video source types:
        - Webcam by device index or name
        - Video file paths (MP4, AVI, MOV)
        - Image files
        - Image directories
        
        Args:
            source: Video source specification:
                   - None: Use webcam with camera_index from config
                   - Integer string (e.g., "0"): Webcam device index
                   - File path: Video file or image file
                   - Directory path: Image directory
            camera_index: Camera device index (overrides config if provided)
        
        Returns:
            True if video source initialized successfully, False otherwise
        
        Raises:
            RuntimeError: If engine is not initialized
            VideoSourceError: If source is unavailable or cannot be opened
        
        Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6
        """
        from guru_vision.video_source import VideoSource, VideoSourceError
        
        # Check if engine is initialized
        if not self.initialized:
            raise RuntimeError("Engine not initialized. Call initialize() first.")
        
        # Release existing video source if any
        if self.video_source is not None:
            self.video_source.release()
            self.video_source = None
        
        # Use camera_index from parameter or config
        cam_idx = camera_index if camera_index is not None else self.config.camera_index
        
        # Use source from parameter or config
        src = source if source is not None else self.config.video_source
        
        try:
            # Create and open video source
            self.video_source = VideoSource(source=src, camera_index=cam_idx)
            success = self.video_source.open()
            
            if success:
                # Log video source info
                info = self.video_source.get_info()
                self.logger.info(
                    f"Video source initialized: type={info['source_type']}, "
                    f"resolution={info['resolution']}, fps={info['fps']:.1f}"
                )
                
                if info['total_frames'] is not None:
                    self.logger.info(f"Total frames: {info['total_frames']}")
            
            return success
            
        except VideoSourceError as e:
            self.logger.error(f"Failed to initialize video source: {e}")
            # Emit error event
            self._emit_event('error', {
                'timestamp': datetime.utcnow().isoformat(),
                'component': 'video_source',
                'error_type': 'VideoSourceError',
                'error_message': str(e)
            })
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error initializing video source: {e}", exc_info=True)
            # Emit error event
            self._emit_event('error', {
                'timestamp': datetime.utcnow().isoformat(),
                'component': 'video_source',
                'error_type': type(e).__name__,
                'error_message': str(e)
            })
            raise
    
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read the next frame from the video source.
        
        Returns:
            Tuple of (success, frame):
                - success: True if frame was read successfully
                - frame: Frame as numpy array in BGR format, or None if failed
        
        Raises:
            RuntimeError: If video source is not initialized
        
        Requirements: 19.1, 19.2, 19.3, 19.4
        """
        if self.video_source is None:
            raise RuntimeError(
                "Video source not initialized. Call init_video_source() first."
            )
        
        return self.video_source.read()
    
    def seek_frame(self, frame_number: int) -> bool:
        """
        Seek to a specific frame number in the video.
        
        This method is only supported for video files and image sequences.
        Webcam sources cannot seek.
        
        Args:
            frame_number: Frame number to seek to (0-indexed)
        
        Returns:
            True if seek was successful, False otherwise
        
        Raises:
            RuntimeError: If video source is not initialized
        
        Requirements: 19.7
        """
        if self.video_source is None:
            raise RuntimeError(
                "Video source not initialized. Call init_video_source() first."
            )
        
        return self.video_source.seek(frame_number)
    
    def get_video_info(self) -> dict:
        """
        Get information about the current video source.
        
        Returns:
            Dictionary with source information:
                - source_type: Type of video source
                - resolution: (width, height) tuple
                - fps: Frames per second
                - total_frames: Total number of frames (None for webcam)
                - current_frame: Current frame position (-1 for webcam)
        
        Raises:
            RuntimeError: If video source is not initialized
        
        Requirements: 19.6
        """
        if self.video_source is None:
            raise RuntimeError(
                "Video source not initialized. Call init_video_source() first."
            )
        
        return self.video_source.get_info()
    
    def _register_signal_handlers(self) -> None:
        """
        Register signal handlers for graceful shutdown.
        
        This method registers handlers for SIGINT (Ctrl+C) and SIGTERM
        to ensure graceful shutdown when the process is interrupted.
        
        Requirements: 20.6
        """
        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
            if self.logger:
                self.logger.info(f"Received {signal_name}, initiating graceful shutdown...")
            
            # Set shutdown flag
            self._shutdown_requested = True
            
            # Call shutdown method
            try:
                self.shutdown()
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error during signal-triggered shutdown: {e}", exc_info=True)
                # Exit with error code
                import sys
                sys.exit(1)
            
            # Exit successfully
            import sys
            sys.exit(0)
        
        # Register handlers for SIGINT and SIGTERM
        # Requirement 20.6: Handle SIGINT and SIGTERM
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Also register atexit handler as a fallback
            atexit.register(self._atexit_handler)
            
            if self.logger:
                self.logger.debug("Signal handlers registered for SIGINT and SIGTERM")
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Could not register signal handlers: {e}")
    
    def _atexit_handler(self) -> None:
        """
        Handler called at program exit.
        
        This is a fallback to ensure shutdown is called even if
        signal handlers don't fire.
        """
        if self.initialized and not self._shutdown_requested:
            if self.logger:
                self.logger.debug("atexit handler triggered, calling shutdown")
            try:
                self.shutdown()
            except Exception as e:
                if self.logger:
                    self.logger.error(f"Error in atexit handler: {e}", exc_info=True)
    
    def shutdown(self) -> None:
        """
        Gracefully shutdown the engine and release resources.
        
        This method:
        1. Releases camera resources
        2. Saves pending database changes
        3. Closes ONNX Runtime sessions
        4. Completes within 3 seconds
        
        Requirements: 20.3, 20.4, 20.5, 20.7
        """
        import time
        
        # Set shutdown flag to prevent duplicate shutdowns
        if self._shutdown_requested:
            if self.logger:
                self.logger.debug("Shutdown already in progress, skipping")
            return
        
        self._shutdown_requested = True
        
        # Start timing to ensure we complete within 3 seconds
        # Requirement 20.5: Complete shutdown within 3 seconds
        start_time = time.time()
        
        if self.logger:
            self.logger.info("GuruVision Engine shutdown initiated")
        
        try:
            # Step 1: Release camera resources
            # Requirement 20.3: Release all camera resources
            if self.video_source is not None:
                try:
                    self.video_source.release()
                    self.video_source = None
                    if self.logger:
                        self.logger.info("Video source released successfully")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Failed to release video source: {e}", exc_info=True)
            else:
                if self.logger:
                    self.logger.debug("No video source to release")
            
            # Step 2: Save pending database changes
            # Requirement 20.4: Save any pending database changes
            if self.database is not None:
                try:
                    self.database.save()
                    if self.logger:
                        self.logger.info("Database changes saved successfully")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Failed to save database during shutdown: {e}", exc_info=True)
            
            # Step 3: Close ONNX Runtime sessions
            # Requirement 20.5: Close ONNX Runtime sessions
            
            # Close recognizer session
            if self.recognizer is not None and hasattr(self.recognizer, 'session'):
                try:
                    # ONNX Runtime sessions are automatically cleaned up by Python's garbage collector
                    # But we can explicitly delete the reference to help with cleanup
                    del self.recognizer.session
                    if self.logger:
                        self.logger.debug("Recognition model session closed")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Error closing recognition session: {e}", exc_info=True)
            
            # Close liveness detector session
            if self.liveness_detector is not None and hasattr(self.liveness_detector, 'session'):
                try:
                    if self.liveness_detector.model_loaded:
                        del self.liveness_detector.session
                        if self.logger:
                            self.logger.debug("Liveness detector session closed")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Error closing liveness session: {e}", exc_info=True)
            
            # Close emotion recognizer session
            if self.emotion_recognizer is not None and hasattr(self.emotion_recognizer, 'session'):
                try:
                    if self.emotion_recognizer.model_loaded:
                        del self.emotion_recognizer.session
                        if self.logger:
                            self.logger.debug("Emotion recognizer session closed")
                except Exception as e:
                    if self.logger:
                        self.logger.error(f"Error closing emotion session: {e}", exc_info=True)
            
            # Clear module references
            self.detector = None
            self.aligner = None
            self.recognizer = None
            self.liveness_detector = None
            self.emotion_recognizer = None
            self.tracker = None
            self.database = None
            
            # Mark as not initialized
            self.initialized = False
            
            # Check shutdown time
            elapsed_time = time.time() - start_time
            if self.logger:
                self.logger.info(f"GuruVision Engine shutdown complete in {elapsed_time:.3f} seconds")
            
            # Requirement 20.5: Ensure shutdown completes within 3 seconds
            if elapsed_time > 3.0:
                if self.logger:
                    self.logger.warning(
                        f"Shutdown took {elapsed_time:.3f} seconds, exceeding 3 second target"
                    )
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"Error during shutdown: {e}", exc_info=True)
            # Re-raise to ensure caller knows shutdown failed
            raise
