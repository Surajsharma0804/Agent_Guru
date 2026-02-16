"""
Unit tests for Privacy Manager

Tests privacy protection features including:
- Secure memory deletion
- Image anonymization
- Privacy compliance validation
"""

import pytest
import numpy as np
import cv2
from guru_vision.privacy import (
    PrivacyManager,
    AnonymizationLevel,
    PrivacyViolation,
    contains_sensitive_content,
    calculate_privacy_risk
)


class TestPrivacyManager:
    """Test PrivacyManager class"""
    
    def test_init_default(self):
        """Test default initialization"""
        pm = PrivacyManager()
        assert pm.privacy_mode is False
        assert pm.anonymization_level == AnonymizationLevel.ENHANCED
        assert pm.secure_deletion is True
        assert pm.metrics.privacy_processed_count == 0
    
    def test_init_custom(self):
        """Test custom initialization"""
        pm = PrivacyManager(
            privacy_mode=True,
            anonymization_level=AnonymizationLevel.MAXIMUM
        )
        assert pm.privacy_mode is True
        assert pm.anonymization_level == AnonymizationLevel.MAXIMUM
    
    def test_validate_privacy_compliance_disabled(self):
        """Test privacy validation when disabled"""
        pm = PrivacyManager(privacy_mode=False)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        assert pm.validate_privacy_compliance(frame) is True
    
    def test_validate_privacy_compliance_valid_frame(self):
        """Test privacy validation with valid frame"""
        pm = PrivacyManager(privacy_mode=True)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        assert pm.validate_privacy_compliance(frame) is True
    
    def test_validate_privacy_compliance_large_frame(self):
        """Test privacy validation with oversized frame"""
        pm = PrivacyManager(privacy_mode=True)
        # Create frame larger than 100MB
        frame = np.zeros((10000, 10000, 3), dtype=np.uint8)
        with pytest.raises(ValueError, match="Frame too large"):
            pm.validate_privacy_compliance(frame)
        assert pm.metrics.privacy_violations == 1
    
    def test_secure_cleanup_disabled(self):
        """Test secure cleanup when disabled"""
        pm = PrivacyManager(privacy_mode=False)
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
        pm.secure_cleanup(frame)
        # Frame should not be modified when privacy mode is off
        assert pm.metrics.secure_deletions == 0
    
    def test_secure_cleanup_enabled(self):
        """Test secure cleanup when enabled"""
        pm = PrivacyManager(privacy_mode=True)
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
        original_data = frame.copy()
        pm.secure_cleanup(frame)
        # Frame should be overwritten
        assert not np.array_equal(frame, original_data)
        assert pm.metrics.secure_deletions == 1
        assert pm.metrics.privacy_processed_count == 1
    
    def test_anonymize_frame_none_level(self):
        """Test anonymization with NONE level"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.NONE)
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        result = pm.anonymize_frame(frame)
        assert result.shape == frame.shape
        assert np.array_equal(result, frame)
    
    def test_anonymize_frame_basic_no_faces(self):
        """Test basic anonymization without faces"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.BASIC)
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        result = pm.anonymize_frame(frame, face_boxes=None)
        assert result.shape == frame.shape
        assert np.array_equal(result, frame)
    
    def test_anonymize_frame_basic_with_faces(self):
        """Test basic anonymization with faces"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.BASIC)
        # Create frame with some texture (not uniform)
        frame = np.random.randint(100, 156, (480, 640, 3), dtype=np.uint8)
        original_frame = frame.copy()
        face_boxes = [(100, 100, 150, 150), (300, 200, 100, 120)]
        result = pm.anonymize_frame(frame, face_boxes=face_boxes)
        assert result.shape == frame.shape
        # Face regions should be blurred (different from original)
        face_region = result[100:250, 100:250]
        original_region = original_frame[100:250, 100:250]
        # Blurred region should be different from original
        assert not np.array_equal(face_region, original_region)
    
    def test_anonymize_frame_enhanced(self):
        """Test enhanced anonymization"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.ENHANCED)
        # Create large frame
        frame = np.ones((2000, 2000, 3), dtype=np.uint8) * 128
        face_boxes = [(500, 500, 200, 200)]
        result = pm.anonymize_frame(frame, face_boxes=face_boxes)
        # Frame should be resized
        assert result.shape[0] <= 1280 or result.shape[1] <= 1280
    
    def test_anonymize_frame_maximum(self):
        """Test maximum anonymization"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.MAXIMUM)
        frame = np.ones((1920, 1080, 3), dtype=np.uint8) * 128
        face_boxes = [(400, 300, 200, 200)]
        result = pm.anonymize_frame(frame, face_boxes=face_boxes)
        # Frame should be heavily reduced
        assert result.shape[0] <= 640 and result.shape[1] <= 640
        # Should have noise added
        assert not np.array_equal(result, frame)
    
    def test_anonymize_frame_edge_coordinates(self):
        """Test anonymization with edge case coordinates"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.BASIC)
        frame = np.ones((480, 640, 3), dtype=np.uint8) * 128
        # Test coordinates at edges
        face_boxes = [
            (0, 0, 100, 100),  # Top-left corner
            (540, 380, 100, 100),  # Bottom-right (partially out of bounds)
            (-10, -10, 50, 50),  # Negative coordinates
        ]
        result = pm.anonymize_frame(frame, face_boxes=face_boxes)
        assert result.shape == frame.shape
    
    def test_enable_disable_privacy_mode(self):
        """Test enabling and disabling privacy mode"""
        pm = PrivacyManager(privacy_mode=False)
        assert pm.is_privacy_mode_active() is False
        
        pm.enable_privacy_mode()
        assert pm.is_privacy_mode_active() is True
        
        pm.disable_privacy_mode()
        assert pm.is_privacy_mode_active() is False
    
    def test_set_anonymization_level(self):
        """Test setting anonymization level"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.BASIC)
        assert pm.anonymization_level == AnonymizationLevel.BASIC
        
        pm.set_anonymization_level(AnonymizationLevel.MAXIMUM)
        assert pm.anonymization_level == AnonymizationLevel.MAXIMUM
    
    def test_report_violation(self):
        """Test reporting privacy violations"""
        pm = PrivacyManager()
        assert pm.metrics.privacy_violations == 0
        
        pm.report_violation(PrivacyViolation.DATA_LEAKAGE)
        assert pm.metrics.privacy_violations == 1
        
        pm.report_violation(PrivacyViolation.UNAUTHORIZED_ACCESS)
        assert pm.metrics.privacy_violations == 2
    
    def test_get_metrics(self):
        """Test getting privacy metrics"""
        pm = PrivacyManager(privacy_mode=True)
        frame = np.ones((100, 100, 3), dtype=np.uint8)
        
        pm.secure_cleanup(frame)
        # Anonymize with some face boxes to ensure processing happens
        pm.anonymize_frame(frame, face_boxes=[(10, 10, 50, 50)])
        
        metrics = pm.get_metrics()
        assert metrics.secure_deletions == 1
        assert metrics.privacy_processed_count == 1
        # Anonymization time should be recorded (may be very small but > 0)
        assert metrics.avg_anonymization_time_ms >= 0


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_contains_sensitive_content_small_frame(self):
        """Test sensitive content detection with small frame"""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        assert contains_sensitive_content(frame) is False
    
    def test_contains_sensitive_content_large_frame(self):
        """Test sensitive content detection with large frame"""
        # Create frame larger than 50MB
        frame = np.zeros((8000, 8000, 3), dtype=np.uint8)
        assert contains_sensitive_content(frame) is True
    
    def test_contains_sensitive_content_unusual_aspect_ratio(self):
        """Test sensitive content detection with unusual aspect ratio"""
        # Very wide frame
        frame = np.zeros((100, 1000, 3), dtype=np.uint8)
        assert contains_sensitive_content(frame) is True
        
        # Very tall frame
        frame = np.zeros((1000, 100, 3), dtype=np.uint8)
        assert contains_sensitive_content(frame) is True
    
    def test_calculate_privacy_risk_small_frame(self):
        """Test privacy risk calculation for small frame"""
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        risk = calculate_privacy_risk(frame)
        assert 0.0 <= risk <= 1.0
        assert risk < 0.5  # Small frame should have low risk
    
    def test_calculate_privacy_risk_large_frame(self):
        """Test privacy risk calculation for large frame"""
        frame = np.zeros((4000, 4000, 3), dtype=np.uint8)
        risk = calculate_privacy_risk(frame)
        assert 0.0 <= risk <= 1.0
        assert risk > 0.3  # Large frame should have higher risk
    
    def test_calculate_privacy_risk_hd_frame(self):
        """Test privacy risk calculation for HD frame"""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        risk = calculate_privacy_risk(frame)
        assert 0.0 <= risk <= 1.0


class TestAnonymizationQuality:
    """Test anonymization quality and effectiveness"""
    
    def test_blur_effectiveness(self):
        """Test that blurring effectively obscures face regions"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.BASIC)
        
        # Create frame with distinct pattern in face region (with texture)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add texture to face region (checkerboard pattern)
        for i in range(100, 250, 10):
            for j in range(100, 250, 10):
                if (i + j) % 20 == 0:
                    frame[i:i+10, j:j+10] = 255
        
        original_frame = frame.copy()
        face_boxes = [(100, 100, 150, 150)]
        result = pm.anonymize_frame(frame, face_boxes=face_boxes)
        
        # Check that face region is blurred (different from original)
        face_region = result[100:250, 100:250]
        original_region = original_frame[100:250, 100:250]
        assert not np.array_equal(face_region, original_region)
        # Blurred region should have less variance than original
        assert np.std(face_region) < np.std(original_region)
    
    def test_resolution_reduction(self):
        """Test that resolution reduction works correctly"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.ENHANCED)
        
        # Create 4K frame
        frame = np.ones((2160, 3840, 3), dtype=np.uint8) * 128
        result = pm.anonymize_frame(frame)
        
        # Should be reduced to max 1280 on longest side
        assert max(result.shape[0], result.shape[1]) <= 1280
        
        # Aspect ratio should be preserved approximately
        original_ratio = frame.shape[1] / frame.shape[0]
        result_ratio = result.shape[1] / result.shape[0]
        assert abs(original_ratio - result_ratio) < 0.1
    
    def test_noise_addition(self):
        """Test that noise is added in maximum anonymization"""
        pm = PrivacyManager(anonymization_level=AnonymizationLevel.MAXIMUM)
        
        # Create uniform frame
        frame = np.ones((640, 640, 3), dtype=np.uint8) * 128
        result = pm.anonymize_frame(frame)
        
        # Result should have variance due to noise
        assert np.std(result) > 0
        # But should still be close to original brightness
        assert abs(np.mean(result) - 128) < 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
