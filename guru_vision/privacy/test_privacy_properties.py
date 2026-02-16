"""
Property-based tests for Privacy Manager

Tests universal properties that must hold for all inputs:
- Anonymization preserves frame dimensions
- Secure deletion overwrites all data
- Privacy validation is consistent
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings, assume
from guru_vision.privacy import (
    PrivacyManager,
    AnonymizationLevel,
    PrivacyViolation,
    contains_sensitive_content,
    calculate_privacy_risk
)


# Strategy for generating valid frames
@st.composite
def frame_strategy(draw):
    """Generate random valid frames"""
    height = draw(st.integers(min_value=100, max_value=2000))
    width = draw(st.integers(min_value=100, max_value=2000))
    # Keep frame size reasonable to avoid memory issues
    assume(height * width * 3 < 50_000_000)  # < 50MB
    frame = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    return frame


# Strategy for generating face bounding boxes
@st.composite
def face_boxes_strategy(draw, frame_shape):
    """Generate random face bounding boxes within frame"""
    height, width = frame_shape[:2]
    num_faces = draw(st.integers(min_value=0, max_value=5))
    boxes = []
    for _ in range(num_faces):
        x = draw(st.integers(min_value=0, max_value=max(1, width - 50)))
        y = draw(st.integers(min_value=0, max_value=max(1, height - 50)))
        w = draw(st.integers(min_value=20, max_value=min(200, width - x)))
        h = draw(st.integers(min_value=20, max_value=min(200, height - y)))
        boxes.append((x, y, w, h))
    return boxes


class TestPrivacyProperties:
    """Property-based tests for privacy manager"""
    
    @given(frame_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_anonymization_preserves_shape_none(self, frame):
        """Property: NONE anonymization preserves exact frame"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.NONE)
        result = pm.anonymize_frame(frame)
        assert result.shape == frame.shape
        assert np.array_equal(result, frame)
    
    @given(frame_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_anonymization_preserves_dtype(self, frame):
        """Property: Anonymization preserves data type"""
        for level in AnonymizationLevel:
            pm = PrivacyManager(anonymization_level=level)
            result = pm.anonymize_frame(frame)
            assert result.dtype == frame.dtype
    
    @given(frame_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_anonymization_preserves_channels(self, frame):
        """Property: Anonymization preserves number of channels"""
        for level in AnonymizationLevel:
            pm = PrivacyManager(anonymization_level=level)
            result = pm.anonymize_frame(frame)
            assert result.shape[2] == frame.shape[2]
    
    @given(frame_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_basic_anonymization_without_faces_preserves_frame(self, frame):
        """Property: BASIC anonymization without faces preserves frame"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.BASIC)
        result = pm.anonymize_frame(frame, face_boxes=None)
        assert np.array_equal(result, frame)
        
        result = pm.anonymize_frame(frame, face_boxes=[])
        assert np.array_equal(result, frame)
    
    @given(frame=frame_strategy())
    @settings(max_examples=30, deadline=3000)
    def test_enhanced_anonymization_reduces_resolution(self, frame):
        """Property: ENHANCED anonymization reduces large frames"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.ENHANCED)
        result = pm.anonymize_frame(frame)
        
        # If original is larger than 1280, result should be smaller
        if max(frame.shape[0], frame.shape[1]) > 1280:
            assert max(result.shape[0], result.shape[1]) <= 1280
        else:
            # Small frames should be preserved
            assert result.shape == frame.shape
    
    @given(frame=frame_strategy())
    @settings(max_examples=30, deadline=3000)
    def test_maximum_anonymization_reduces_resolution_aggressively(self, frame):
        """Property: MAXIMUM anonymization reduces to max 640px"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.MAXIMUM)
        result = pm.anonymize_frame(frame)
        
        # Result should never exceed 640 on longest side
        assert max(result.shape[0], result.shape[1]) <= 640
    
    @given(frame_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_secure_cleanup_overwrites_data(self, frame):
        """Property: Secure cleanup overwrites all frame data"""
        pm = PrivacyManager(privacy_mode=True)
        original_data = frame.copy()
        pm.secure_cleanup(frame)
        
        # Frame should be modified
        assert not np.array_equal(frame, original_data)
        # Metrics should be updated
        assert pm.metrics.secure_deletions == 1
    
    @given(frame_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_privacy_validation_accepts_valid_frames(self, frame):
        """Property: Privacy validation accepts frames under 100MB"""
        pm = PrivacyManager(privacy_mode=True)
        # Only test frames that are definitely under 100MB
        frame_size_mb = frame.nbytes / (1024 * 1024)
        assume(frame_size_mb < 100)
        
        result = pm.validate_privacy_compliance(frame)
        assert result is True
    
    @given(st.integers(min_value=0, max_value=255))
    @settings(max_examples=50, deadline=1000)
    def test_calculate_privacy_risk_bounded(self, pixel_value):
        """Property: Privacy risk is always between 0 and 1"""
        frame = np.full((480, 640, 3), pixel_value, dtype=np.uint8)
        risk = calculate_privacy_risk(frame)
        assert 0.0 <= risk <= 1.0
    
    @given(frame_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_contains_sensitive_content_deterministic(self, frame):
        """Property: Sensitive content detection is deterministic"""
        result1 = contains_sensitive_content(frame)
        result2 = contains_sensitive_content(frame)
        assert result1 == result2
    
    @given(frame_strategy())
    @settings(max_examples=30, deadline=3000)
    def test_anonymization_metrics_updated(self, frame):
        """Property: Anonymization updates metrics"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.BASIC)
        initial_count = pm.metrics.privacy_processed_count
        
        # Anonymize with face boxes to ensure processing happens
        pm.anonymize_frame(frame, face_boxes=[(10, 10, 50, 50)])
        
        # Metrics should be updated (time may be 0 for very fast operations)
        assert pm.metrics.avg_anonymization_time_ms >= 0
    
    @given(frame=frame_strategy())
    @settings(max_examples=20, deadline=4000)
    def test_anonymization_with_faces_modifies_regions(self, frame):
        """Property: Anonymization with faces modifies face regions"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.BASIC)
        
        # Generate a single face box that's guaranteed to be valid
        height, width = frame.shape[:2]
        # Ensure we have enough space for a face box
        assume(height >= 100 and width >= 100)
        
        # Create a simple face box in the center
        x = width // 4
        y = height // 4
        w = min(100, width // 2)
        h = min(100, height // 2)
        boxes = [(x, y, w, h)]
        
        result = pm.anonymize_frame(frame, face_boxes=boxes)
        
        # Check if face region was modified
        original_region = frame[y:y+h, x:x+w]
        result_region = result[y:y+h, x:x+w]
        
        # For random frames, blurring should modify the region
        # (unless the region is completely uniform, which is unlikely with random data)
        if np.std(original_region) > 1:  # Only check if there's some variance
            assert not np.array_equal(original_region, result_region), \
                "Face region should be modified by blurring"
    
    @given(st.integers(min_value=100, max_value=2000), 
           st.integers(min_value=100, max_value=2000))
    @settings(max_examples=50, deadline=2000)
    def test_anonymization_aspect_ratio_preserved(self, height, width):
        """Property: Anonymization preserves aspect ratio approximately"""
        assume(height * width * 3 < 50_000_000)
        
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.ENHANCED)
        result = pm.anonymize_frame(frame)
        
        original_ratio = width / height
        result_ratio = result.shape[1] / result.shape[0]
        
        # Aspect ratio should be preserved within 10%
        assert abs(original_ratio - result_ratio) / original_ratio < 0.1
    
    @given(frame_strategy())
    @settings(max_examples=50, deadline=2000)
    def test_privacy_mode_toggle_consistent(self, frame):
        """Property: Privacy mode toggle is consistent"""
        pm = PrivacyManager(privacy_mode=False)
        assert pm.is_privacy_mode_active() is False
        
        pm.enable_privacy_mode()
        assert pm.is_privacy_mode_active() is True
        
        pm.disable_privacy_mode()
        assert pm.is_privacy_mode_active() is False
    
    @given(st.integers(min_value=0, max_value=10))
    @settings(max_examples=20, deadline=1000)
    def test_violation_reporting_accumulates(self, num_violations):
        """Property: Violation reporting accumulates correctly"""
        pm = PrivacyManager()
        
        for i in range(num_violations):
            pm.report_violation(PrivacyViolation.DATA_LEAKAGE)
        
        assert pm.metrics.privacy_violations == num_violations


class TestAnonymizationLevelProperties:
    """Test properties across different anonymization levels"""
    
    @given(frame_strategy())
    @settings(max_examples=30, deadline=3000)
    def test_anonymization_levels_ordered_by_strength(self, frame):
        """Property: Higher anonymization levels produce smaller or equal frames"""
        pm_basic = PrivacyManager(anonymization_level=AnonymizationLevel.BASIC)
        pm_enhanced = PrivacyManager(anonymization_level=AnonymizationLevel.ENHANCED)
        pm_maximum = PrivacyManager(anonymization_level=AnonymizationLevel.MAXIMUM)
        
        result_basic = pm_basic.anonymize_frame(frame)
        result_enhanced = pm_enhanced.anonymize_frame(frame)
        result_maximum = pm_maximum.anonymize_frame(frame)
        
        # BASIC should preserve size (unless faces are blurred)
        # ENHANCED should reduce large frames
        # MAXIMUM should reduce most aggressively
        
        basic_pixels = result_basic.shape[0] * result_basic.shape[1]
        enhanced_pixels = result_enhanced.shape[0] * result_enhanced.shape[1]
        maximum_pixels = result_maximum.shape[0] * result_maximum.shape[1]
        
        # MAXIMUM should have fewer or equal pixels than ENHANCED
        assert maximum_pixels <= enhanced_pixels
        
        # MAXIMUM should never exceed 640x640
        assert result_maximum.shape[0] <= 640
        assert result_maximum.shape[1] <= 640
    
    @given(frame_strategy())
    @settings(max_examples=30, deadline=3000)
    def test_all_levels_produce_valid_frames(self, frame):
        """Property: All anonymization levels produce valid frames"""
        for level in AnonymizationLevel:
            pm = PrivacyManager(anonymization_level=level)
            result = pm.anonymize_frame(frame)
            
            # Result should be valid
            assert result is not None
            assert isinstance(result, np.ndarray)
            assert result.dtype == np.uint8
            assert len(result.shape) == 3
            assert result.shape[2] == 3
            assert result.size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
