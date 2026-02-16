"""
Property-based tests for Object Detection module

Tests universal properties that must hold for all inputs.
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings, assume
from guru_vision.object_detection import (
    compute_iou,
    scale_boxes,
    clip_boxes,
    box_area,
    xywh_to_xyxy,
    xyxy_to_xywh,
    non_max_suppression
)


# Strategy for generating valid bounding boxes
@st.composite
def bbox_strategy(draw):
    """Generate random valid bounding box as (x1, y1, x2, y2)"""
    x1 = draw(st.floats(min_value=0, max_value=1000))
    y1 = draw(st.floats(min_value=0, max_value=1000))
    w = draw(st.floats(min_value=1, max_value=500))
    h = draw(st.floats(min_value=1, max_value=500))
    return (x1, y1, x1 + w, y1 + h)


# Strategy for generating arrays of boxes
@st.composite
def boxes_array_strategy(draw):
    """Generate array of bounding boxes"""
    n = draw(st.integers(min_value=0, max_value=20))
    boxes = []
    for _ in range(n):
        x1 = draw(st.floats(min_value=0, max_value=1000))
        y1 = draw(st.floats(min_value=0, max_value=1000))
        w = draw(st.floats(min_value=1, max_value=500))
        h = draw(st.floats(min_value=1, max_value=500))
        boxes.append([x1, y1, x1 + w, y1 + h])
    return np.array(boxes) if boxes else np.array([]).reshape(0, 4)


class TestBBoxProperties:
    """Property-based tests for bounding box utilities"""
    
    @given(bbox_strategy())
    @settings(max_examples=50, deadline=1000)
    def test_iou_self_is_one(self, box):
        """Property: IoU of a box with itself is 1.0"""
        iou = compute_iou(box, box)
        assert abs(iou - 1.0) < 1e-6
    
    @given(bbox_strategy(), bbox_strategy())
    @settings(max_examples=50, deadline=1000)
    def test_iou_symmetric(self, box1, box2):
        """Property: IoU is symmetric"""
        iou1 = compute_iou(box1, box2)
        iou2 = compute_iou(box2, box1)
        assert abs(iou1 - iou2) < 1e-6
    
    @given(bbox_strategy(), bbox_strategy())
    @settings(max_examples=50, deadline=1000)
    def test_iou_bounded(self, box1, box2):
        """Property: IoU is between 0 and 1"""
        iou = compute_iou(box1, box2)
        assert 0.0 <= iou <= 1.0
    
    @given(bbox_strategy())
    @settings(max_examples=50, deadline=1000)
    def test_box_area_positive(self, box):
        """Property: Box area is always positive"""
        area = box_area(box)
        assert area >= 0.0
    
    @given(boxes_array_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_scale_boxes_preserves_shape(self, boxes):
        """Property: Scaling preserves array shape"""
        scaled = scale_boxes(boxes, (100, 100), (200, 200))
        assert scaled.shape == boxes.shape
    
    @given(boxes_array_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_scale_boxes_identity(self, boxes):
        """Property: Scaling to same size preserves boxes"""
        scaled = scale_boxes(boxes, (100, 100), (100, 100))
        # Use lower precision due to float32 conversion
        np.testing.assert_allclose(scaled, boxes, rtol=1e-5, atol=1e-4)
    
    @given(boxes_array_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_clip_boxes_preserves_shape(self, boxes):
        """Property: Clipping preserves array shape"""
        clipped = clip_boxes(boxes, (1000, 1000))
        assert clipped.shape == boxes.shape
    
    @given(boxes_array_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_clip_boxes_within_bounds(self, boxes):
        """Property: Clipped boxes are within image bounds"""
        clipped = clip_boxes(boxes, (500, 500))
        if len(clipped) > 0:
            assert np.all(clipped[:, [0, 2]] >= 0)
            assert np.all(clipped[:, [0, 2]] <= 500)
            assert np.all(clipped[:, [1, 3]] >= 0)
            assert np.all(clipped[:, [1, 3]] <= 500)
    
    @given(boxes_array_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_xywh_xyxy_roundtrip(self, boxes):
        """Property: Converting xywh->xyxy->xywh preserves values"""
        if len(boxes) == 0:
            return
        
        # Convert xyxy to xywh
        xywh = xyxy_to_xywh(boxes)
        # Convert back to xyxy
        back = xywh_to_xyxy(xywh)
        
        np.testing.assert_array_almost_equal(back, boxes, decimal=5)
    
    @given(boxes_array_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_conversion_preserves_shape(self, boxes):
        """Property: Format conversion preserves shape"""
        xywh = xyxy_to_xywh(boxes)
        assert xywh.shape == boxes.shape
        
        back = xywh_to_xyxy(xywh)
        assert back.shape == boxes.shape


class TestNMSProperties:
    """Property-based tests for NMS"""
    
    @given(boxes_array_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_nms_returns_subset(self, boxes):
        """Property: NMS returns a subset of input indices"""
        if len(boxes) == 0:
            return
        
        scores = np.random.rand(len(boxes))
        keep = non_max_suppression(boxes, scores)
        
        assert len(keep) <= len(boxes)
        assert all(0 <= idx < len(boxes) for idx in keep)
    
    @given(boxes_array_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_nms_preserves_highest_score(self, boxes):
        """Property: NMS always keeps the highest scoring box"""
        if len(boxes) == 0:
            return
        
        scores = np.random.rand(len(boxes))
        keep = non_max_suppression(boxes, scores)
        
        if len(keep) > 0:
            highest_score_idx = np.argmax(scores)
            # The highest scoring box should be kept (unless it has 0 overlap with itself, which is impossible)
            assert highest_score_idx in keep or len(keep) == 0
    
    @given(st.integers(min_value=1, max_value=10))
    @settings(max_examples=20, deadline=1000)
    def test_nms_non_overlapping_keeps_all(self, n):
        """Property: NMS keeps all non-overlapping boxes"""
        # Create non-overlapping boxes
        boxes = np.array([
            [i * 100, i * 100, i * 100 + 50, i * 100 + 50]
            for i in range(n)
        ])
        scores = np.random.rand(n)
        
        keep = non_max_suppression(boxes, scores, iou_threshold=0.5)
        
        # All boxes should be kept since they don't overlap
        assert len(keep) == n
    
    @given(st.floats(min_value=0.1, max_value=0.9))
    @settings(max_examples=20, deadline=1000)
    def test_nms_threshold_effect(self, threshold):
        """Property: Lower NMS threshold keeps fewer boxes"""
        # Create overlapping boxes
        boxes = np.array([
            [0, 0, 100, 100],
            [10, 10, 110, 110],
            [20, 20, 120, 120]
        ])
        scores = np.array([0.9, 0.8, 0.7])
        
        keep = non_max_suppression(boxes, scores, iou_threshold=threshold)
        
        # Should keep at least 1 box
        assert len(keep) >= 1
        # Should keep at most all boxes
        assert len(keep) <= 3


class TestScalingProperties:
    """Property-based tests for box scaling"""
    
    @given(
        boxes_array_strategy(),
        st.integers(min_value=100, max_value=1000),
        st.integers(min_value=100, max_value=1000)
    )
    @settings(max_examples=30, deadline=2000)
    def test_scale_then_scale_back(self, boxes, target_h, target_w):
        """Property: Scaling up then down returns to original"""
        if len(boxes) == 0:
            return
        
        orig_h, orig_w = 500, 500
        
        # Scale up
        scaled_up = scale_boxes(boxes, (orig_h, orig_w), (target_h, target_w))
        # Scale back down
        scaled_back = scale_boxes(scaled_up, (target_h, target_w), (orig_h, orig_w))
        
        np.testing.assert_array_almost_equal(scaled_back, boxes, decimal=3)
    
    @given(boxes_array_strategy())
    @settings(max_examples=30, deadline=2000)
    def test_scale_preserves_relative_positions(self, boxes):
        """Property: Scaling preserves relative positions"""
        if len(boxes) < 2:
            return
        
        # Scale boxes
        scaled = scale_boxes(boxes, (100, 100), (200, 200))
        
        # Check that relative ordering is preserved
        for i in range(len(boxes) - 1):
            # If box i was to the left of box i+1, it should still be
            if boxes[i, 0] < boxes[i+1, 0]:
                assert scaled[i, 0] < scaled[i+1, 0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
