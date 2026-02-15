"""
GuruVision Liveness Detection Module

This module provides liveness detection (anti-spoofing) functionality
to distinguish live faces from photos, screens, and masks.
"""

from .detector import LivenessDetector, LivenessResult

__all__ = ['LivenessDetector', 'LivenessResult']
