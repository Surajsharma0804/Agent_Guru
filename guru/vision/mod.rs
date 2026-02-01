//! # Vision and Screen Perception System
//! 
//! Production-grade computer vision system for AGENT_GURU with real-time object detection,
//! multi-object tracking, OCR processing, and privacy-preserving capabilities.
//! 
//! ## Architecture
//! 
//! The vision system implements a layered architecture with strict performance guarantees:
//! - Detection Layer: YOLO-based object detection with ≤40ms latency
//! - Tracking Layer: Kalman filter-based multi-object tracking with state prediction
//! - Recognition Layer: OCR and face recognition with ≤500ms processing time
//! - Privacy Layer: Secure processing with no image storage in privacy mode
//! 
//! ## Performance Requirements
//! 
//! - Video processing: ≥24 FPS sustained (99th percentile)
//! - Object detection latency: ≤40ms per frame
//! - Face recognition: ≤500ms per face
//! - OCR processing: ≤100ms per text region
//! - Memory usage: <1GB for real-time processing
//! - Multi-camera support: Up to 4 simultaneous inputs
//! 
//! ## Security and Privacy
//! 
//! - Privacy mode: No image storage, secure deletion of processed data
//! - Capability-based access control for all vision operations
//! - Encrypted processing pipelines for sensitive data
//! - Formal verification of privacy guarantees

pub mod detection;
pub mod tracking;
pub mod ocr;
pub mod privacy;
pub mod face_recognition;
pub mod gesture_detection;
pub mod scene_understanding;

#[cfg(test)]
pub mod property_tests;

use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Vision system errors with comprehensive error handling
#[derive(Error, Debug)]
pub enum VisionError {
    /// Object detection operation failed
    #[error("Detection failed: {0}")]
    DetectionFailed(String),
    
    /// Multi-object tracking operation failed
    #[error("Tracking failed: {0}")]
    TrackingFailed(String),
    
    /// OCR processing operation failed
    #[error("OCR processing failed: {0}")]
    OcrFailed(String),
    
    /// Face recognition operation failed
    #[error("Face recognition failed: {0}")]
    FaceRecognitionFailed(String),
    
    /// Gesture detection operation failed
    #[error("Gesture detection failed: {0}")]
    GestureDetectionFailed(String),
    
    /// Scene understanding operation failed
    #[error("Scene understanding failed: {0}")]
    SceneUnderstandingFailed(String),
    
    /// Privacy protection violation detected
    #[error("Privacy violation: {0}")]
    PrivacyViolation(String),
    
    /// Performance constraint was violated
    #[error("Performance constraint violated: {0}")]
    PerformanceViolation(String),
    
    /// Memory usage limit was exceeded
    #[error("Memory limit exceeded: {0}")]
    MemoryLimitExceeded(String),
    
    /// Hardware acceleration is not available
    #[error("Hardware acceleration unavailable: {0}")]
    HardwareAccelerationUnavailable(String),
    
    /// Input format is invalid or unsupported
    #[error("Invalid input format: {0}")]
    InvalidInputFormat(String),
    
    /// Configuration parameter is invalid
    #[error("Configuration error: {0}")]
    ConfigurationError(String),
}

/// Result type for vision operations
pub type VisionResult<T> = Result<T, VisionError>;

/// Image data structure with metadata
#[derive(Debug, Clone)]
pub struct ImageData {
    /// Raw image data in RGB format
    pub data: Vec<u8>,
    /// Image width in pixels
    pub width: u32,
    /// Image height in pixels  
    pub height: u32,
    /// Number of channels (typically 3 for RGB)
    pub channels: u32,
    /// Timestamp when image was captured
    pub timestamp: Instant,
    /// Camera ID for multi-camera setups
    pub camera_id: u32,
    /// Image format metadata
    pub format: ImageFormat,
}

/// Supported image formats
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ImageFormat {
    /// 8-bit RGB format (3 channels)
    Rgb8,
    /// 8-bit RGBA format (4 channels with alpha)
    Rgba8,
    /// 8-bit BGR format (3 channels, blue-green-red)
    Bgr8,
    /// 8-bit BGRA format (4 channels with alpha, blue-green-red-alpha)
    Bgra8,
    /// 8-bit grayscale format (1 channel)
    Grayscale8,
    /// YUV 4:2:0 planar format
    Yuv420p,
}

/// Bounding box with confidence score
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoundingBox {
    /// X coordinate of top-left corner
    pub x: f32,
    /// Y coordinate of top-left corner
    pub y: f32,
    /// Width of bounding box
    pub width: f32,
    /// Height of bounding box
    pub height: f32,
    /// Confidence score (0.0 to 1.0)
    pub confidence: f32,
    /// Object class ID
    pub class_id: u32,
    /// Object class name
    pub class_name: String,
}

/// Object detection result
#[derive(Debug, Clone)]
pub struct DetectionResult {
    /// List of detected objects
    pub objects: Vec<BoundingBox>,
    /// Processing time in milliseconds
    pub processing_time_ms: u32,
    /// Frame timestamp
    pub timestamp: Instant,
    /// Detection confidence threshold used
    pub confidence_threshold: f32,
    /// Non-maximum suppression threshold used
    pub nms_threshold: f32,
}

/// Tracked object with temporal information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrackedObject {
    /// Unique tracking ID
    pub track_id: u64,
    /// Current bounding box
    pub bbox: BoundingBox,
    /// Predicted next position
    pub predicted_bbox: Option<BoundingBox>,
    /// Tracking confidence
    pub tracking_confidence: f32,
    /// Number of frames tracked
    pub age: u32,
    /// Number of consecutive missed detections
    pub time_since_update: u32,
    /// Object velocity (pixels per frame)
    pub velocity: (f32, f32),
    /// Kalman filter state
    pub state: Vec<f32>,
    /// State covariance matrix
    pub covariance: Vec<Vec<f32>>,
}

/// Multi-object tracking result
#[derive(Debug, Clone)]
pub struct TrackingResult {
    /// List of tracked objects
    pub tracked_objects: Vec<TrackedObject>,
    /// Processing time in milliseconds
    pub processing_time_ms: u32,
    /// Frame timestamp
    pub timestamp: Instant,
    /// Number of active tracks
    pub active_tracks: u32,
    /// Number of new tracks initiated
    pub new_tracks: u32,
    /// Number of tracks terminated
    pub terminated_tracks: u32,
}

/// OCR text detection result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TextDetection {
    /// Detected text content
    pub text: String,
    /// Bounding box of text region
    pub bbox: BoundingBox,
    /// Text recognition confidence
    pub confidence: f32,
    /// Language detected
    pub language: Option<String>,
    /// Text orientation angle
    pub angle: f32,
    /// Font size estimate
    pub font_size: Option<f32>,
}

/// OCR processing result
#[derive(Debug, Clone)]
pub struct OcrResult {
    /// List of detected text regions
    pub text_detections: Vec<TextDetection>,
    /// Processing time in milliseconds
    pub processing_time_ms: u32,
    /// Frame timestamp
    pub timestamp: Instant,
    /// Overall OCR confidence
    pub overall_confidence: f32,
}

/// Face detection and recognition result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FaceDetection {
    /// Face bounding box
    pub bbox: BoundingBox,
    /// Facial landmarks (68 points)
    pub landmarks: Vec<(f32, f32)>,
    /// Face recognition confidence
    pub recognition_confidence: f32,
    /// Identified person (if known)
    pub person_id: Option<String>,
    /// Age estimate
    pub estimated_age: Option<u32>,
    /// Gender estimate
    pub estimated_gender: Option<String>,
    /// Emotion classification
    pub emotion: Option<String>,
    /// Emotion confidence
    pub emotion_confidence: Option<f32>,
    /// Liveness detection score
    pub liveness_score: f32,
}

/// Gesture detection result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GestureDetection {
    /// Gesture type
    pub gesture_type: String,
    /// Gesture confidence
    pub confidence: f32,
    /// Hand bounding box
    pub hand_bbox: BoundingBox,
    /// Hand landmarks (21 points)
    pub hand_landmarks: Vec<(f32, f32)>,
    /// Gesture duration
    pub duration_ms: u32,
    /// Gesture velocity
    pub velocity: (f32, f32),
}

/// Scene understanding result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SceneUnderstanding {
    /// Scene description
    pub description: String,
    /// Spatial relationships between objects
    pub spatial_relationships: Vec<SpatialRelationship>,
    /// Scene classification
    pub scene_type: String,
    /// Scene confidence
    pub confidence: f32,
    /// Depth estimation (if available)
    pub depth_map: Option<Vec<f32>>,
}

/// Spatial relationship between objects
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SpatialRelationship {
    /// First object ID
    pub object1_id: u64,
    /// Second object ID
    pub object2_id: u64,
    /// Relationship type (e.g., "above", "left_of", "inside")
    pub relationship: String,
    /// Relationship confidence
    pub confidence: f32,
    /// Distance between objects (pixels)
    pub distance: f32,
}

/// Vision system performance metrics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VisionMetrics {
    /// Frames per second
    pub fps: f32,
    /// Average detection latency (ms)
    pub avg_detection_latency_ms: f32,
    /// Average tracking latency (ms)
    pub avg_tracking_latency_ms: f32,
    /// Average OCR latency (ms)
    pub avg_ocr_latency_ms: f32,
    /// Memory usage (bytes)
    pub memory_usage_bytes: u64,
    /// CPU utilization percentage
    pub cpu_utilization: f32,
    /// GPU utilization percentage (if available)
    pub gpu_utilization: Option<f32>,
    /// Number of processed frames
    pub frames_processed: u64,
    /// Number of detection errors
    pub detection_errors: u64,
    /// Number of tracking errors
    pub tracking_errors: u64,
    /// Privacy mode active
    pub privacy_mode_active: bool,
}

/// Vision system configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VisionConfig {
    /// Enable object detection
    pub enable_detection: bool,
    /// Enable multi-object tracking
    pub enable_tracking: bool,
    /// Enable OCR processing
    pub enable_ocr: bool,
    /// Enable face recognition
    pub enable_face_recognition: bool,
    /// Enable gesture detection
    pub enable_gesture_detection: bool,
    /// Enable scene understanding
    pub enable_scene_understanding: bool,
    /// Privacy mode enabled
    pub privacy_mode: bool,
    /// Maximum processing latency (ms)
    pub max_latency_ms: u32,
    /// Target frame rate
    pub target_fps: f32,
    /// Maximum memory usage (bytes)
    pub max_memory_bytes: u64,
    /// Detection confidence threshold
    pub detection_confidence_threshold: f32,
    /// NMS threshold for detection
    pub nms_threshold: f32,
    /// Tracking confidence threshold
    pub tracking_confidence_threshold: f32,
    /// Maximum number of tracked objects
    pub max_tracked_objects: u32,
    /// Hardware acceleration preferences
    pub hardware_acceleration: HardwareAcceleration,
}

/// Hardware acceleration options
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HardwareAcceleration {
    /// No hardware acceleration
    None,
    /// CPU-based acceleration (SIMD, etc.)
    Cpu,
    /// GPU-based acceleration (CUDA, OpenCL, etc.)
    Gpu,
    /// Neural Processing Unit acceleration
    Npu,
    /// Automatic selection of best available acceleration
    Auto,
}

/// Main vision system processor
pub struct VisionProcessor {
    config: VisionConfig,
    detector: Arc<dyn detection::ObjectDetector + Send + Sync>,
    tracker: Arc<Mutex<Box<dyn tracking::MultiObjectTracker + Send + Sync>>>,
    ocr_engine: Arc<dyn ocr::OcrEngine + Send + Sync>,
    face_recognizer: Arc<dyn face_recognition::FaceRecognizer + Send + Sync>,
    gesture_detector: Arc<dyn gesture_detection::GestureDetector + Send + Sync>,
    scene_analyzer: Arc<dyn scene_understanding::SceneAnalyzer + Send + Sync>,
    privacy_manager: Arc<Mutex<privacy::PrivacyManager>>,
    metrics: VisionMetrics,
    performance_monitor: PerformanceMonitor,
}

/// Performance monitoring for vision operations
pub struct PerformanceMonitor {
    frame_times: Vec<Duration>,
    detection_times: Vec<Duration>,
    tracking_times: Vec<Duration>,
    ocr_times: Vec<Duration>,
    memory_samples: Vec<u64>,
    start_time: Instant,
}

impl VisionProcessor {
    /// Create new vision processor with configuration
    pub fn new(config: VisionConfig) -> VisionResult<Self> {
        let detector = detection::create_detector(&config)?;
        let tracker = Arc::new(Mutex::new(tracking::create_tracker(&config)?));
        let ocr_engine = ocr::create_ocr_engine(&config)?;
        let face_recognizer = face_recognition::create_face_recognizer(&config)?;
        let gesture_detector = gesture_detection::create_gesture_detector(&config)?;
        let scene_analyzer = scene_understanding::create_scene_analyzer(&config)?;
        let privacy_manager = Arc::new(Mutex::new(privacy::PrivacyManager::new(&config)?));
        
        let metrics = VisionMetrics {
            fps: 0.0,
            avg_detection_latency_ms: 0.0,
            avg_tracking_latency_ms: 0.0,
            avg_ocr_latency_ms: 0.0,
            memory_usage_bytes: 0,
            cpu_utilization: 0.0,
            gpu_utilization: None,
            frames_processed: 0,
            detection_errors: 0,
            tracking_errors: 0,
            privacy_mode_active: config.privacy_mode,
        };
        
        let performance_monitor = PerformanceMonitor {
            frame_times: Vec::with_capacity(1000),
            detection_times: Vec::with_capacity(1000),
            tracking_times: Vec::with_capacity(1000),
            ocr_times: Vec::with_capacity(1000),
            memory_samples: Vec::with_capacity(1000),
            start_time: Instant::now(),
        };
        
        Ok(Self {
            config,
            detector,
            tracker,
            ocr_engine,
            face_recognizer,
            gesture_detector,
            scene_analyzer,
            privacy_manager,
            metrics,
            performance_monitor,
        })
    }
    
    /// Process single frame with all enabled vision capabilities
    pub fn process_frame(&mut self, image: &ImageData) -> VisionResult<VisionFrameResult> {
        let frame_start = Instant::now();
        
        // Privacy check
        if self.config.privacy_mode {
            self.privacy_manager.lock().unwrap().validate_privacy_compliance(image)?;
        }
        
        let mut result = VisionFrameResult {
            detection_result: None,
            tracking_result: None,
            ocr_result: None,
            face_detections: Vec::new(),
            gesture_detections: Vec::new(),
            scene_understanding: None,
            processing_time_ms: 0,
            timestamp: image.timestamp,
        };
        
        // Object detection
        if self.config.enable_detection {
            let detection_start = Instant::now();
            match self.detector.detect(image) {
                Ok(detection_result) => {
                    result.detection_result = Some(detection_result);
                    self.performance_monitor.detection_times.push(detection_start.elapsed());
                }
                Err(e) => {
                    self.metrics.detection_errors += 1;
                    return Err(VisionError::DetectionFailed(e.to_string()));
                }
            }
        }
        
        // Multi-object tracking
        if self.config.enable_tracking && result.detection_result.is_some() {
            let tracking_start = Instant::now();
            match self.tracker.lock().unwrap().update(result.detection_result.as_ref().unwrap()) {
                Ok(tracking_result) => {
                    result.tracking_result = Some(tracking_result);
                    self.performance_monitor.tracking_times.push(tracking_start.elapsed());
                }
                Err(e) => {
                    self.metrics.tracking_errors += 1;
                    return Err(VisionError::TrackingFailed(e.to_string()));
                }
            }
        }
        
        // OCR processing
        if self.config.enable_ocr {
            let ocr_start = Instant::now();
            match self.ocr_engine.process(image) {
                Ok(ocr_result) => {
                    result.ocr_result = Some(ocr_result);
                    self.performance_monitor.ocr_times.push(ocr_start.elapsed());
                }
                Err(e) => {
                    return Err(VisionError::OcrFailed(e.to_string()));
                }
            }
        }
        
        // Face recognition
        if self.config.enable_face_recognition {
            match self.face_recognizer.detect_faces(image) {
                Ok(faces) => result.face_detections = faces,
                Err(e) => return Err(VisionError::FaceRecognitionFailed(e.to_string())),
            }
        }
        
        // Gesture detection
        if self.config.enable_gesture_detection {
            match self.gesture_detector.detect_gestures(image) {
                Ok(gestures) => result.gesture_detections = gestures,
                Err(e) => return Err(VisionError::GestureDetectionFailed(e.to_string())),
            }
        }
        
        // Scene understanding
        if self.config.enable_scene_understanding {
            match self.scene_analyzer.analyze_scene(image, &result) {
                Ok(scene) => result.scene_understanding = Some(scene),
                Err(e) => return Err(VisionError::SceneUnderstandingFailed(e.to_string())),
            }
        }
        
        let frame_time = frame_start.elapsed();
        result.processing_time_ms = frame_time.as_millis() as u32;
        
        // Update performance metrics
        self.update_metrics(frame_time);
        
        // Privacy cleanup
        if self.config.privacy_mode {
            self.privacy_manager.lock().unwrap().secure_cleanup(image)?;
        }
        
        // Performance validation
        if result.processing_time_ms > self.config.max_latency_ms {
            return Err(VisionError::PerformanceViolation(
                format!("Frame processing took {}ms, exceeds limit of {}ms", 
                       result.processing_time_ms, self.config.max_latency_ms)
            ));
        }
        
        Ok(result)
    }
    
    /// Update performance metrics
    fn update_metrics(&mut self, frame_time: Duration) {
        self.performance_monitor.frame_times.push(frame_time);
        self.metrics.frames_processed += 1;
        
        // Calculate rolling averages
        if self.performance_monitor.frame_times.len() > 100 {
            self.performance_monitor.frame_times.remove(0);
        }
        
        let avg_frame_time = self.performance_monitor.frame_times.iter()
            .map(|d| d.as_secs_f32())
            .sum::<f32>() / self.performance_monitor.frame_times.len() as f32;
        
        self.metrics.fps = 1.0 / avg_frame_time;
        
        if !self.performance_monitor.detection_times.is_empty() {
            self.metrics.avg_detection_latency_ms = 
                self.performance_monitor.detection_times.iter()
                    .map(|d| d.as_millis() as f32)
                    .sum::<f32>() / self.performance_monitor.detection_times.len() as f32;
        }
        
        if !self.performance_monitor.tracking_times.is_empty() {
            self.metrics.avg_tracking_latency_ms = 
                self.performance_monitor.tracking_times.iter()
                    .map(|d| d.as_millis() as f32)
                    .sum::<f32>() / self.performance_monitor.tracking_times.len() as f32;
        }
        
        if !self.performance_monitor.ocr_times.is_empty() {
            self.metrics.avg_ocr_latency_ms = 
                self.performance_monitor.ocr_times.iter()
                    .map(|d| d.as_millis() as f32)
                    .sum::<f32>() / self.performance_monitor.ocr_times.len() as f32;
        }
    }
    
    /// Get current performance metrics
    pub fn get_metrics(&self) -> &VisionMetrics {
        &self.metrics
    }
    
    /// Update configuration
    pub fn update_config(&mut self, config: VisionConfig) -> VisionResult<()> {
        // Validate configuration
        if config.max_latency_ms == 0 {
            return Err(VisionError::ConfigurationError(
                "Maximum latency must be greater than 0".to_string()
            ));
        }
        
        if config.target_fps <= 0.0 {
            return Err(VisionError::ConfigurationError(
                "Target FPS must be greater than 0".to_string()
            ));
        }
        
        self.config = config;
        self.metrics.privacy_mode_active = self.config.privacy_mode;
        
        Ok(())
    }
    
    /// Enable privacy mode
    pub fn enable_privacy_mode(&mut self) -> VisionResult<()> {
        self.config.privacy_mode = true;
        self.metrics.privacy_mode_active = true;
        self.privacy_manager.lock().unwrap().enable_privacy_mode()?;
        Ok(())
    }
    
    /// Disable privacy mode
    pub fn disable_privacy_mode(&mut self) -> VisionResult<()> {
        self.config.privacy_mode = false;
        self.metrics.privacy_mode_active = false;
        self.privacy_manager.lock().unwrap().disable_privacy_mode()?;
        Ok(())
    }
}

/// Complete vision processing result for a single frame
#[derive(Debug, Clone)]
pub struct VisionFrameResult {
    /// Object detection results
    pub detection_result: Option<DetectionResult>,
    /// Multi-object tracking results
    pub tracking_result: Option<TrackingResult>,
    /// OCR processing results
    pub ocr_result: Option<OcrResult>,
    /// Face detection and recognition results
    pub face_detections: Vec<FaceDetection>,
    /// Gesture detection results
    pub gesture_detections: Vec<GestureDetection>,
    /// Scene understanding results
    pub scene_understanding: Option<SceneUnderstanding>,
    /// Total processing time in milliseconds
    pub processing_time_ms: u32,
    /// Frame timestamp
    pub timestamp: Instant,
}

impl Default for VisionConfig {
    fn default() -> Self {
        Self {
            enable_detection: true,
            enable_tracking: true,
            enable_ocr: true,
            enable_face_recognition: true,
            enable_gesture_detection: true,
            enable_scene_understanding: true,
            privacy_mode: false,
            max_latency_ms: 40, // 40ms for 24+ FPS
            target_fps: 30.0,
            max_memory_bytes: 1024 * 1024 * 1024, // 1GB
            detection_confidence_threshold: 0.5,
            nms_threshold: 0.4,
            tracking_confidence_threshold: 0.7,
            max_tracked_objects: 100,
            hardware_acceleration: HardwareAcceleration::Auto,
        }
    }
}

/// Utility functions for bounding box operations
pub mod bbox_utils {
    use super::BoundingBox;
    
    /// Calculate intersection over union (IoU) between two bounding boxes
    pub fn calculate_iou(box1: &BoundingBox, box2: &BoundingBox) -> f32 {
        let x1 = box1.x.max(box2.x);
        let y1 = box1.y.max(box2.y);
        let x2 = (box1.x + box1.width).min(box2.x + box2.width);
        let y2 = (box1.y + box1.height).min(box2.y + box2.height);
        
        if x2 <= x1 || y2 <= y1 {
            return 0.0;
        }
        
        let intersection = (x2 - x1) * (y2 - y1);
        let area1 = box1.width * box1.height;
        let area2 = box2.width * box2.height;
        let union = area1 + area2 - intersection;
        
        if union <= 0.0 {
            0.0
        } else {
            intersection / union
        }
    }
    
    /// Convert bounding box from center format (x, y, w, h) to corner format (x1, y1, x2, y2)
    pub fn center_to_corner(x: f32, y: f32, w: f32, h: f32) -> (f32, f32, f32, f32) {
        let x1 = x - w / 2.0;
        let y1 = y - h / 2.0;
        let x2 = x + w / 2.0;
        let y2 = y + h / 2.0;
        (x1, y1, x2, y2)
    }
    
    /// Convert bounding box from corner format (x1, y1, x2, y2) to center format (x, y, w, h)
    pub fn corner_to_center(x1: f32, y1: f32, x2: f32, y2: f32) -> (f32, f32, f32, f32) {
        let x = (x1 + x2) / 2.0;
        let y = (y1 + y2) / 2.0;
        let w = x2 - x1;
        let h = y2 - y1;
        (x, y, w, h)
    }
    
    /// Clip bounding box to image boundaries
    pub fn clip_bbox(bbox: &mut BoundingBox, img_width: u32, img_height: u32) {
        bbox.x = bbox.x.max(0.0).min(img_width as f32);
        bbox.y = bbox.y.max(0.0).min(img_height as f32);
        bbox.width = bbox.width.min(img_width as f32 - bbox.x);
        bbox.height = bbox.height.min(img_height as f32 - bbox.y);
    }
    
    /// Scale bounding box coordinates
    pub fn scale_bbox(bbox: &mut BoundingBox, scale_x: f32, scale_y: f32) {
        bbox.x *= scale_x;
        bbox.y *= scale_y;
        bbox.width *= scale_x;
        bbox.height *= scale_y;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use super::bbox_utils::*;
    
    #[test]
    fn test_iou_calculation() {
        let box1 = BoundingBox {
            x: 10.0, y: 10.0, width: 20.0, height: 20.0,
            confidence: 0.9, class_id: 0, class_name: "test".to_string(),
        };
        
        let box2 = BoundingBox {
            x: 15.0, y: 15.0, width: 20.0, height: 20.0,
            confidence: 0.8, class_id: 0, class_name: "test".to_string(),
        };
        
        let iou = calculate_iou(&box1, &box2);
        assert!(iou > 0.0 && iou < 1.0);
    }
    
    #[test]
    fn test_bbox_conversion() {
        let (x1, y1, x2, y2) = center_to_corner(50.0, 50.0, 20.0, 30.0);
        assert_eq!((x1, y1, x2, y2), (40.0, 35.0, 60.0, 65.0));
        
        let (x, y, w, h) = corner_to_center(40.0, 35.0, 60.0, 65.0);
        assert_eq!((x, y, w, h), (50.0, 50.0, 20.0, 30.0));
    }
    
    #[test]
    fn test_bbox_clipping() {
        let mut bbox = BoundingBox {
            x: -5.0, y: -5.0, width: 50.0, height: 50.0,
            confidence: 0.9, class_id: 0, class_name: "test".to_string(),
        };
        
        clip_bbox(&mut bbox, 100, 100);
        assert!(bbox.x >= 0.0 && bbox.y >= 0.0);
        assert!(bbox.x + bbox.width <= 100.0);
        assert!(bbox.y + bbox.height <= 100.0);
    }
}