"""
Unit tests for Object Detection module

Tests YOLO detector, NMS, and bounding box utilities.
"""

import pytest
import numpy as np
from guru_vision.object_detection import (
    YOLODetector,
    DetectedObject,
    non_max_suppression,
    nms_per_class,
    compute_iou,
    scale_boxes,
    clip_boxes,
    box_area,
    xywh_to_xyxy,
    xyxy_to_xywh
)


class TestBBoxUtils:
    """Test bounding box utility functions"""
    
    def test_compute_iou_no_overlap(self):
        """Test IoU with no overlap"""
        box1 = (0, 0, 10, 10)
        box2 = (20, 20, 30, 30)
        assert compute_iou(box1, box2) == 0.0
    
    def test_compute_iou_full_overlap(self):
        """Test IoU with full overlap"""
        box1 = (0, 0, 10, 10)
        box2 = (0, 0, 10, 10)
        assert compute_iou(box1, box2) == 1.0
    
    def test_compute_iou_partial_overlap(self):
        """Test IoU with partial overlap"""
        box1 = (0, 0, 10, 10)
        box2 = (5, 5, 15, 15)
        iou = compute_iou(box1, box2)
        assert 0.0 < iou < 1.0
        # Expected: intersection = 25, union = 175, IoU = 25/175 ≈ 0.143
        assert abs(iou - 0.143) < 0.01
    
    def test_box_area(self):
        """Test box area calculation"""
        box = (0, 0, 10, 10)
        assert box_area(box) == 100.0
        
        box = (5, 5, 15, 20)
        assert box_area(box) == 150.0
    
    def test_box_area_invalid(self):
        """Test box area with invalid box"""
        box = (10, 10, 5, 5)  # x2 < x1, y2 < y1
        assert box_area(box) == 0.0
    
    def test_scale_boxes_empty(self):
        """Test scaling empty boxes array"""
        boxes = np.array([]).reshape(0, 4)
        scaled = scale_boxes(boxes, (100, 100), (200, 200))
        assert scaled.shape == (0, 4)
    
    def test_scale_boxes_upscale(self):
        """Test upscaling boxes"""
        boxes = np.array([[10, 10, 20, 20]])
        scaled = scale_boxes(boxes, (100, 100), (200, 200))
        expected = np.array([[20, 20, 40, 40]])
        np.testing.assert_array_almost_equal(scaled, expected)
    
    def test_scale_boxes_downscale(self):
        """Test downscaling boxes"""
        boxes = np.array([[20, 20, 40, 40]])
        scaled = scale_boxes(boxes, (200, 200), (100, 100))
        expected = np.array([[10, 10, 20, 20]])
        np.testing.assert_array_almost_equal(scaled, expected)
    
    def test_clip_boxes_empty(self):
        """Test clipping empty boxes array"""
        boxes = np.array([]).reshape(0, 4)
        clipped = clip_boxes(boxes, (100, 100))
        assert clipped.shape == (0, 4)
    
    def test_clip_boxes_within_bounds(self):
        """Test clipping boxes already within bounds"""
        boxes = np.array([[10, 10, 20, 20]])
        clipped = clip_boxes(boxes, (100, 100))
        np.testing.assert_array_equal(clipped, boxes)
    
    def test_clip_boxes_out_of_bounds(self):
        """Test clipping boxes outside bounds"""
        boxes = np.array([[-10, -10, 110, 110]])
        clipped = clip_boxes(boxes, (100, 100))
        expected = np.array([[0, 0, 100, 100]])
        np.testing.assert_array_equal(clipped, expected)
    
    def test_xywh_to_xyxy_empty(self):
        """Test converting empty array"""
        boxes = np.array([]).reshape(0, 4)
        converted = xywh_to_xyxy(boxes)
        assert converted.shape == (0, 4)
    
    def test_xywh_to_xyxy(self):
        """Test converting from xywh to xyxy format"""
        # (x_center=10, y_center=10, w=20, h=20) -> (x1=0, y1=0, x2=20, y2=20)
        boxes = np.array([[10, 10, 20, 20]])
        converted = xywh_to_xyxy(boxes)
        expected = np.array([[0, 0, 20, 20]])
        np.testing.assert_array_almost_equal(converted, expected)
    
    def test_xyxy_to_xywh_empty(self):
        """Test converting empty array"""
        boxes = np.array([]).reshape(0, 4)
        converted = xyxy_to_xywh(boxes)
        assert converted.shape == (0, 4)
    
    def test_xyxy_to_xywh(self):
        """Test converting from xyxy to xywh format"""
        # (x1=0, y1=0, x2=20, y2=20) -> (x_center=10, y_center=10, w=20, h=20)
        boxes = np.array([[0, 0, 20, 20]])
        converted = xyxy_to_xywh(boxes)
        expected = np.array([[10, 10, 20, 20]])
        np.testing.assert_array_almost_equal(converted, expected)
    
    def test_conversion_roundtrip(self):
        """Test that converting back and forth preserves values"""
        original = np.array([[0, 0, 20, 20], [10, 10, 30, 30]])
        converted = xyxy_to_xywh(original)
        back = xywh_to_xyxy(converted)
        np.testing.assert_array_almost_equal(back, original)


class TestNMS:
    """Test Non-Maximum Suppression"""
    
    def test_nms_empty(self):
        """Test NMS with empty inputs"""
        boxes = np.array([]).reshape(0, 4)
        scores = np.array([])
        keep = non_max_suppression(boxes, scores)
        assert keep == []
    
    def test_nms_single_box(self):
        """Test NMS with single box"""
        boxes = np.array([[0, 0, 10, 10]])
        scores = np.array([0.9])
        keep = non_max_suppression(boxes, scores)
        assert keep == [0]
    
    def test_nms_no_overlap(self):
        """Test NMS with non-overlapping boxes"""
        boxes = np.array([
            [0, 0, 10, 10],
            [20, 20, 30, 30],
            [40, 40, 50, 50]
        ])
        scores = np.array([0.9, 0.8, 0.7])
        keep = non_max_suppression(boxes, scores, iou_threshold=0.5)
        assert len(keep) == 3
    
    def test_nms_high_overlap(self):
        """Test NMS with highly overlapping boxes"""
        boxes = np.array([
            [0, 0, 10, 10],
            [1, 1, 11, 11],  # High overlap with first box (IoU ~0.68)
            [1.5, 1.5, 11.5, 11.5]   # High overlap with first box (IoU ~0.56)
        ])
        scores = np.array([0.9, 0.8, 0.7])
        keep = non_max_suppression(boxes, scores, iou_threshold=0.5)
        assert len(keep) == 1
        assert keep[0] == 0  # Highest score
    
    def test_nms_per_class_empty(self):
        """Test per-class NMS with empty inputs"""
        boxes = np.array([]).reshape(0, 4)
        scores = np.array([])
        class_ids = np.array([])
        keep = nms_per_class(boxes, scores, class_ids)
        assert keep == []
    
    def test_nms_per_class_single_class(self):
        """Test per-class NMS with single class"""
        boxes = np.array([
            [0, 0, 10, 10],
            [1, 1, 11, 11]
        ])
        scores = np.array([0.9, 0.8])
        class_ids = np.array([0, 0])
        keep = nms_per_class(boxes, scores, class_ids, iou_threshold=0.5)
        assert len(keep) == 1
    
    def test_nms_per_class_multiple_classes(self):
        """Test per-class NMS with multiple classes"""
        boxes = np.array([
            [0, 0, 10, 10],   # Class 0
            [1, 1, 11, 11],   # Class 0, overlaps with first
            [0, 0, 10, 10],   # Class 1, same position as first but different class
        ])
        scores = np.array([0.9, 0.8, 0.85])
        class_ids = np.array([0, 0, 1])
        keep = nms_per_class(boxes, scores, class_ids, iou_threshold=0.5)
        # Should keep 2 boxes: one from class 0, one from class 1
        assert len(keep) == 2


class TestDetectedObject:
    """Test DetectedObject dataclass"""
    
    def test_create_detected_object(self):
        """Test creating DetectedObject"""
        obj = DetectedObject(
            class_id=0,
            class_name="person",
            confidence=0.95,
            bbox=(10, 20, 30, 40)
        )
        assert obj.class_id == 0
        assert obj.class_name == "person"
        assert obj.confidence == 0.95
        assert obj.bbox == (10, 20, 30, 40)


class TestYOLODetector:
    """Test YOLO detector"""
    
    def test_init_without_model(self):
        """Test initializing detector without model"""
        detector = YOLODetector(model_path=None)
        assert detector.model_loaded is False
        assert detector.session is None
    
    def test_init_with_invalid_model(self):
        """Test initializing detector with invalid model path"""
        detector = YOLODetector(model_path="nonexistent.onnx")
        assert detector.model_loaded is False
    
    def test_detect_without_model(self):
        """Test detection without loaded model"""
        detector = YOLODetector(model_path=None)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = detector.detect(frame)
        assert detections == []
    
    def test_set_confidence_threshold(self):
        """Test setting confidence threshold"""
        detector = YOLODetector()
        detector.set_confidence_threshold(0.7)
        assert detector.confidence_threshold == 0.7
    
    def test_set_confidence_threshold_invalid(self):
        """Test setting invalid confidence threshold"""
        detector = YOLODetector()
        with pytest.raises(ValueError):
            detector.set_confidence_threshold(1.5)
        with pytest.raises(ValueError):
            detector.set_confidence_threshold(-0.1)
    
    def test_set_nms_threshold(self):
        """Test setting NMS threshold"""
        detector = YOLODetector()
        detector.set_nms_threshold(0.3)
        assert detector.nms_threshold == 0.3
    
    def test_set_nms_threshold_invalid(self):
        """Test setting invalid NMS threshold"""
        detector = YOLODetector()
        with pytest.raises(ValueError):
            detector.set_nms_threshold(1.5)
        with pytest.raises(ValueError):
            detector.set_nms_threshold(-0.1)
    
    def test_preprocess(self):
        """Test image preprocessing"""
        detector = YOLODetector(input_size=(640, 640))
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        
        tensor, scale_factors = detector._preprocess(frame)
        
        # Check tensor shape
        assert tensor.shape == (1, 3, 640, 640)
        # Check tensor dtype
        assert tensor.dtype == np.float32
        # Check tensor range (should be normalized to [0, 1])
        assert 0.0 <= tensor.min() <= tensor.max() <= 1.0
        # Check scale factors
        assert len(scale_factors) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
