"""
Privacy Manager for Vision Processing

Implements privacy protection including:
- Secure memory deletion
- Image anonymization
- Privacy compliance validation
- Data minimization
"""

import numpy as np
import cv2
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import time


class AnonymizationLevel(Enum):
    """Privacy protection levels"""
    NONE = "none"
    BASIC = "basic"  # Blur faces
    ENHANCED = "enhanced"  # Blur faces + remove metadata
    MAXIMUM = "maximum"  # Heavy processing + data minimization


class PrivacyViolation(Enum):
    """Privacy violation types"""
    IMAGE_STORAGE_ATTEMPT = "image_storage_attempt"
    DATA_LEAKAGE = "data_leakage"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    INSECURE_DELETION = "insecure_deletion"
    ANONYMIZATION_FAILURE = "anonymization_failure"


@dataclass
class PrivacyMetrics:
    """Privacy processing metrics"""
    privacy_processed_count: int = 0
    secure_deletions: int = 0
    privacy_violations: int = 0
    avg_anonymization_time_ms: float = 0.0


class PrivacyManager:
    """Privacy manager for vision processing"""
    
    def __init__(self, privacy_mode: bool = False, 
                 anonymization_level: AnonymizationLevel = AnonymizationLevel.ENHANCED):
        """
        Initialize privacy manager
        
        Args:
            privacy_mode: Enable privacy mode
            anonymization_level: Level of anonymization to apply
        """
        self.privacy_mode = privacy_mode
        self.anonymization_level = anonymization_level
        self.secure_deletion = True
        self.metrics = PrivacyMetrics()
        
    def validate_privacy_compliance(self, frame: np.ndarray) -> bool:
        """
        Validate privacy compliance for frame processing
        
        Args:
            frame: Input frame
            
        Returns:
            True if compliant, False otherwise
            
        Raises:
            ValueError: If privacy violation detected
        """
        if not self.privacy_mode:
            return True
            
        # Check frame size (100MB limit in privacy mode)
        frame_size_mb = frame.nbytes / (1024 * 1024)
        if frame_size_mb > 100:
            self.metrics.privacy_violations += 1
            raise ValueError(f"Frame too large for privacy mode: {frame_size_mb:.2f}MB")
            
        return True
        
    def secure_cleanup(self, frame: np.ndarray) -> None:
        """
        Perform secure cleanup of frame data
        
        Args:
            frame: Frame to securely delete
        """
        if not self.privacy_mode:
            return
            
        # Securely overwrite memory
        if frame is not None and frame.size > 0:
            # Overwrite with zeros
            frame.fill(0)
            # Overwrite with ones
            frame.fill(255)
            # Overwrite with random data
            frame[:] = np.random.randint(0, 256, frame.shape, dtype=frame.dtype)
            
        self.metrics.secure_deletions += 1
        self.metrics.privacy_processed_count += 1
        
    def anonymize_frame(self, frame: np.ndarray, 
                       face_boxes: Optional[list] = None) -> np.ndarray:
        """
        Anonymize frame for privacy protection
        
        Args:
            frame: Input frame
            face_boxes: Optional list of face bounding boxes to blur
            
        Returns:
            Anonymized frame
        """
        start_time = time.time()
        
        if self.anonymization_level == AnonymizationLevel.NONE:
            return frame.copy()
            
        anonymized = frame.copy()
        
        if self.anonymization_level == AnonymizationLevel.BASIC:
            anonymized = self._apply_basic_anonymization(anonymized, face_boxes)
        elif self.anonymization_level == AnonymizationLevel.ENHANCED:
            anonymized = self._apply_enhanced_anonymization(anonymized, face_boxes)
        elif self.anonymization_level == AnonymizationLevel.MAXIMUM:
            anonymized = self._apply_maximum_anonymization(anonymized, face_boxes)
            
        # Update metrics
        processing_time = (time.time() - start_time) * 1000
        self._update_anonymization_metrics(processing_time)
        
        return anonymized
        
    def _apply_basic_anonymization(self, frame: np.ndarray, 
                                   face_boxes: Optional[list] = None) -> np.ndarray:
        """Apply basic anonymization (blur faces)"""
        if face_boxes is None or len(face_boxes) == 0:
            return frame
            
        for box in face_boxes:
            x, y, w, h = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            
            # Ensure coordinates are within frame bounds
            x = max(0, min(x, frame.shape[1] - 1))
            y = max(0, min(y, frame.shape[0] - 1))
            w = max(1, min(w, frame.shape[1] - x))
            h = max(1, min(h, frame.shape[0] - y))
            
            # Extract face region
            face_region = frame[y:y+h, x:x+w]
            
            if face_region.size > 0:
                # Apply Gaussian blur
                kernel_size = max(31, int(min(w, h) * 0.3))
                if kernel_size % 2 == 0:
                    kernel_size += 1
                blurred = cv2.GaussianBlur(face_region, (kernel_size, kernel_size), 0)
                frame[y:y+h, x:x+w] = blurred
                
        return frame
        
    def _apply_enhanced_anonymization(self, frame: np.ndarray,
                                     face_boxes: Optional[list] = None) -> np.ndarray:
        """Apply enhanced anonymization (blur faces + data minimization)"""
        # First apply basic anonymization
        frame = self._apply_basic_anonymization(frame, face_boxes)
        
        # Additional privacy protection: reduce resolution if too high
        max_dimension = 1280
        if frame.shape[0] > max_dimension or frame.shape[1] > max_dimension:
            scale = max_dimension / max(frame.shape[0], frame.shape[1])
            new_width = int(frame.shape[1] * scale)
            new_height = int(frame.shape[0] * scale)
            frame = cv2.resize(frame, (new_width, new_height))
            
        return frame
        
    def _apply_maximum_anonymization(self, frame: np.ndarray,
                                     face_boxes: Optional[list] = None) -> np.ndarray:
        """Apply maximum anonymization (heavy processing + data minimization)"""
        # Apply enhanced anonymization first
        frame = self._apply_enhanced_anonymization(frame, face_boxes)
        
        # Further reduce resolution
        max_dimension = 640
        if frame.shape[0] > max_dimension or frame.shape[1] > max_dimension:
            scale = max_dimension / max(frame.shape[0], frame.shape[1])
            new_width = int(frame.shape[1] * scale)
            new_height = int(frame.shape[0] * scale)
            frame = cv2.resize(frame, (new_width, new_height))
            
        # Add privacy-preserving noise
        noise = np.random.randint(-5, 6, frame.shape, dtype=np.int16)
        frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
        return frame
        
    def _update_anonymization_metrics(self, processing_time_ms: float) -> None:
        """Update anonymization performance metrics"""
        if self.metrics.privacy_processed_count == 0:
            self.metrics.avg_anonymization_time_ms = processing_time_ms
        else:
            count = self.metrics.privacy_processed_count
            self.metrics.avg_anonymization_time_ms = (
                (self.metrics.avg_anonymization_time_ms * count + processing_time_ms) / 
                (count + 1)
            )
            
    def enable_privacy_mode(self) -> None:
        """Enable privacy mode"""
        self.privacy_mode = True
        
    def disable_privacy_mode(self) -> None:
        """Disable privacy mode"""
        self.privacy_mode = False
        
    def get_metrics(self) -> PrivacyMetrics:
        """Get privacy metrics"""
        return self.metrics
        
    def is_privacy_mode_active(self) -> bool:
        """Check if privacy mode is active"""
        return self.privacy_mode
        
    def set_anonymization_level(self, level: AnonymizationLevel) -> None:
        """Set anonymization level"""
        self.anonymization_level = level
        
    def report_violation(self, violation: PrivacyViolation) -> None:
        """Report privacy violation"""
        self.metrics.privacy_violations += 1
        print(f"Privacy violation detected: {violation.value}")


def contains_sensitive_content(frame: np.ndarray) -> bool:
    """
    Check if frame contains potentially sensitive content
    
    Args:
        frame: Input frame
        
    Returns:
        True if sensitive content detected
    """
    # Check frame size
    frame_size_mb = frame.nbytes / (1024 * 1024)
    if frame_size_mb > 50:
        return True
        
    # Check aspect ratio
    if frame.shape[0] > 0 and frame.shape[1] > 0:
        aspect_ratio = frame.shape[1] / frame.shape[0]
        if aspect_ratio < 0.3 or aspect_ratio > 3.0:
            return True
            
    return False


def calculate_privacy_risk(frame: np.ndarray) -> float:
    """
    Calculate privacy risk score for frame
    
    Args:
        frame: Input frame
        
    Returns:
        Risk score between 0.0 and 1.0
    """
    risk_score = 0.0
    
    # Size-based risk
    size_mb = frame.nbytes / (1024 * 1024)
    risk_score += min(size_mb / 10.0, 1.0) * 0.3
    
    # Resolution-based risk
    total_pixels = frame.shape[0] * frame.shape[1]
    if total_pixels > 1920 * 1080:
        risk_score += 0.2
        
    return min(risk_score, 1.0)
