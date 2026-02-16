"""
Bounding Box Utilities

Provides utility functions for bounding box operations including:
- IoU computation
- Box scaling and clipping
- Box area calculation
"""

import numpy as np
from typing import Tuple, List


def compute_iou(box1: Tuple[float, float, float, float],
                box2: Tuple[float, float, float, float]) -> float:
    """
    Compute Intersection over Union (IoU) between two bounding boxes.
    
    Args:
        box1: First box as (x1, y1, x2, y2)
        box2: Second box as (x1, y1, x2, y2)
    
    Returns:
        IoU score between 0.0 and 1.0
    """
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    
    # Compute intersection area
    inter_x_min = max(x1_min, x2_min)
    inter_y_min = max(y1_min, y2_min)
    inter_x_max = min(x1_max, x2_max)
    inter_y_max = min(y1_max, y2_max)
    
    if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
        return 0.0
    
    inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
    
    # Compute union area
    box1_area = (x1_max - x1_min) * (y1_max - y1_min)
    box2_area = (x2_max - x2_min) * (y2_max - y2_min)
    union_area = box1_area + box2_area - inter_area
    
    if union_area == 0:
        return 0.0
    
    return inter_area / union_area


def box_area(box: Tuple[float, float, float, float]) -> float:
    """
    Compute area of a bounding box.
    
    Args:
        box: Box as (x1, y1, x2, y2)
    
    Returns:
        Area of the box
    """
    x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def scale_boxes(boxes: np.ndarray,
                original_shape: Tuple[int, int],
                target_shape: Tuple[int, int]) -> np.ndarray:
    """
    Scale bounding boxes from one image size to another.
    
    Args:
        boxes: Array of boxes with shape (N, 4) as (x1, y1, x2, y2)
        original_shape: Original image shape as (height, width)
        target_shape: Target image shape as (height, width)
    
    Returns:
        Scaled boxes with same shape as input
    """
    if len(boxes) == 0:
        return boxes
    
    orig_h, orig_w = original_shape
    target_h, target_w = target_shape
    
    scale_x = target_w / orig_w
    scale_y = target_h / orig_h
    
    scaled_boxes = boxes.astype(np.float32).copy()
    scaled_boxes[:, [0, 2]] *= scale_x  # Scale x coordinates
    scaled_boxes[:, [1, 3]] *= scale_y  # Scale y coordinates
    
    return scaled_boxes


def clip_boxes(boxes: np.ndarray,
               image_shape: Tuple[int, int]) -> np.ndarray:
    """
    Clip bounding boxes to image boundaries.
    
    Args:
        boxes: Array of boxes with shape (N, 4) as (x1, y1, x2, y2)
        image_shape: Image shape as (height, width)
    
    Returns:
        Clipped boxes with same shape as input
    """
    if len(boxes) == 0:
        return boxes
    
    height, width = image_shape
    
    clipped_boxes = boxes.copy()
    clipped_boxes[:, [0, 2]] = np.clip(clipped_boxes[:, [0, 2]], 0, width)
    clipped_boxes[:, [1, 3]] = np.clip(clipped_boxes[:, [1, 3]], 0, height)
    
    return clipped_boxes


def xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    """
    Convert boxes from (x_center, y_center, width, height) to (x1, y1, x2, y2).
    
    Args:
        boxes: Array of boxes with shape (N, 4) as (x_center, y_center, w, h)
    
    Returns:
        Converted boxes as (x1, y1, x2, y2)
    """
    if len(boxes) == 0:
        return boxes
    
    converted = boxes.copy()
    converted[:, 0] = boxes[:, 0] - boxes[:, 2] / 2  # x1 = x_center - w/2
    converted[:, 1] = boxes[:, 1] - boxes[:, 3] / 2  # y1 = y_center - h/2
    converted[:, 2] = boxes[:, 0] + boxes[:, 2] / 2  # x2 = x_center + w/2
    converted[:, 3] = boxes[:, 1] + boxes[:, 3] / 2  # y2 = y_center + h/2
    
    return converted


def xyxy_to_xywh(boxes: np.ndarray) -> np.ndarray:
    """
    Convert boxes from (x1, y1, x2, y2) to (x_center, y_center, width, height).
    
    Args:
        boxes: Array of boxes with shape (N, 4) as (x1, y1, x2, y2)
    
    Returns:
        Converted boxes as (x_center, y_center, w, h)
    """
    if len(boxes) == 0:
        return boxes
    
    converted = boxes.copy()
    converted[:, 0] = (boxes[:, 0] + boxes[:, 2]) / 2  # x_center
    converted[:, 1] = (boxes[:, 1] + boxes[:, 3]) / 2  # y_center
    converted[:, 2] = boxes[:, 2] - boxes[:, 0]  # width
    converted[:, 3] = boxes[:, 3] - boxes[:, 1]  # height
    
    return converted
