"""
Non-Maximum Suppression (NMS)

Implements NMS algorithm for removing duplicate detections.
"""

import numpy as np
from typing import List, Tuple
from .bbox_utils import compute_iou


def non_max_suppression(boxes: np.ndarray,
                       scores: np.ndarray,
                       iou_threshold: float = 0.4) -> List[int]:
    """
    Apply Non-Maximum Suppression to remove duplicate detections.
    
    Args:
        boxes: Array of bounding boxes with shape (N, 4) as (x1, y1, x2, y2)
        scores: Array of confidence scores with shape (N,)
        iou_threshold: IoU threshold for suppression (default: 0.4)
    
    Returns:
        List of indices to keep
    """
    if len(boxes) == 0:
        return []
    
    # Sort by scores in descending order
    sorted_indices = np.argsort(scores)[::-1]
    
    keep_indices = []
    
    while len(sorted_indices) > 0:
        # Pick the box with highest score
        current_idx = sorted_indices[0]
        keep_indices.append(current_idx)
        
        if len(sorted_indices) == 1:
            break
        
        # Compute IoU with remaining boxes
        current_box = boxes[current_idx]
        remaining_boxes = boxes[sorted_indices[1:]]
        
        ious = np.array([
            compute_iou(current_box, box)
            for box in remaining_boxes
        ])
        
        # Keep boxes with IoU below threshold
        keep_mask = ious < iou_threshold
        sorted_indices = sorted_indices[1:][keep_mask]
    
    return keep_indices


def nms_per_class(boxes: np.ndarray,
                  scores: np.ndarray,
                  class_ids: np.ndarray,
                  iou_threshold: float = 0.4) -> List[int]:
    """
    Apply NMS separately for each class.
    
    Args:
        boxes: Array of bounding boxes with shape (N, 4) as (x1, y1, x2, y2)
        scores: Array of confidence scores with shape (N,)
        class_ids: Array of class IDs with shape (N,)
        iou_threshold: IoU threshold for suppression
    
    Returns:
        List of indices to keep
    """
    if len(boxes) == 0:
        return []
    
    keep_indices = []
    unique_classes = np.unique(class_ids)
    
    for class_id in unique_classes:
        # Get indices for this class
        class_mask = class_ids == class_id
        class_indices = np.where(class_mask)[0]
        
        if len(class_indices) == 0:
            continue
        
        # Apply NMS for this class
        class_boxes = boxes[class_indices]
        class_scores = scores[class_indices]
        
        class_keep = non_max_suppression(class_boxes, class_scores, iou_threshold)
        
        # Convert back to original indices
        keep_indices.extend(class_indices[class_keep].tolist())
    
    return keep_indices
