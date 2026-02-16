"""
Object Detection Module

Provides YOLO-based object detection for 80 COCO classes using ONNX Runtime.
Supports confidence filtering, non-maximum suppression, and multi-scale detection.
"""

from .yolo_detector import YOLODetector, DetectedObject
from .nms import non_max_suppression, nms_per_class
from .bbox_utils import (
    compute_iou,
    scale_boxes,
    clip_boxes,
    box_area,
    xywh_to_xyxy,
    xyxy_to_xywh
)

__all__ = [
    'YOLODetector',
    'DetectedObject',
    'non_max_suppression',
    'nms_per_class',
    'compute_iou',
    'scale_boxes',
    'clip_boxes',
    'box_area',
    'xywh_to_xyxy',
    'xyxy_to_xywh'
]
