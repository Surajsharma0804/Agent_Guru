"""
GuruVision Custom Face Detection Module

This module provides a custom face detection implementation using ONNX Runtime
directly with RetinaFace models. This is a proprietary implementation for
GuruVision facial recognition system.

Requirements: 3.5, 26.4
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional
import numpy as np
import cv2
import os
import logging

from guru_vision.exceptions import DetectionError, InitializationError

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """
    Represents a detected face with bounding box, landmarks, and confidence.
    
    Attributes:
        bbox: Bounding box coordinates as (x, y, w, h)
        landmarks: 5-point facial landmarks (left_eye, right_eye, nose, left_mouth, right_mouth)
                   Shape: (5, 2) array with x, y coordinates for each landmark
        confidence: Detection confidence score (0.0 to 1.0)
    """
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    landmarks: np.ndarray  # (5, 2) array
    confidence: float


class FaceDetector:
    """
    GuruVision Custom Face Detector using ONNX Runtime.
    
    This is a proprietary implementation that uses RetinaFace ONNX models
    directly without relying on high-level APIs. Provides full control over
    the detection pipeline for patent purposes.
    
    Requirements: 3.5, 26.4
    """
    
    def __init__(self, model_path: Optional[str] = None, use_gpu: bool = True):
        """
        Initialize the custom face detector.
        
        Args:
            model_path: Path to the ONNX detection model. If None, uses default location.
            use_gpu: Whether to use GPU acceleration if available (default: True)
        
        Raises:
            InitializationError: If required dependencies are not installed or model initialization fails
        """
        try:
            import onnxruntime as ort
        except ImportError:
            raise InitializationError(
                "ONNX Runtime is not installed. Please install it with: "
                "pip install onnxruntime or onnxruntime-gpu"
            )
        
        try:
            # Set default model path if not provided
            if model_path is None:
                # Use the downloaded InsightFace model as base
                home = os.path.expanduser("~")
                model_path = os.path.join(home, ".insightface", "models", "buffalo_l", "det_10g.onnx")
            
            if not os.path.exists(model_path):
                raise InitializationError(
                    f"Model file not found at {model_path}. "
                    "Please ensure the model is downloaded."
                )
            
            # Configure ONNX Runtime session
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            
            # Set execution providers
            if use_gpu:
                providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            else:
                providers = ['CPUExecutionProvider']
            
            # Create inference session
            self.session = ort.InferenceSession(model_path, sess_options, providers=providers)
            
            # Get model input/output details
            self.input_name = self.session.get_inputs()[0].name
            self.input_shape = self.session.get_inputs()[0].shape
            self.output_names = [output.name for output in self.session.get_outputs()]
            
            self.use_gpu = use_gpu
            self.model_path = model_path
            self.det_size = (640, 640)
            
            # Anchor configuration for RetinaFace
            self._init_anchors()
            
            logger.info(f"Face detector initialized successfully with model: {model_path}")
            
        except InitializationError:
            # Re-raise InitializationError as-is
            raise
        except Exception as e:
            logger.error(f"Failed to initialize face detector: {e}")
            raise InitializationError(f"Failed to initialize face detector: {e}") from e
    
    def _init_anchors(self):
        """Initialize anchor boxes for RetinaFace detection."""
        # RetinaFace uses anchor-based detection
        # Feature pyramid network with strides [8, 16, 32]
        self.fmc = 3  # Number of feature map levels
        self._feat_stride_fpn = [8, 16, 32]
        self._num_anchors = 2  # Number of anchors per location
        
        # Anchor ratios for each stride
        self._anchor_cfg = {
            '32': {'SCALES': (32, 16), 'BASE_SIZE': 16, 'RATIOS': (1.0,), 'ALLOWED_BORDER': 9999},
            '16': {'SCALES': (8, 4), 'BASE_SIZE': 16, 'RATIOS': (1.0,), 'ALLOWED_BORDER': 9999},
            '8': {'SCALES': (2, 1), 'BASE_SIZE': 16, 'RATIOS': (1.0,), 'ALLOWED_BORDER': 9999},
        }
    
    def _preprocess(self, img: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Preprocess image for detection.
        
        Args:
            img: Input image in BGR format
        
        Returns:
            Tuple of (preprocessed_image, scale_factor)
        """
        # Resize image to detection size while maintaining aspect ratio
        im_ratio = float(img.shape[0]) / img.shape[1]
        model_ratio = float(self.det_size[1]) / self.det_size[0]
        
        if im_ratio > model_ratio:
            new_height = self.det_size[1]
            new_width = int(new_height / im_ratio)
        else:
            new_width = self.det_size[0]
            new_height = int(new_width * im_ratio)
        
        det_scale = float(new_height) / img.shape[0]
        resized_img = cv2.resize(img, (new_width, new_height))
        
        # Pad to detection size
        det_img = np.zeros((self.det_size[1], self.det_size[0], 3), dtype=np.uint8)
        det_img[:new_height, :new_width, :] = resized_img
        
        # Normalize and transpose to CHW format
        det_img = det_img.astype(np.float32)
        det_img = (det_img - 127.5) / 128.0
        det_img = np.transpose(det_img, (2, 0, 1))
        det_img = np.expand_dims(det_img, axis=0)
        
        return det_img, det_scale
    
    def _postprocess(self, net_out: List[np.ndarray], det_scale: float, 
                     threshold: float) -> List[Detection]:
        """
        Post-process network outputs to extract detections.
        
        Args:
            net_out: Raw network outputs
            det_scale: Scale factor used in preprocessing
            threshold: Confidence threshold
        
        Returns:
            List of Detection objects
        """
        proposals_list = []
        scores_list = []
        landmarks_list = []
        
        # Process each feature pyramid level
        for idx, stride in enumerate(self._feat_stride_fpn):
            # Extract scores, bbox deltas, and landmark deltas
            scores = net_out[idx]
            bbox_deltas = net_out[idx + self.fmc]
            landmark_deltas = net_out[idx + self.fmc * 2]
            
            height, width = self.det_size[1] // stride, self.det_size[0] // stride
            
            # Generate anchors for this level
            anchors = self._generate_anchors(height, width, stride)
            
            # Apply deltas to anchors
            proposals = self._bbox_pred(anchors, bbox_deltas)
            proposals[:, 0:4] /= det_scale
            
            # Apply deltas to landmarks
            landmarks = self._landmark_pred(anchors, landmark_deltas)
            landmarks[:, :, 0:2] /= det_scale
            
            # Filter by threshold
            scores = scores.ravel()
            order = np.where(scores >= threshold)[0]
            
            proposals = proposals[order, :]
            landmarks = landmarks[order, :, :]
            scores = scores[order]
            
            proposals_list.append(proposals)
            scores_list.append(scores)
            landmarks_list.append(landmarks)
        
        # Concatenate all levels
        proposals = np.vstack(proposals_list)
        landmarks = np.vstack(landmarks_list)
        scores = np.hstack(scores_list)
        
        # Apply NMS
        keep = self._nms(proposals, scores, 0.4)
        
        # Create Detection objects
        detections = []
        for i in keep:
            bbox = proposals[i, :4].astype(int)
            x1, y1, x2, y2 = bbox
            x, y, w, h = x1, y1, x2 - x1, y2 - y1
            
            detection = Detection(
                bbox=(x, y, w, h),
                landmarks=landmarks[i].astype(np.float32),
                confidence=float(scores[i])
            )
            detections.append(detection)
        
        return detections
    
    def _generate_anchors(self, height: int, width: int, stride: int) -> np.ndarray:
        """Generate anchor boxes for a feature map level."""
        anchor_cfg = self._anchor_cfg[str(stride)]
        base_size = anchor_cfg['BASE_SIZE']
        scales = np.array(anchor_cfg['SCALES'])
        
        # Generate base anchors
        base_anchors = []
        for scale in scales:
            size = base_size * scale
            base_anchors.append([0, 0, size - 1, size - 1])
        base_anchors = np.array(base_anchors, dtype=np.float32)
        
        # Generate all anchors
        shift_x = np.arange(0, width) * stride
        shift_y = np.arange(0, height) * stride
        shift_x, shift_y = np.meshgrid(shift_x, shift_y)
        shifts = np.vstack((shift_x.ravel(), shift_y.ravel(),
                           shift_x.ravel(), shift_y.ravel())).transpose()
        
        anchors = base_anchors.reshape((1, len(base_anchors), 4)) + \
                  shifts.reshape((len(shifts), 1, 4))
        anchors = anchors.reshape((len(shifts) * len(base_anchors), 4))
        
        return anchors
    
    def _bbox_pred(self, anchors: np.ndarray, deltas: np.ndarray) -> np.ndarray:
        """Apply bounding box deltas to anchors."""
        # Check if deltas need reshaping (4D from ONNX) or are already 2D
        if deltas.ndim == 4:
            # Reshape from (batch, channels, height, width) to (N, 4)
            deltas = deltas.transpose((0, 2, 3, 1)).reshape((-1, 4))
        elif deltas.ndim == 2:
            # Already in correct shape (N, 4)
            pass
        else:
            raise ValueError(f"Unexpected deltas shape: {deltas.shape}")
        
        widths = anchors[:, 2] - anchors[:, 0] + 1.0
        heights = anchors[:, 3] - anchors[:, 1] + 1.0
        ctr_x = anchors[:, 0] + 0.5 * widths
        ctr_y = anchors[:, 1] + 0.5 * heights
        
        dx = deltas[:, 0]
        dy = deltas[:, 1]
        dw = deltas[:, 2]
        dh = deltas[:, 3]
        
        pred_ctr_x = dx * widths + ctr_x
        pred_ctr_y = dy * heights + ctr_y
        pred_w = np.exp(dw) * widths
        pred_h = np.exp(dh) * heights
        
        pred_boxes = np.zeros(deltas.shape, dtype=deltas.dtype)
        pred_boxes[:, 0] = pred_ctr_x - 0.5 * pred_w
        pred_boxes[:, 1] = pred_ctr_y - 0.5 * pred_h
        pred_boxes[:, 2] = pred_ctr_x + 0.5 * pred_w
        pred_boxes[:, 3] = pred_ctr_y + 0.5 * pred_h
        
        return pred_boxes
    
    def _landmark_pred(self, anchors: np.ndarray, deltas: np.ndarray) -> np.ndarray:
        """Apply landmark deltas to anchors."""
        # Check if deltas need reshaping (4D from ONNX) or are already 2D
        if deltas.ndim == 4:
            # Reshape from (batch, channels, height, width) to (N, 10)
            deltas = deltas.transpose((0, 2, 3, 1)).reshape((-1, 10))
        elif deltas.ndim == 2:
            # Already in correct shape (N, 10)
            pass
        else:
            raise ValueError(f"Unexpected deltas shape: {deltas.shape}")
        
        widths = anchors[:, 2] - anchors[:, 0] + 1.0
        heights = anchors[:, 3] - anchors[:, 1] + 1.0
        ctr_x = anchors[:, 0] + 0.5 * widths
        ctr_y = anchors[:, 1] + 0.5 * heights
        
        landmarks = np.zeros((deltas.shape[0], 5, 2), dtype=deltas.dtype)
        for i in range(5):
            landmarks[:, i, 0] = deltas[:, i * 2] * widths + ctr_x
            landmarks[:, i, 1] = deltas[:, i * 2 + 1] * heights + ctr_y
        
        return landmarks
    
    def _nms(self, dets: np.ndarray, scores: np.ndarray, thresh: float) -> List[int]:
        """Non-maximum suppression."""
        x1 = dets[:, 0]
        y1 = dets[:, 1]
        x2 = dets[:, 2]
        y2 = dets[:, 3]
        
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores.argsort()[::-1]
        
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            
            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            inter = w * h
            
            ovr = inter / (areas[i] + areas[order[1:]] - inter)
            
            inds = np.where(ovr <= thresh)[0]
            order = order[inds + 1]
        
        return keep
    
    def detect(self, frame: np.ndarray, confidence_threshold: float = 0.5) -> List[Detection]:
        """
        Detect all faces in the given frame.
        
        This is a custom implementation using ONNX Runtime directly for
        full control over the detection pipeline.
        
        Requirements: 3.1, 3.3, 3.4
        
        Args:
            frame: Input image as numpy array in BGR format (OpenCV format)
            confidence_threshold: Minimum confidence score for detections (default: 0.5)
        
        Returns:
            List of Detection objects, one for each detected face.
            Returns empty list if no faces are detected.
        
        Raises:
            DetectionError: If frame is invalid or detection fails
        """
        try:
            if frame is None or frame.size == 0:
                raise DetectionError("Invalid frame: frame is None or empty")
            
            # Preprocess
            input_blob, det_scale = self._preprocess(frame)
            
            # Run inference
            net_out = self.session.run(self.output_names, {self.input_name: input_blob})
            
            # Postprocess
            detections = self._postprocess(net_out, det_scale, confidence_threshold)
            
            logger.debug(f"Detected {len(detections)} faces in frame")
            
            return detections
            
        except DetectionError:
            # Re-raise DetectionError as-is
            raise
        except Exception as e:
            logger.error(f"Face detection failed: {e}")
            raise DetectionError(f"Face detection failed: {e}") from e
