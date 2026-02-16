"""
YOLO Object Detector

Implements YOLO-based object detection using ONNX Runtime.
Supports 80 COCO classes with confidence filtering and NMS.
"""

import numpy as np
import cv2
from dataclasses import dataclass
from typing import List, Tuple, Optional
import logging

from .nms import nms_per_class
from .bbox_utils import xywh_to_xyxy, scale_boxes, clip_boxes


# COCO class names (80 classes)
COCO_CLASSES = [
    'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
    'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
    'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
    'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
    'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
    'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
    'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
    'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator',
    'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]


logger = logging.getLogger(__name__)


@dataclass
class DetectedObject:
    """
    Represents a detected object.
    
    Attributes:
        class_id: Class ID (0-79 for COCO)
        class_name: Human-readable class name
        confidence: Detection confidence (0.0-1.0)
        bbox: Bounding box as (x1, y1, x2, y2)
    """
    class_id: int
    class_name: str
    confidence: float
    bbox: Tuple[float, float, float, float]


class YOLODetector:
    """
    YOLO object detector using ONNX Runtime.
    
    This detector can work with or without a model file:
    - With model: Performs actual YOLO detection
    - Without model: Returns empty detections (graceful degradation)
    """
    
    def __init__(self,
                 model_path: Optional[str] = None,
                 confidence_threshold: float = 0.5,
                 nms_threshold: float = 0.4,
                 input_size: Tuple[int, int] = (640, 640),
                 use_gpu: bool = False):
        """
        Initialize YOLO detector.
        
        Args:
            model_path: Path to YOLO ONNX model (optional)
            confidence_threshold: Minimum confidence for detections
            nms_threshold: IoU threshold for NMS
            input_size: Model input size as (height, width)
            use_gpu: Whether to use GPU acceleration
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold
        self.input_size = input_size
        self.use_gpu = use_gpu
        
        self.session = None
        self.model_loaded = False
        
        # Try to load model if path provided
        if model_path:
            try:
                self._load_model()
            except Exception as e:
                logger.warning(f"Failed to load YOLO model from {model_path}: {e}")
                logger.info("Object detection will return empty results")
    
    def _load_model(self) -> None:
        """Load YOLO ONNX model."""
        try:
            import onnxruntime as ort
            
            # Set execution providers
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider'] if self.use_gpu else ['CPUExecutionProvider']
            
            # Create session
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            self.model_loaded = True
            
            logger.info(f"YOLO model loaded successfully from {self.model_path}")
            logger.info(f"Using providers: {self.session.get_providers()}")
            
        except ImportError:
            logger.error("onnxruntime not installed. Install with: pip install onnxruntime")
            raise
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
    
    def detect(self, image: np.ndarray) -> List[DetectedObject]:
        """
        Detect objects in an image.
        
        Args:
            image: Input image in BGR format (OpenCV format)
        
        Returns:
            List of detected objects
        """
        # If model not loaded, return empty list (graceful degradation)
        if not self.model_loaded or self.session is None:
            return []
        
        # Preprocess image
        input_tensor, scale_factors = self._preprocess(image)
        
        # Run inference
        try:
            outputs = self.session.run(None, {self.session.get_inputs()[0].name: input_tensor})
            predictions = outputs[0]
        except Exception as e:
            logger.error(f"YOLO inference failed: {e}")
            return []
        
        # Post-process predictions
        detections = self._postprocess(predictions, image.shape[:2], scale_factors)
        
        return detections
    
    def _preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, Tuple[float, float]]:
        """
        Preprocess image for YOLO model.
        
        Args:
            image: Input image in BGR format
        
        Returns:
            Tuple of (preprocessed tensor, scale factors)
        """
        # Get original dimensions
        orig_h, orig_w = image.shape[:2]
        target_h, target_w = self.input_size
        
        # Calculate scale factors
        scale_x = target_w / orig_w
        scale_y = target_h / orig_h
        
        # Resize image
        resized = cv2.resize(image, (target_w, target_h))
        
        # Convert BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1]
        normalized = rgb.astype(np.float32) / 255.0
        
        # Transpose to CHW format
        transposed = np.transpose(normalized, (2, 0, 1))
        
        # Add batch dimension
        batched = np.expand_dims(transposed, axis=0)
        
        return batched, (scale_x, scale_y)
    
    def _postprocess(self,
                    predictions: np.ndarray,
                    original_shape: Tuple[int, int],
                    scale_factors: Tuple[float, float]) -> List[DetectedObject]:
        """
        Post-process YOLO predictions.
        
        Args:
            predictions: Raw model predictions
            original_shape: Original image shape as (height, width)
            scale_factors: Scale factors used in preprocessing
        
        Returns:
            List of detected objects
        """
        # predictions shape: (batch, num_predictions, 85)
        # 85 = 4 (bbox) + 1 (objectness) + 80 (class scores)
        
        if len(predictions.shape) == 3:
            predictions = predictions[0]  # Remove batch dimension
        
        # Extract components
        boxes = predictions[:, :4]  # (x_center, y_center, w, h)
        objectness = predictions[:, 4]
        class_scores = predictions[:, 5:]
        
        # Get class IDs and confidences
        class_ids = np.argmax(class_scores, axis=1)
        class_confidences = np.max(class_scores, axis=1)
        
        # Compute final confidence (objectness * class_confidence)
        confidences = objectness * class_confidences
        
        # Filter by confidence threshold
        conf_mask = confidences >= self.confidence_threshold
        boxes = boxes[conf_mask]
        confidences = confidences[conf_mask]
        class_ids = class_ids[conf_mask]
        
        if len(boxes) == 0:
            return []
        
        # Convert boxes from xywh to xyxy format
        boxes = xywh_to_xyxy(boxes)
        
        # Scale boxes back to original image size
        scale_x, scale_y = scale_factors
        boxes[:, [0, 2]] /= scale_x
        boxes[:, [1, 3]] /= scale_y
        
        # Clip boxes to image boundaries
        boxes = clip_boxes(boxes, original_shape)
        
        # Apply NMS per class
        keep_indices = nms_per_class(boxes, confidences, class_ids, self.nms_threshold)
        
        # Create DetectedObject instances
        detections = []
        for idx in keep_indices:
            detection = DetectedObject(
                class_id=int(class_ids[idx]),
                class_name=COCO_CLASSES[class_ids[idx]],
                confidence=float(confidences[idx]),
                bbox=(
                    float(boxes[idx, 0]),
                    float(boxes[idx, 1]),
                    float(boxes[idx, 2]),
                    float(boxes[idx, 3])
                )
            )
            detections.append(detection)
        
        return detections
    
    def set_confidence_threshold(self, threshold: float) -> None:
        """Set confidence threshold for detections."""
        if not (0.0 <= threshold <= 1.0):
            raise ValueError("Confidence threshold must be between 0.0 and 1.0")
        self.confidence_threshold = threshold
    
    def set_nms_threshold(self, threshold: float) -> None:
        """Set NMS IoU threshold."""
        if not (0.0 <= threshold <= 1.0):
            raise ValueError("NMS threshold must be between 0.0 and 1.0")
        self.nms_threshold = threshold
